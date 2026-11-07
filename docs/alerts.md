# Alerts

Prometheus evaluates two alert rules on the backend every 30 s. They are in [charts/monitoring/templates/prometheusrule.yaml](../charts/monitoring/templates/prometheusrule.yaml), and ArgoCD deploys them with the monitoring app. Alertmanager is disabled, so they notify no one: you see them in Prometheus and Grafana.

| Alert | Its condition |
| --- | --- |
| `SkyWatchBackendHighErrorRate` | over the last 5 minutes, more than 5% of backend requests are answered with a 5xx |
| `SkyWatchBackendHighLatency` | over the last 5 minutes, the backend's p95 latency is above 1 second |

An alert is **inactive** while its condition is false. It is **pending** once the condition is true, and **firing** once the condition has stayed true for 5 minutes. When the condition turns false, the alert goes straight back to inactive. With no traffic, neither condition can be true, so an idle backend raises nothing.

At very low traffic, a few real Open-Meteo timeouts are enough to make both alerts pending, or even fire them: each timeout is a 502 that took over 5 s, and with only a handful of requests in 5 minutes, each one weighs a lot. The rules have no minimum-traffic guard.

## Where to see them

- **Prometheus** has no Ingress. Run `kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090`, then open <http://localhost:9090/alerts> for the states and <http://localhost:9090/rules> for the rules.
- **Grafana** (<http://grafana.192-168-60-11.sslip.io>): go to Alerting > Alert rules. They are listed as data source-managed rules of the Prometheus data source. They are read-only there. Grafana's API returns the same list: `GET /api/prometheus/prometheus/api/v1/rules` (the last `prometheus` in the path is the data source's uid).

## Trigger both: make Open-Meteo unreachable

Nothing answers at 192.0.2.1, an address reserved for documentation (RFC 5737). If the backend calls Open-Meteo there, each call waits out the backend's 5 s timeout (`HTTP_TIMEOUT_SECONDS`). The backend then answers 502, so every request is both a 5xx and slower than 1 second.

The break goes on a throwaway branch that only the `skywatch` app follows, not on `main`, where each push builds and deploys new images.

1. From an up-to-date `main`, create the branch and push it:

   ```bash
   git switch -c alert-demo
   git push -u origin alert-demo
   ```

2. Point the `skywatch` app at it. Pause root's automation first: root's self-heal would otherwise put `skywatch` back on `main`.

   ```bash
   kubectl -n argocd patch application root --type json -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]'
   kubectl -n argocd patch application skywatch --type merge -p '{"spec":{"source":{"targetRevision":"alert-demo"}}}'
   ```

3. In `charts/skywatch/values.yaml`, set the backend's URLs:

   ```yaml
       GEOCODING_URL: https://192.0.2.1/v1/search
       FORECAST_URL: https://192.0.2.1/v1/forecast
   ```

   Commit and push:

   ```bash
   git commit -am "Demo: point the backend at an unreachable Open-Meteo"
   git push
   ```

   ArgoCD checks Git every 60 s. The changed config rolls the backend's pods, and the new pods start with empty caches, so every city needs Open-Meteo.
4. Send a request every few seconds through the frontend:

   ```bash
   while true; do curl -s -o /dev/null -w '%{http_code}\n' "http://skywatch.192-168-60-11.sslip.io/?city=Haifa"; sleep 2; done
   ```

   Each page takes about 5 s and answers 502, "Weather service unavailable". The frontend waits up to 15 s for the backend, so the page shows the backend's 502, not a frontend timeout. Open-Meteo gets no calls.

**What to expect:** both alerts go pending a minute or two after the new pods start answering (Prometheus scrapes every 30 s, and a rate needs two scrapes). They fire 5 minutes after that. The p95 reaches about 7.4 s, not 5 s: the requests fall in the histogram's 5 s to 7.5 s bucket, and the quantile is interpolated inside it.

**To clear them:** revert the commit on the branch:

```bash
git revert --no-edit HEAD
git push
```

ArgoCD rolls the pods back to the real URLs. With or without traffic, both alerts go back to inactive about 5 minutes after the last failed request, once it has left the 5-minute window. Then stop the loop.

**Afterwards**, put root back as Ansible applies it. Its self-heal returns `skywatch` to `main`. Then delete the branch:

```bash
kubectl apply --server-side -f ansible/roles/gitops_bootstrap/files/root-app.yaml
git switch main
git push origin --delete alert-demo
git branch -D alert-demo
```
