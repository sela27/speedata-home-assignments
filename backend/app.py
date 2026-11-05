import os

import requests
from flask import Flask, request

# Conditions for each WMO weather code, exactly as in the "WMO Weather
# interpretation codes (WW)" table at https://open-meteo.com/en/docs.
# Codes 96 and 99 (hail) come only from models with an explicit hail forecast;
# the other models report thunderstorms as 95 and 97.
CONDITIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    97: "Heavy thunderstorm",
    99: "Thunderstorm with heavy hail",
}


def create_app():
    app = Flask(__name__)
    version = os.environ.get("APP_VERSION", "dev")
    geocoding_url = os.environ.get(
        "GEOCODING_URL", "https://geocoding-api.open-meteo.com/v1/search"
    )
    forecast_url = os.environ.get(
        "FORECAST_URL", "https://api.open-meteo.com/v1/forecast"
    )
    timeout = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "5"))

    def call_open_meteo(url, params):
        """GET one Open-Meteo API; raises requests.RequestException on any failure."""
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def city_lookup(name):
        """The most populous place with this name, or None if there is none."""
        lookup_result = call_open_meteo(
            geocoding_url,
            {"name": name, "count": 1, "language": "en", "format": "json"},
        )
        # Open-Meteo leaves out "results" entirely when nothing matches.
        places = lookup_result.get("results", [])
        return places[0] if places else None

    def weather_report(place):
        current_weather = call_open_meteo(
            forecast_url,
            {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,weather_code",
            },
        )
        current = current_weather["current"]
        return {
            "city": place["name"],
            # Open-Meteo leaves out country for some places.
            "country": place.get("country", ""),
            "temperature_c": current["temperature_2m"],
            "conditions": CONDITIONS.get(current["weather_code"], "Unknown"),
        }

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": version}

    @app.get("/api/weather")
    def weather():
        name = request.args.get("city", "").strip()
        if not name:
            return {"error": "Enter a city name"}, 400
        try:
            place = city_lookup(name)
            if place is None:
                return {"error": "City not found"}, 404
            return weather_report(place)
        except requests.RequestException as error:
            app.logger.warning("Open-Meteo call failed: %s", error)
            return {"error": "Weather service unavailable"}, 502
        except (KeyError, TypeError) as error:
            # An answer without the fields we read, e.g. no "current".
            app.logger.warning("Open-Meteo answer unreadable: %r", error)
            return {"error": "Weather service unavailable"}, 502

    return app
