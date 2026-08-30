"""Deliver signed outbound webhooks from the persistent delivery queue."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import requests

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.observability.metrics import WEBHOOK_DELIVERIES
from api_service.utils.ssrf_guard import validate_url

logger = LoggerManager.get_logger("WebhookWorker")
MAX_RETRIES = 5


def run_webhook_worker():
    db = DatabaseManager()
    for item in db.get_due_webhook_deliveries():
        body = item["payload"].encode("utf-8")
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        signature = hmac.new(item["secret"].encode("utf-8"), timestamp.encode("ascii") + b"." + body,
                             hashlib.sha256).hexdigest()
        try:
            validate_url(item["url"], allow_private=bool(item["allow_private"]))
            response = requests.post(item["url"], data=body, timeout=10, allow_redirects=False, headers={
                "Content-Type": "application/json", "User-Agent": "SuggestArr-Webhook/1",
                "X-SuggestArr-Event": item["event_type"], "X-SuggestArr-Event-Id": item["event_id"],
                "X-SuggestArr-Timestamp": timestamp, "X-SuggestArr-Signature": f"sha256={signature}",
            })
            if 200 <= response.status_code < 300:
                db.update_webhook_delivery(item["id"], "delivered", item["retry_count"])
                WEBHOOK_DELIVERIES.labels(event=item["event_type"], status="delivered").inc()
                continue
            raise RuntimeError(f"HTTP {response.status_code}")
        except Exception as exc:
            retry = item["retry_count"] + 1
            if retry >= MAX_RETRIES:
                db.update_webhook_delivery(item["id"], "failed", retry, error=str(exc))
                WEBHOOK_DELIVERIES.labels(event=item["event_type"], status="failed").inc()
            else:
                next_attempt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=min(30 * (2 ** retry), 3600))
                db.update_webhook_delivery(item["id"], "queued", retry, next_attempt, str(exc))
                WEBHOOK_DELIVERIES.labels(event=item["event_type"], status="retry").inc()
                logger.warning("Webhook %s delivery retry %s: %s", item["event_type"], retry, exc)
