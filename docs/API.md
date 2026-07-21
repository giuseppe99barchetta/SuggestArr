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

For an installation-wide operational snapshot, administrators can use
`GET /api/v1/installation/stats`. It groups counts for requests, enabled and
disabled jobs, job executions, suggestions by status, and the Seer delivery
queue. It returns counters only; it never exposes configuration, identities,
or credentials, and returns `403` for non-administrator keys. Swagger groups
endpoint under **Installation** and documents its complete response schema.

The in-memory rate limiter is per worker. Treat API keys like passwords: do
not place them in URLs, logs, browser storage, or source control.
