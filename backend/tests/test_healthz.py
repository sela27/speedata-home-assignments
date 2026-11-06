from app import create_app


def test_healthz_reports_ok_and_the_running_version(monkeypatch):
    # The full commit SHA, as the chart injects it from the image tag.
    monkeypatch.setenv("APP_VERSION", "3f9c2ab7e1d4c8f0a6b2e9d3c5f7a1b8e4d0c26f")
    client = create_app().test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "version": "3f9c2ab7e1d4c8f0a6b2e9d3c5f7a1b8e4d0c26f",
    }


def test_healthz_reports_dev_when_no_version_is_set(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    client = create_app().test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "version": "dev"}
