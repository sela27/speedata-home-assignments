import os

import requests
from flask import Flask, render_template, request

# What the visitor sees for each backend answer that is not a Weather report.
FRIENDLY_MESSAGES = {
    400: "Enter a city name",
    404: "City not found",
    502: "Weather service unavailable",
}

# Longer than the backend's own two Open-Meteo calls at 5 seconds each, so a
# slow Open-Meteo still reaches the visitor as the backend's 502.
BACKEND_TIMEOUT_SECONDS = 15


def create_app():
    app = Flask(__name__)
    version = os.environ.get("APP_VERSION", "dev")
    # No default: where the backend runs depends on the deployment, so a
    # missing BACKEND_URL stops the app at startup instead of failing later.
    backend_url = os.environ["BACKEND_URL"]

    def call_backend(path, params=None):
        """GET one backend endpoint; raises requests.RequestException if it can't."""
        return requests.get(
            f"{backend_url}{path}", params=params, timeout=BACKEND_TIMEOUT_SECONDS
        )

    def backend_version():
        """The version the backend's /healthz reports, or "unknown"."""
        try:
            return call_backend("/healthz").json()["version"]
        except requests.RequestException:
            return "unknown"

    def weather_report(city):
        """The Weather report (or None) and the HTTP status for the page."""
        try:
            answer = call_backend("/api/weather", {"city": city})
        except requests.RequestException as error:
            app.logger.warning("Backend call failed: %s", error)
            return None, 502
        if answer.status_code == 200:
            return answer.json(), 200
        if answer.status_code in FRIENDLY_MESSAGES:
            return None, answer.status_code
        # Anything else, e.g. a 500 from a crashed backend, is our upstream failing.
        app.logger.warning("Backend answered %s", answer.status_code)
        return None, 502

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": version}

    @app.get("/")
    def index():
        city = request.args.get("city")
        report, status = None, 200
        # No "city" at all is a first visit. A blank one still goes to the
        # backend, whose 400 is what tells the visitor to enter a city name.
        if city is not None:
            report, status = weather_report(city)
        page = render_template(
            "index.html",
            report=report,
            message=FRIENDLY_MESSAGES.get(status),
            frontend_version=version,
            backend_version=backend_version(),
        )
        return page, status

    return app
