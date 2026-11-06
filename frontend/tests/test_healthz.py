import pytest
import responses

from app import create_app


@pytest.fixture
def backend():
    """A fake backend with nothing registered: /healthz must not call it, so a
    backend outage can never make the frontend look unhealthy."""
    with responses.RequestsMock() as fake:
        yield fake


def test_healthz_reports_ok_and_the_running_version(monkeypatch, backend):
    # The full commit SHA, as the chart injects it from the image tag. Only
    # the footer shortens it; /healthz reports it whole.
    monkeypatch.setenv("APP_VERSION", "5be7d10a3c9e4f8b2d6a1c0e7f3b9d5a2c4e6f81")
    monkeypatch.setenv("BACKEND_URL", "http://backend.test:8080")
    client = create_app().test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "version": "5be7d10a3c9e4f8b2d6a1c0e7f3b9d5a2c4e6f81",
    }


def test_healthz_reports_dev_when_no_version_is_set(monkeypatch, backend):
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.setenv("BACKEND_URL", "http://backend.test:8080")
    client = create_app().test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "version": "dev"}
