# Grafana admin secret is created at bootstrap, not with Sealed Secrets

The only secret the deployed apps need from this project is Grafana's admin password: Ansible generates it during Bring-up and creates the `grafana-admin` Secret once (re-runs never rotate it), and the monitoring values reference it only through `admin.existingSecret`, so Git holds no secret material. We rejected Sealed Secrets because this project recreates its cluster from scratch, and a SealedSecret committed for one cluster would not decrypt in the next.

## Considered Options

- **Sealed Secrets**: a SealedSecret is encrypted to one cluster's controller key, and every Bring-up creates a new cluster, on a reviewer's machine and after every `down.ps1`, so the committed file would not decrypt there.
- **Sealed Secrets, with the controller's private key shipped outside Git**: the committed file would decrypt, but the private key, itself a secret, would have to reach every machine that runs Bring-up.
- **Sealed Secrets, re-sealed at Bring-up**: the file would match each new cluster, but Bring-up would have to push it to the repo every time.

## Consequences

- The Secret is not tracked by ArgoCD: no drift detection, and rotation is a manual step.
- Ansible also creates the `monitoring` namespace, with the Secret. Both outlive the monitoring app: deleting it leaves them, as [apps/monitoring.yaml](../../apps/monitoring.yaml) says.
- For a long-lived cluster, the next step would be the External Secrets Operator backed by a real secret store.
