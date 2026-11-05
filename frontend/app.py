import os
import time

import requests
from flask import Flask, g, render_template, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

# What the visitor sees for each backend answer that is not a Weather report.
FRIENDLY_MESSAGES = {
    400: "Enter a city name",
    404: "City not found",
    502: "Weather service unavailable",
}

# Longer than the backend's own two Open-Meteo calls at 5 seconds each, so a
# slow Open-Meteo still reaches the visitor as the backend's 502.
BACKEND_TIMEOUT_SECONDS = 15
# The backend's /healthz waits on nothing, so 2 seconds is plenty: a backend
# that hangs then delays the page's footer by 2 seconds, not another 15.
BACKEND_VERSION_TIMEOUT_SECONDS = 2


def create_app():
    app = Flask(__name__)
    version = os.environ.get("APP_VERSION", "dev")
    # No default: where the backend runs depends on the deployment, so a
    # missing BACKEND_URL stops the app at startup instead of failing later.
    backend_url = os.environ["BACKEND_URL"]

    # The backend's RED metrics, same names and labels, so one dashboard query
    # covers both services. Metrics go in this app's own registry, not
    # prometheus-client's global one, so every create_app() (one per test)
    # starts from zero. gunicorn runs one worker, so this one registry sees
    # every request the pod answers.
    registry = CollectorRegistry()
    # RED: rate and errors from the counter, duration from the histogram.
    http_requests = Counter(
        "http_requests_total",
        "HTTP requests answered, by route and status",
        ["service", "endpoint", "status"],
        registry=registry,
    )
    http_request_duration = Histogram(
        "http_request_duration_seconds",
        "Time to answer an HTTP request, by route",
        ["service", "endpoint"],
        registry=registry,
    )

    def call_backend(path, params=None, timeout=BACKEND_TIMEOUT_SECONDS):
        """GET one backend endpoint; raises requests.RequestException if it can't."""
        return requests.get(f"{backend_url}{path}", params=params, timeout=timeout)

    def backend_version():
        """The version the backend's /healthz reports, or "unknown"."""
        try:
            answer = call_backend("/healthz", timeout=BACKEND_VERSION_TIMEOUT_SECONDS)
            return answer.json()["version"]
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

    @app.before_request
    def start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def count_request(response):
        # The route ("/"), never the raw path, so a scanner trying many paths
        # can't create many label values. A 404 for an unknown path (or a
        # 405) has no route.
        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        # Probes and scrapes are not visitors' traffic.
        if endpoint not in ("/healthz", "/metrics"):
            http_requests.labels(
                service="frontend", endpoint=endpoint, status=response.status_code
            ).inc()
            http_request_duration.labels(service="frontend", endpoint=endpoint).observe(
                time.perf_counter() - g.request_started
            )
        return response

    @app.get("/metrics")
    def metrics():
        return generate_latest(registry), {"Content-Type": CONTENT_TYPE_LATEST}

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
