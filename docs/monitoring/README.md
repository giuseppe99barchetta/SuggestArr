# Monitoring

SuggestArr exposes Prometheus metrics at `GET /api/v1/metrics` for an
administrator JWT. Start with the scraper configuration in
[`../API.md`](../API.md#prometheus-metrics), then import the included Grafana
dashboard and load the alert rules into Prometheus.

The webhook and metric endpoints must remain reachable only by trusted
automation. For API-key authentication, terminate the scrape at a reverse
proxy that injects `X-API-Key` rather than storing an API key in Prometheus
configuration.

## Included assets

- `prometheus-alerts.yml`: queue, integration-error, and job-latency alerts.
- `grafana-dashboard.json`: a compact overview for queues, failures, retries,
  and job durations.

Alerts intentionally describe symptoms. Route them through Alertmanager (or an
equivalent) according to the installation's notification policy.
