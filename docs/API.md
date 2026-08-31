# Public API v1

SuggestArr exposes its stable external API at `/api/v1`. Dashboard endpoints
under `/api/*` are internal-only and may change without notice. Build external
integrations only against the public v1 routes.

## Addresses

| Purpose | Address |
| --- | --- |
| Interactive Swagger UI | `http://localhost:5000/docs` |
| OpenAPI JSON | `http://localhost:5000/api/v1/openapi.json` |
| OpenAPI YAML | `http://localhost:5000/api/v1/openapi.yaml` |
| Public integration API | `http://localhost:5000/api/v1/...` |
| Internal dashboard API | `http://localhost:5000/api/...` |

Swagger is served directly by the SuggestArr backend and uses the standard
Swagger UI assets bundled with the application; it does not inherit the
SuggestArr dashboard styles. Opening the documentation and specification does
not require a key. API calls that require authentication can be authorized in
Swagger with an API key.

When `SUBPATH=/suggestarr` is configured, prepend `/suggestarr` to every
address above. For example: `http://localhost:5000/suggestarr/docs` and
`http://localhost:5000/suggestarr/api/v1/jobs`.

Create a named API key from Profile. The full value is shown only once; store
it in the integration's secret store and revoke it independently when needed.

```bash
curl -H "X-API-Key: sarr_<key_id>_<secret>" \
  https://suggestarr.example.com/api/v1/jobs
```

JWT bearer tokens and `X-API-Key` both work on public routes, but never send
both in one request. Responses use `data` and optional pagination `meta`.

Available v1 operations currently cover service status, identity, jobs and
their previews, asynchronous job runs, suggestions/actions, and requests.
`GET /api/v1/requests/stats` returns the request counters visible to the
authenticated user (total, today, this week, and this month).

## Run and delivery correlation

Every job run has a numeric `id`, returned when it is queued and readable at
`GET /api/v1/runs/{run_id}`. Queue deliveries produced by that run retain the
same `execution_id`; that run resource returns their delivery `id`, state,
retry metadata and timestamps. These references are safe to use in support
requests and logs: neither response includes Seer payloads, webhook bodies,
tokens, passwords or API keys.

For an installation-wide operational snapshot, administrators can use
`GET /api/v1/installation/stats`. It groups counts for requests, enabled and
disabled jobs, job executions, suggestions by status, and the Seer delivery
queue. It returns counters only; it never exposes configuration, identities,
or credentials, and returns `403` for non-administrator keys. Swagger groups
endpoint under **Installation** and documents its complete response schema.

The in-memory rate limiter is per worker. Treat API keys like passwords: do
not place them in URLs, logs, browser storage, or source control.

## Prometheus metrics

Administrators can scrape `GET /api/v1/metrics` with an administrator JWT.
Deployments that use API keys can instead put a reverse proxy in front of the
endpoint and inject `X-API-Key`; Prometheus' `authorization` block is for
Bearer tokens.
The endpoint exposes low-cardinality job duration/status, integration errors,
Seer queue/retry, and webhook delivery metrics. It never includes titles,
users, credentials, or request payloads as labels.

```yaml
scrape_configs:
  - job_name: suggestarr
    metrics_path: /api/v1/metrics
    authorization:
      type: Bearer
      credentials: <administrator-jwt>
    static_configs:
      - targets: [suggestarr:5000]
```

Recommended alerts are a growing `suggestarr_integration_errors_total`, a
non-zero `suggestarr_seer_queue_items{status="failed"}`, and an elevated job
duration. Use Alertmanager (or your existing alerting system) for routing and
silencing rather than embedding notification policy in SuggestArr.

## Outbound webhooks

Administrators can create signed subscriptions at `POST /api/v1/webhooks`,
list them with `GET /api/v1/webhooks`, and remove one with
`DELETE /api/v1/webhooks/{webhook_id}`. Supported events are:

- `suggestion.created`
- `suggestion.awaiting_approval`
- `suggestion.approved`
- `suggestion.rejected`
- `request.submitted`
- `request.failed`
- `run.failed`

Each delivery is queued persistently and retried with exponential backoff up to
five attempts. The JSON body has the stable envelope
`{"version":1,"event":"…","data":{…}}` and is signed with HMAC-SHA256. Verify the signature
against the exact UTF-8 body using `"<timestamp>.<body>"` and the shared
secret from `X-SuggestArr-Signature`; the timestamp and event identifiers are
provided by `X-SuggestArr-Timestamp`, `X-SuggestArr-Event`, and
`X-SuggestArr-Event-Id`.

Webhook URLs are SSRF-validated. Private-network destinations are rejected by
default; set `allow_private: true` only for trusted local automation such as
Home Assistant or n8n.

Recent delivery status is available to administrators at
`GET /api/v1/webhooks/deliveries`; it intentionally omits secrets and message
bodies. Requeue one delivery with
`POST /api/v1/webhooks/deliveries/{delivery_id}/retry`.
