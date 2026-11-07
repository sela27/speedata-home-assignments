# SkyWatch

A small weather-query app (a Flask frontend and a backend API that calls Open-Meteo) running on a local multi-node K3s cluster, delivered through CI (GitHub Actions → GHCR) and GitOps (ArgoCD).

> **Status: work in progress.** This README is a placeholder. The Bring-up guide, the architecture and the decisions are written in milestone M6.

## Chosen path

**Path A**: three Ubuntu 24.04 VMs created with Multipass (one control plane, two workers), with K3s installed by Ansible.

## Supported host

Windows 11 Pro with Hyper-V. Other host operating systems are not supported.

Bring-up writes everything it generates (the SSH key pair, the host kubeconfig, rendered cloud-init files) under `.state/`, which Git ignores.

## Where to look

- The spec: [issue #1](https://github.com/sela27/speedata-home-assignments/issues/1). Its sub-issues are the tickets, with their order of work.
- Key decisions: [docs/adr/](docs/adr/)
- The alerts, and how to trigger each one: [docs/alerts.md](docs/alerts.md)
- Load for the dashboard and the HPA: `scripts\load.ps1` runs k6 on [scripts/load.js](scripts/load.js) for 5 minutes
- Project vocabulary: [GLOSSARY.md](GLOSSARY.md)
- The assignment itself: [skywatch-assignment.md](skywatch-assignment.md)
