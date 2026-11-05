from app import create_app


def test_healthz_reports_ok_and_the_running_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "3f9c2ab")
    client = create_app().test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "version": "3f9c2ab"}
