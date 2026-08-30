"""Persistent outbound webhook delivery queue."""
import json
import uuid


class WebhookMixin:
    _WEBHOOK_SERVICE = "outbound_webhooks"

    def list_webhooks(self):
        items = (self.get_integration(self._WEBHOOK_SERVICE) or {}).get("items", [])
        return [{key: value for key, value in item.items() if key != "secret"} for item in items]

    def create_webhook(self, data):
        item = {
            "id": uuid.uuid4().hex,
            "name": data["name"].strip(), "url": data["url"].strip(), "secret": data["secret"],
            "events": sorted(set(data["events"])), "enabled": bool(data.get("enabled", True)),
            "allow_private": bool(data.get("allow_private", False)),
        }
        config = self.get_integration(self._WEBHOOK_SERVICE) or {"items": []}
        config["items"] = [*config.get("items", []), item]
        self.set_integration(self._WEBHOOK_SERVICE, config)
        return {key: value for key, value in item.items() if key != "secret"}

    def delete_webhook(self, webhook_id):
        config = self.get_integration(self._WEBHOOK_SERVICE) or {"items": []}
        items = config.get("items", [])
        remaining = [item for item in items if item.get("id") != webhook_id]
        if len(remaining) == len(items):
            return False
        self.set_integration(self._WEBHOOK_SERVICE, {"items": remaining})
        return True

    def enqueue_webhook_event(self, event, payload):
        hooks = (self.get_integration(self._WEBHOOK_SERVICE) or {}).get("items", [])
        event_id = uuid.uuid4().hex
        query = """INSERT INTO webhook_deliveries
            (event_id, webhook_id, event_type, url, secret, allow_private, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)"""
        if self.db_type in ("mysql", "mariadb", "postgres"):
            query = query.replace("?", "%s")
        inserted = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for hook in hooks:
                if hook.get("enabled", True) and event in hook.get("events", []):
                    cursor.execute(query, (event_id, hook["id"], event, hook["url"], hook["secret"],
                                           int(bool(hook.get("allow_private", False))), json.dumps({
                                               "version": 1, "event": event, "data": payload,
                                           })))
                    inserted += 1
            conn.commit()
        return inserted

    def list_webhook_deliveries(self, max_items=100):
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        query = ("SELECT id,event_id,webhook_id,event_type,url,status,retry_count,next_attempt_at,last_error,created_at,updated_at "
                 "FROM webhook_deliveries ORDER BY id DESC LIMIT " + ph)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (max_items,))
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_due_webhook_deliveries(self, max_items=50):
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        query = ("SELECT id,event_id,event_type,url,secret,allow_private,payload,retry_count FROM webhook_deliveries "
                 "WHERE status='queued' AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP) "
                 f"ORDER BY id ASC LIMIT {ph}")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (max_items,))
            return [dict(row) if self.db_type == "sqlite" else dict(zip([x[0] for x in cursor.description], row))
                    for row in cursor.fetchall()]

    def update_webhook_delivery(self, delivery_id, status, retry_count=0, next_attempt_at=None, error=None):
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        query = (f"UPDATE webhook_deliveries SET status={ph},retry_count={ph},next_attempt_at={ph},"
                 f"last_error={ph},updated_at=CURRENT_TIMESTAMP WHERE id={ph}")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, retry_count, next_attempt_at, (error or "")[:500] or None, delivery_id))
            conn.commit()

    def retry_webhook_delivery(self, delivery_id):
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE webhook_deliveries SET status='queued',retry_count=0,next_attempt_at=NULL,last_error=NULL WHERE id={ph} AND status='failed'", (delivery_id,))
            conn.commit()
            return cursor.rowcount > 0
