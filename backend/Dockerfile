# Stage 1: build a virtualenv with the pinned dependencies.
FROM python:3.14.10-slim-trixie AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /venv
COPY requirements.txt .
RUN /venv/bin/pip install -r requirements.txt

# Stage 2: the runtime gets only the virtualenv and the code.
FROM python:3.14.10-slim-trixie

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /venv /venv
COPY app.py .

# Numeric, so Kubernetes' runAsNonRoot can verify it.
USER 10001:10001
EXPOSE 8080

# Exec form, so SIGTERM reaches gunicorn. The worker temp dir is on
# /dev/shm (memory-backed), so the root filesystem can be read-only.
# gunicorn's control socket is unused and would need a writable home dir.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "app:create_app()"]
