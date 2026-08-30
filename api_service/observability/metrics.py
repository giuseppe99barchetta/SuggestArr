"""Low-cardinality Prometheus metrics for SuggestArr operations."""
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

JOB_RUNS = Counter("suggestarr_job_runs_total", "Completed job runs", ("job_type", "status"))
JOB_DURATION = Histogram("suggestarr_job_duration_seconds", "Job execution duration", ("job_type",))
INTEGRATION_ERRORS = Counter("suggestarr_integration_errors_total", "Integration errors", ("service",))
QUEUE_ITEMS = Gauge("suggestarr_seer_queue_items", "Seer delivery queue items", ("status",))
QUEUE_RETRIES = Counter("suggestarr_seer_queue_retries_total", "Seer delivery retries")
WEBHOOK_DELIVERIES = Counter("suggestarr_webhook_deliveries_total", "Webhook deliveries", ("event", "status"))


def observe_job(job_type: str, status: str, duration: float) -> None:
    JOB_RUNS.labels(job_type=job_type, status=status).inc()
    JOB_DURATION.labels(job_type=job_type).observe(duration)


def integration_error(service: str) -> None:
    INTEGRATION_ERRORS.labels(service=service).inc()


def refresh_queue_metrics(db) -> None:
    counts = {status: 0 for status in ("awaiting_approval", "queued", "submitting", "submitted", "failed")}
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM pending_requests GROUP BY status")
        counts.update(dict(cursor.fetchall()))
    for status, count in counts.items():
        QUEUE_ITEMS.labels(status=status).set(count)


def render_metrics(db) -> tuple[bytes, str]:
    refresh_queue_metrics(db)
    return generate_latest(), CONTENT_TYPE_LATEST
