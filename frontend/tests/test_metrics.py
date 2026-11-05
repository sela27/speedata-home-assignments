import pytest
import responses
from prometheus_client.parser import text_string_to_metric_families
from responses import matchers

from app import create_app

# Not the real address: every test proves the frontend calls BACKEND_URL.
BACKEND_URL = "http://backend.test:8080"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", BACKEND_URL)
    return create_app().test_client()


@pytest.fixture
def backend():
    """Fake the backend at the HTTP layer; any unregistered call fails."""
    with responses.RequestsMock() as fake:
        fake.get(f"{BACKEND_URL}/healthz", json={"status": "ok", "version": "8d1e4f0"})
        yield fake


def metric(client, name, **labels):
    """What GET /metrics reports for one sample, or None if it isn't there."""
    page = client.get("/metrics").get_data(as_text=True)
    for family in text_string_to_metric_families(page):
        for sample in family.samples:
            if sample.name == name and sample.labels == labels:
                return sample.value
    return None


def requests_counted(client, endpoint, status):
    return metric(
        client,
        "http_requests_total",
        service="frontend",
        endpoint=endpoint,
        status=status,
    )


def test_page_request_is_counted_and_healthz_is_not(client, backend):
    client.get("/")  # first visit: only the backend's version is asked for
    client.get("/healthz")

    assert requests_counted(client, "/", "200") == 1
    assert requests_counted(client, "/healthz", "200") is None
    # Each check above scraped /metrics, and none of those scrapes was counted.
    assert requests_counted(client, "/metrics", "200") is None


def test_page_requests_are_counted_by_status_and_timed(client, backend):
    backend.get(
        f"{BACKEND_URL}/api/weather",
        match=[matchers.query_param_matcher({"city": "Berlin"})],
        json={
            "city": "Berlin",
            "country": "Germany",
            "temperature_c": 12.3,
            "conditions": "Clear sky",
        },
    )
    backend.get(
        f"{BACKEND_URL}/api/weather",
        match=[matchers.query_param_matcher({"city": "Xyzzyville"})],
        status=404,
        json={"error": "City not found"},
    )

    client.get("/?city=Berlin")
    client.get("/?city=Xyzzyville")

    assert requests_counted(client, "/", "200") == 1
    assert requests_counted(client, "/", "404") == 1
    timed = metric(
        client,
        "http_request_duration_seconds_count",
        service="frontend",
        endpoint="/",
    )
    assert timed == 2


def test_request_for_an_unknown_path_is_counted_without_its_path(client):
    # Scanners try any path; one label value per path would flood Prometheus.
    response = client.get("/wp-login.php")

    assert response.status_code == 404
    assert requests_counted(client, "unmatched", "404") == 1
    assert requests_counted(client, "/wp-login.php", "404") is None
