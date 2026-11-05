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
CLEAR_AND_MILD = {"current": {"temperature_2m": 12.3, "weather_code": 0}}


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


def fake_city_lookup(fake, name, places):
    fake.get(
        GEOCODING_URL,
        match=[matchers.query_param_matcher({"name": name}, strict_match=False)],
        json={"results": places, "generationtime_ms": 0.4},
    )


def fake_current_weather(fake, place, temperature, weather_code):
    coordinates = {"latitude": place["latitude"], "longitude": place["longitude"]}
    fake.get(
        FORECAST_URL,
        match=[matchers.query_param_matcher(coordinates, strict_match=False)],
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


# Expected wording follows the WMO code table in Open-Meteo's forecast docs.
@pytest.mark.parametrize(
    ("weather_code", "conditions"),
    [
        (2, "Partly cloudy"),
        (45, "Fog"),
        (63, "Moderate rain"),
        (75, "Heavy snowfall"),
        (97, "Heavy thunderstorm"),
        (99, "Thunderstorm with heavy hail"),
        (42, "Unknown"),  # not a WMO code Open-Meteo uses
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
    open_meteo.get(GEOCODING_URL, match=[timeout], json={"results": [BERLIN]})
    open_meteo.get(FORECAST_URL, match=[timeout], json=CLEAR_AND_MILD)

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
    open_meteo.get(
        "http://geocoding.test/v1/search", match=[timeout], json={"results": [BERLIN]}
    )
    open_meteo.get(
        "http://forecast.test/v1/forecast", match=[timeout], json=CLEAR_AND_MILD
    )

    response = client.get("/api/weather?city=Berlin")

    assert response.status_code == 200
