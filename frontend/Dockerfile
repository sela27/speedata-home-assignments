# One base image for both stages, so they cannot drift apart.
ARG PYTHON_IMAGE=python:3.14.10-slim-trixie

# Stage 1: build a virtualenv with the pinned dependencies.
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /venv
COPY requirements.txt .
RUN /venv/bin/pip install -r requirements.txt

# Stage 2: the runtime gets only the virtualenv and the code.
FROM ${PYTHON_IMAGE}

ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /venv /venv
COPY app.py .
COPY templates/ templates/

# Numeric, so Kubernetes' runAsNonRoot can verify it.
USER 10001:10001
EXPOSE 8080

# Exec form, so SIGTERM reaches gunicorn. The worker temp dir is on
# /dev/shm (memory-backed), so the root filesystem can be read-only.
# gunicorn's control socket is unused and would need a writable home dir.
# 1 worker, so the Prometheus metrics live in one process.
# 128 threads, more than load.js's 100 waiting pages, so a probe
# always gets one.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "128", "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "app:create_app()"]
