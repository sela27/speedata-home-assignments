import os

from flask import Flask


def create_app():
    app = Flask(__name__)
    version = os.environ.get("APP_VERSION", "dev")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": version}

    return app
