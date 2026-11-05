import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
import responses
from responses import matchers

from app import create_app

# Open-Meteo's public endpoints, as documented at open-meteo.com.
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

BERLIN = {
    "name": "Berlin",
    "country": "Germany",
    "latitude": 52.52437,
    "longitude": 13.41053,
}


@pytest.fixture
def client(monkeypatch):
    for name in ("GEOCODING_URL", "FORECAST_URL", "HTTP_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    return create_app().test_client()


@pytest.fixture
def open_meteo():
    """Fake Open-Meteo at the HTTP layer; any unregistered call fails."""
    with responses.RequestsMock() as fake:
        yield fake


class FakeClock:
    """Stands in for time.monotonic(); time moves only when a test says so."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(time, "monotonic", fake)
    return fake


def fake_city_lookup(fake, name, places, *, url=GEOCODING_URL, also_match=()):
    return fake.get(
        url,
        match=[
            matchers.query_param_matcher({"name": name}, strict_match=False),
            *also_match,
        ],
        json={"results": places, "generationtime_ms": 0.4},
    )


def fake_current_weather(
    fake, place, temperature, weather_code, *, url=FORECAST_URL, also_match=()
):
    coordinates = {"latitude": place["latitude"], "longitude": place["longitude"]}
    return fake.get(
        url,
        match=[
            matchers.query_param_matcher(coordinates, strict_match=False),
            *also_match,
        ],
        json={"current": {"temperature_2m": temperature, "weather_code": weather_code}},
    )


def test_known_city_returns_its_weather_report(client, open_meteo):
    fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    fake_current_weather(open_meteo, BERLIN, temperature=12.3, weather_code=0)

    response = client.get("/api/weather?city=Berlin")

    assert response.status_code == 200
    assert response.get_json() == {
        "city": "Berlin",
        "country": "Germany",
        "temperature_c": 12.3,
        "conditions": "Clear sky",
    }


def test_most_populous_place_wins_when_several_share_the_name(client, open_meteo):
    # Open-Meteo ranks matches by population, most populous first.
    paris_france = {
        "name": "Paris",
        "country": "France",
        "latitude": 48.85341,
        "longitude": 2.3488,
    }
    paris_texas = {
        "name": "Paris",
        "country": "United States",
        "latitude": 33.66094,
        "longitude": -95.55551,
    }
    fake_city_lookup(open_meteo, "Paris", [paris_france, paris_texas])
    fake_current_weather(open_meteo, paris_france, temperature=9.5, weather_code=3)

    response = client.get("/api/weather?city=Paris")

    assert response.get_json()["country"] == "France"


def test_city_lookup_without_a_country_still_returns_a_weather_report(
    client, open_meteo
):
    # Open-Meteo leaves out the fields it has no value for, country included.
    no_country = {"name": "Nowhere", "latitude": -75.25, "longitude": -0.07}
    fake_city_lookup(open_meteo, "Nowhere", [no_country])
    fake_current_weather(open_meteo, no_country, temperature=-31.0, weather_code=3)

    response = client.get("/api/weather?city=Nowhere")

    assert response.status_code == 200
    assert response.get_json() == {
        "city": "Nowhere",
        "country": "",
        "temperature_c": -31.0,
        "conditions": "Overcast",
    }


# Expected wording is copied from the "WMO Weather interpretation codes (WW)"
# table at https://open-meteo.com/en/docs.
@pytest.mark.parametrize(
    ("weather_code", "conditions"),
    [
        (2, "Partly cloudy"),
        (45, "Fog"),
        (63, "Moderate rain"),
        (75, "Heavy snowfall"),
        (97, "Heavy thunderstorm"),
        (99, "Thunderstorm with heavy hail"),
        (42, "Unknown"),  # not in that table
    ],
)
def test_weather_code_is_reported_as_conditions(
    client, open_meteo, weather_code, conditions
):
    fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    fake_current_weather(open_meteo, BERLIN, temperature=4.0, weather_code=weather_code)

    response = client.get("/api/weather?city=Berlin")

    assert response.get_json()["conditions"] == conditions


@pytest.mark.parametrize("query", ["", "?city=", "?city=%20%20"])
def test_missing_or_blank_city_is_a_bad_request(client, open_meteo, query):
    response = client.get(f"/api/weather{query}")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Enter a city name"}


def test_city_that_matches_nothing_is_not_found(client, open_meteo):
    # Open-Meteo leaves out "results" entirely when nothing matches.
    open_meteo.get(GEOCODING_URL, json={"generationtime_ms": 0.3})

    response = client.get("/api/weather?city=Xyzzyville")

    assert response.status_code == 404
    assert response.get_json() == {"error": "City not found"}


def test_open_meteo_error_is_a_bad_gateway(client, open_meteo):
    # Open-Meteo's own error body; it must not be mistaken for "no match".
    open_meteo.get(
        GEOCODING_URL,
        status=500,
        json={"error": True, "reason": "Internal server error"},
    )

    response = client.get("/api/weather?city=Berlin")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Weather service unavailable"}


def test_open_meteo_answer_without_current_weather_is_a_bad_gateway(client, open_meteo):
    fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    open_meteo.get(FORECAST_URL, json={"generationtime_ms": 0.2})

    response = client.get("/api/weather?city=Berlin")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Weather service unavailable"}


def test_open_meteo_timeout_is_a_bad_gateway(client, open_meteo):
    fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    open_meteo.get(FORECAST_URL, body=requests.exceptions.ReadTimeout())

    response = client.get("/api/weather?city=Berlin")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Weather service unavailable"}


def test_open_meteo_is_called_at_its_public_urls_with_a_5_second_timeout(
    client, open_meteo
):
    timeout = matchers.request_kwargs_matcher({"timeout": 5.0})
    fake_city_lookup(open_meteo, "Berlin", [BERLIN], also_match=[timeout])
    fake_current_weather(
        open_meteo, BERLIN, temperature=12.3, weather_code=0, also_match=[timeout]
    )

    response = client.get("/api/weather?city=Berlin")

    assert response.status_code == 200


def test_open_meteo_urls_and_timeout_can_be_set_from_the_environment(
    monkeypatch, open_meteo
):
    monkeypatch.setenv("GEOCODING_URL", "http://geocoding.test/v1/search")
    monkeypatch.setenv("FORECAST_URL", "http://forecast.test/v1/forecast")
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "2.5")
    client = create_app().test_client()
    timeout = matchers.request_kwargs_matcher({"timeout": 2.5})
    fake_city_lookup(
        open_meteo,
        "Berlin",
        [BERLIN],
        url="http://geocoding.test/v1/search",
        also_match=[timeout],
    )
    fake_current_weather(
        open_meteo,
        BERLIN,
        temperature=12.3,
        weather_code=0,
        url="http://forecast.test/v1/forecast",
        also_match=[timeout],
    )

    response = client.get("/api/weather?city=Berlin")

    assert response.status_code == 200


@pytest.mark.parametrize("same_city", ["Berlin", "berlin", "%20%20BERLIN%20"])
def test_second_request_for_the_same_city_makes_no_upstream_call(
    client, open_meteo, same_city
):
    city_lookup = fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    current_weather = fake_current_weather(
        open_meteo, BERLIN, temperature=12.3, weather_code=0
    )
    first = client.get("/api/weather?city=Berlin")

    second = client.get(f"/api/weather?city={same_city}")

    assert second.status_code == 200
    assert second.get_json() == first.get_json()
    assert city_lookup.call_count == 1
    assert current_weather.call_count == 1


def test_weather_report_is_kept_for_10_minutes(client, open_meteo, clock):
    fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    current_weather = fake_current_weather(
        open_meteo, BERLIN, temperature=12.3, weather_code=0
    )
    client.get("/api/weather?city=Berlin")

    clock.advance(9 * 60 + 59)
    client.get("/api/weather?city=Berlin")
    assert current_weather.call_count == 1

    clock.advance(1)
    response = client.get("/api/weather?city=Berlin")
    assert current_weather.call_count == 2
    assert response.status_code == 200


def test_city_lookup_is_kept_for_24_hours(client, open_meteo, clock):
    city_lookup = fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    fake_current_weather(open_meteo, BERLIN, temperature=12.3, weather_code=0)
    client.get("/api/weather?city=Berlin")

    clock.advance(23 * 60 * 60 + 59 * 60)
    client.get("/api/weather?city=Berlin")
    assert city_lookup.call_count == 1

    clock.advance(60)
    response = client.get("/api/weather?city=Berlin")
    assert city_lookup.call_count == 2
    assert response.status_code == 200


def test_city_not_found_is_not_cached(client, open_meteo):
    city_lookup = open_meteo.get(GEOCODING_URL, json={"generationtime_ms": 0.3})
    client.get("/api/weather?city=Xyzzyville")

    response = client.get("/api/weather?city=Xyzzyville")

    assert response.status_code == 404
    assert city_lookup.call_count == 2


def test_weather_service_unavailable_is_not_cached(client, open_meteo):
    fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    # When several fakes match, responses answers with them in order.
    open_meteo.get(FORECAST_URL, body=requests.exceptions.ReadTimeout())
    fake_current_weather(open_meteo, BERLIN, temperature=12.3, weather_code=0)
    first = client.get("/api/weather?city=Berlin")

    second = client.get("/api/weather?city=Berlin")

    assert first.status_code == 502
    assert second.status_code == 200
    assert second.get_json()["temperature_c"] == 12.3


def test_concurrent_requests_for_the_same_city_all_get_its_weather_report(
    client, open_meteo, clock, monkeypatch
):
    fake_city_lookup(open_meteo, "Berlin", [BERLIN])
    fake_current_weather(open_meteo, BERLIN, temperature=12.3, weather_code=0)
    expected = client.get("/api/weather?city=Berlin").get_json()
    clock.advance(10 * 60)  # the cached Weather report has just expired

    # The cache reads the clock after finding an entry and before deleting it
    # as expired. A slow clock holds every thread in that gap at once: without
    # the cache's lock they all delete the same entry, and all but the first
    # fail with a KeyError, which the visitor sees as a 502.
    def slow_clock():
        time.sleep(0.05)
        return clock()

    monkeypatch.setattr(time, "monotonic", slow_clock)

    def ask(_):
        # One test client per thread, all sharing one app and so one cache.
        return client.application.test_client().get("/api/weather?city=Berlin")

    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(ask, range(8)))

    assert [answer.status_code for answer in answers] == [200] * 8
    assert all(answer.get_json() == expected for answer in answers)
