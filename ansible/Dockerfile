# The Ansible container: the controller that provisions the cluster nodes
# over SSH on the Node network. Build it with: docker build -t skywatch-ansible ansible

# One base image for both stages, the same one the app images use.
ARG PYTHON_IMAGE=python:3.14.10-slim-trixie

# Stage 1: download helm. BuildKit checks the tarball against the pinned
# checksum (published on get.helm.sh) and fails the build if it differs.
# linux-amd64, because the supported host is Windows 11 on x64.
FROM ${PYTHON_IMAGE} AS helm
ADD --checksum=sha256:0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b \
    https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz /tmp/helm.tar.gz
RUN tar -xzf /tmp/helm.tar.gz -C /tmp

# Stage 2: the controller.
FROM ${PYTHON_IMAGE}

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/venv/bin:$PATH"

# Ansible reaches the nodes with ssh. Its version comes with the Debian release
# of the pinned base image. Not pinned in apt, because Debian removes old
# package versions from its mirrors, which would break the build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Pinned Python packages in a virtualenv, and the pinned collection in a
# system-wide collections path, so the non-root user below can use both.
COPY requirements.txt requirements.yml /tmp/
RUN python -m venv /venv \
    && pip install -r /tmp/requirements.txt \
    && ansible-galaxy collection install -r /tmp/requirements.yml -p /usr/share/ansible/collections

COPY --from=helm /tmp/linux-amd64/helm /usr/local/bin/helm

RUN groupadd --gid 10001 ansible \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/sh ansible
USER 10001:10001

CMD ["ansible", "--version"]
