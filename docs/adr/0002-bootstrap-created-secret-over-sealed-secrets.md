# Grafana admin secret is created at bootstrap, not with Sealed Secrets

The only secret this project has to manage is Grafana's admin password. Ansible generates a random password during cluster bootstrap and creates the `grafana-admin` Secret once (re-runs never rotate it); the monitoring values only reference it through `admin.existingSecret`, so Git holds no secret material at all. We rejected Sealed Secrets because a SealedSecret is encrypted to one cluster's controller key, and this project recreates its cluster from scratch, on a reviewer's machine and after every `down.ps1`. The committed file would not decrypt there, and the workarounds either ship the private key outside Git or have bootstrap push re-sealed files to the repo.

## Consequences

- The Secret is not tracked by ArgoCD: no drift detection, and rotation is a manual step.
- For a long-lived cluster, the next step would be the External Secrets Operator backed by a real secret store.
