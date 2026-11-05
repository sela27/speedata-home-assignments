# SkyWatch — DevOps Home Assignment

## Overview

Build and deploy SkyWatch, a small distributed weather-query app, on a local Kubernetes cluster, fully automated through CI and GitOps. No cloud account is needed: everything runs on your laptop.

The request flow:

1. A user submits a city name in a **Flask frontend**.
2. The frontend calls a **backend API service** (2 replicas) over HTTP.
3. The backend calls the free [Open-Meteo](https://open-meteo.com) geocoding and forecast APIs (no API key required).
4. The result is returned to the user.

The app itself is deliberately simple. We care most about how you build, ship, and run it.

## System requirements and setup paths

Pick the path that fits your laptop. Both are valid; Path A shows more of your skills.

|  | Path A: Full (recommended) | Path B: Reduced |
| --- | --- | --- |
| Laptop RAM | 16 GB+ | 8 GB |
| Cluster | 3 Ubuntu VMs via [Multipass](https://multipass.run) (or Vagrant), K3s installed with Ansible | Multi-node [k3d](https://k3d.io) or [kind](https://kind.sigs.k8s.io) cluster in Docker |
| Nodes | 1 control plane + 2 workers | 1 control plane + 2 workers (or 1 + 1 if RAM is tight) |
| Ansible | Required | Optional (bonus) |
| VM allocation | ~6–7 GB total (e.g. 1.5 GB control plane, 2.5 GB per worker) | n/a |

Also needed: Docker, ~20 GB free disk, 4+ CPU cores, a GitHub account (for the repo, Actions, and GHCR).

On Apple Silicon, everything in this stack has arm64 support. Make sure the images you build will actually run on your cluster's architecture.

## Tasks

### 1. Application

Write the two small services in Python (or Go, if you prefer):

- **Frontend:** a web page with a city input. On submit, it calls the backend and displays the weather result (current temperature and conditions are enough).
- **Backend:** an HTTP API that takes a city name, calls Open-Meteo, and returns the result. Include a health endpoint.

Keep it minimal. Read configuration, such as the backend URL, from environment variables.

### 2. Cluster provisioning

- **Path A:** create 3 VMs and write Ansible roles that install K3s on the control plane and join the workers. Pin the K3s version. The playbook must be idempotent: re-running it on a healthy cluster must not break anything.
- **Path B:** create the multi-node cluster from a checked-in config file (k3d or kind).
- Both paths: `kubectl` works from your host, and no application workloads are scheduled on the control plane.

### 3. Containerization and CI

- A Dockerfile per service, kept small and production-minded.
- A GitHub Actions pipeline that, on every push to `main`: lints the code, builds both images, pushes them to GitHub Container Registry tagged with the commit SHA, and updates the image tags in your Helm values in Git.
- The tag-update commit must not re-trigger the pipeline in a loop.

### 4. Helm chart

One chart for the whole app:

- Frontend Deployment + Service, reachable from your host.
- Backend Deployment with 2 replicas and an internal Service.
- Configuration through values and ConfigMaps, not hardcoded in images.
- Readiness/liveness probes and resource requests/limits for every container.
- No plaintext secrets committed to Git (e.g. a Grafana admin password if you do the observability bonus). Explain your approach.

### 5. GitOps with ArgoCD

- Install ArgoCD in the cluster and define an `Application` that deploys your chart from your repo.
- Automated sync with prune and self-heal enabled.
- **The key flow:** a code change pushed to `main` ends up running in the cluster with no manual `kubectl` or `helm` commands.

## Bonus (optional)

Pick any that interest you. Depth on one beats a shallow pass on all.

- **Observability:** deploy Prometheus and Grafana (e.g. kube-prometheus-stack), expose app metrics such as request count and latency, and build a dashboard for them.
- **Ansible on Path B:** use Ansible to bootstrap the cluster and its add-ons.
- **Terraform:** provision the cluster (e.g. via a kind/k3d or Multipass provider) and/or install ArgoCD with Terraform.
- **AWS:** deploy the same setup on AWS with Terraform. Destroy it when you're done to avoid costs.
- **Multi-arch images:** build for both `linux/amd64` and `linux/arm64`.
- **ArgoCD app-of-apps:** manage monitoring and other add-ons through ArgoCD as well.
- **Ingress:** expose the frontend through an Ingress controller instead of a NodePort.
- **Autoscaling:** an HPA on the backend based on CPU or request rate.

## Submission and evaluation

Expect about a day of focused work. Submit within 7 days of receiving the assignment.

### What to submit

A link to a public GitHub repo containing all code, manifests, playbooks, and pipelines, plus a README with:

- Which path you chose and step-by-step instructions to bring the system up from scratch.
- An architecture overview and your key design decisions.
- Problems you ran into and how you solved them.
- What you would improve or do differently with more time.
- Proof of the GitOps flow: screenshots or a short recording of a commit rolling out through ArgoCD.

### Using AI

AI tools (Claude, Copilot, Cursor, etc.) are welcome; we use them daily too. You must understand and be able to explain every part of your solution. After submission, we'll hold a review session where you walk us through your work and make a live change or debug an issue.

### How we evaluate

| Area | What we look for |
| --- | --- |
| GitOps flow | Push to `main` reaches the cluster with no manual steps |
| CI pipeline | Clear stages, SHA tagging, no trigger loops, sensible caching |
| Helm and Kubernetes | Clean templates, probes, resources, secrets handled properly |
| Provisioning | Reproducible cluster setup; idempotent Ansible on Path A |
| Code | Readable, minimal, configured via environment |
| Documentation | Someone else can bring it up from the README alone |
| Review session | Understanding of your choices and troubleshooting approach |
