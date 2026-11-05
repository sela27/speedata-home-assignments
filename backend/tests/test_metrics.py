import pytest
import requests
import responses
from prometheus_client.parser import text_string_to_metric_families

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
CLEAR_SKY = {"current": {"temperature_2m": 12.3, "weather_code": 0}}


@pytest.fixture
def client(monkeypatch):
    for name in ("GEOCODING_URL", "FORECAST_URL"):
        monkeypatch.delenv(name, raising=False)
    return create_app().test_client()


@pytest.fixture
def open_meteo():
    """Fake Open-Meteo at the HTTP layer; any unregistered call fails."""
    with responses.RequestsMock() as fake:
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
        service="backend",
        endpoint=endpoint,
        status=status,
    )


def test_api_request_is_counted_and_healthz_is_not(client):
    client.get("/api/weather")  # 400, so Open-Meteo is not called
    client.get("/healthz")

    assert requests_counted(client, "/api/weather", "400") == 1
    assert requests_counted(client, "/healthz", "200") is None
    # Each check above scraped /metrics, and none of those scrapes was counted.
    assert requests_counted(client, "/metrics", "200") is None


def test_api_requests_are_counted_by_status_and_timed(client, open_meteo):
    open_meteo.get(GEOCODING_URL, json={"results": [BERLIN]})
    open_meteo.get(FORECAST_URL, json=CLEAR_SKY)

    client.get("/api/weather?city=Berlin")
    client.get("/api/weather?city=")

    assert requests_counted(client, "/api/weather", "200") == 1
    assert requests_counted(client, "/api/weather", "400") == 1
    timed = metric(
        client,
        "http_request_duration_seconds_count",
        service="backend",
        endpoint="/api/weather",
    )
    assert timed == 2


def test_request_for_an_unknown_path_is_counted_without_its_path(client):
    # Scanners try any path; one label value per path would flood Prometheus.
    client.get("/wp-login.php")

    assert requests_counted(client, "unmatched", "404") == 1
    assert requests_counted(client, "/wp-login.php", "404") is None


def test_each_open_meteo_call_is_timed_by_api_even_one_that_fails(client, open_meteo):
    open_meteo.get(GEOCODING_URL, json={"results": [BERLIN]})
    open_meteo.get(FORECAST_URL, body=requests.exceptions.ReadTimeout())

    client.get("/api/weather?city=Berlin")

    calls = "openmeteo_request_duration_seconds_count"
    assert metric(client, calls, api="geocoding") == 1
    # A timeout is the slowest Open-Meteo answer of all, so it counts too.
    assert metric(client, calls, api="forecast") == 1


def test_cache_lookups_are_counted_as_hits_and_misses(client, open_meteo):
    open_meteo.get(GEOCODING_URL, json={"results": [BERLIN]})
    open_meteo.get(FORECAST_URL, json=CLEAR_SKY)

    client.get("/api/weather?city=Berlin")  # both caches miss
    client.get("/api/weather?city=Berlin")  # both caches hit

    lookups = "cache_lookups_total"
    assert metric(client, lookups, cache="city_lookup", result="miss") == 1
    assert metric(client, lookups, cache="city_lookup", result="hit") == 1
    assert metric(client, lookups, cache="weather_report", result="miss") == 1
    assert metric(client, lookups, cache="weather_report", result="hit") == 1
