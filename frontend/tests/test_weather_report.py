import re

import pytest
import requests
import responses
from responses import matchers

from app import create_app

# Not the real address: every test proves the frontend calls BACKEND_URL.
BACKEND_URL = "http://backend.test:8080"


@pytest.fixture
def client(monkeypatch):
    # The full commit SHA, as the chart injects it from the image tag.
    monkeypatch.setenv("APP_VERSION", "5be7d10a3c9e4f8b2d6a1c0e7f3b9d5a2c4e6f81")
    monkeypatch.setenv("BACKEND_URL", BACKEND_URL)
    return create_app().test_client()


@pytest.fixture
def backend():
    """Fake the backend at the HTTP layer; any unregistered call fails."""
    with responses.RequestsMock() as fake:
        yield fake


def fake_backend_version(fake, version):
    fake.get(f"{BACKEND_URL}/healthz", json={"status": "ok", "version": version})


def fake_backend_down(fake):
    # Every call to the backend, whatever its path, is refused.
    refused = requests.exceptions.ConnectionError("Connection refused")
    fake.get(re.compile(f"{re.escape(BACKEND_URL)}/"), body=refused)


def fake_weather_report(fake, city, *, status=200, json):
    fake.get(
        f"{BACKEND_URL}/api/weather",
        match=[matchers.query_param_matcher({"city": city})],
        status=status,
        json=json,
    )


def test_first_visit_shows_the_city_form_and_asks_for_no_weather(client, backend):
    fake_backend_version(backend, "8d1e4f0")

    response = client.get("/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '<form action="/" method="get">' in page
    assert 'name="city"' in page
    assert "Backend 8d1e4f0" in page


def test_weather_report_renders_with_both_versions_in_the_footer(client, backend):
    fake_backend_version(backend, "8d1e4f0")
    fake_weather_report(
        backend,
        "Berlin",
        json={
            "city": "Berlin",
            "country": "Germany",
            "temperature_c": 12.3,
            "conditions": "Clear sky",
        },
    )

    response = client.get("/?city=Berlin")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Berlin, Germany" in page
    assert "12.3 °C" in page
    assert "Clear sky" in page
    assert "Frontend 5be7d10" in page
    assert "Backend 8d1e4f0" in page


def test_weather_report_for_a_place_without_a_country_names_only_the_city(
    client, backend
):
    # The backend sends an empty country when Open-Meteo has none.
    fake_backend_version(backend, "8d1e4f0")
    fake_weather_report(
        backend,
        "Nowhere",
        json={
            "city": "Nowhere",
            "country": "",
            "temperature_c": -31.0,
            "conditions": "Overcast",
        },
    )

    response = client.get("/?city=Nowhere")

    page = response.get_data(as_text=True)
    assert "-31.0 °C" in page
    assert "Nowhere," not in page


# The backend's error answers, as its /api/weather sends them.
@pytest.mark.parametrize(
    ("city", "status", "message"),
    [
        ("", 400, "Enter a city name"),
        ("Xyzzyville", 404, "City not found"),
        ("Berlin", 502, "Weather service unavailable"),
    ],
)
def test_backend_error_renders_as_a_friendly_message(
    client, backend, city, status, message
):
    fake_backend_version(backend, "8d1e4f0")
    fake_weather_report(backend, city, status=status, json={"error": message})

    response = client.get(f"/?city={city}")

    assert response.status_code == status
    page = response.get_data(as_text=True)
    assert message in page
    assert "Backend 8d1e4f0" in page


def test_backend_is_given_15_seconds_for_weather_and_2_for_its_version(client, backend):
    # 15 s is more than the backend's two Open-Meteo calls at 5 seconds each;
    # its /healthz calls nothing, so a hung backend delays the footer only 2 s.
    backend.get(
        f"{BACKEND_URL}/healthz",
        match=[matchers.request_kwargs_matcher({"timeout": 2})],
        json={"status": "ok", "version": "8d1e4f0"},
    )
    backend.get(
        f"{BACKEND_URL}/api/weather",
        match=[matchers.request_kwargs_matcher({"timeout": 15})],
        status=404,
        json={"error": "City not found"},
    )

    response = client.get("/?city=Xyzzyville")

    assert response.status_code == 404
    assert "Backend 8d1e4f0" in response.get_data(as_text=True)


def test_unexpected_backend_answer_renders_as_unavailable(client, backend):
    fake_backend_version(backend, "8d1e4f0")
    backend.get(
        f"{BACKEND_URL}/api/weather",
        status=500,
        body="<h1>Internal Server Error</h1>",
        content_type="text/html",
    )

    response = client.get("/?city=Berlin")

    assert response.status_code == 502
    assert "Weather service unavailable" in response.get_data(as_text=True)


def test_backend_that_is_down_renders_as_unavailable(client, backend):
    fake_backend_down(backend)

    response = client.get("/?city=Berlin")

    assert response.status_code == 502
    page = response.get_data(as_text=True)
    assert "Weather service unavailable" in page
    assert "Frontend 5be7d10" in page
    assert "Backend unknown" in page


def test_footer_shows_the_short_form_of_both_versions(client, backend):
    # Both versions are full commit SHAs; the footer shows Git's short form.
    fake_backend_version(backend, "8d1e4f0b6a2c9e3d7f1a5b8c0e4d2f6a9b3c7e15")

    page = client.get("/").get_data(as_text=True)

    assert "Frontend 5be7d10 · Backend 8d1e4f0" in page


def test_footer_shows_dev_and_unknown_as_they_are(monkeypatch, backend):
    # A local run has no APP_VERSION, and a backend that is down has no version.
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.setenv("BACKEND_URL", BACKEND_URL)
    fake_backend_down(backend)
    client = create_app().test_client()

    page = client.get("/").get_data(as_text=True)

    assert "Frontend dev · Backend unknown" in page
