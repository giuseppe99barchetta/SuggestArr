"""Persistent outbound webhook delivery queue."""
import json
import uuid
from urllib.parse import urlparse

from api_service.services.notification_formats import describe_event, render_notification


class WebhookMixin:
    _WEBHOOK_SERVICE = "outbound_webhooks"

    def get_webhook_allowed_hosts(self):
        config = self.get_integration(self._WEBHOOK_SERVICE) or {}
        return config.get("allowed_hosts", [])

    def set_webhook_allowed_hosts(self, hosts):
        config = self.get_integration(self._WEBHOOK_SERVICE) or {"items": []}
        config["allowed_hosts"] = hosts
        self.set_integration(self._WEBHOOK_SERVICE, config)

    def is_webhook_destination_allowed(self, url):
        hosts = self.get_webhook_allowed_hosts()
        return not hosts or urlparse(url).hostname.lower() in hosts

    def list_webhooks(self):
        items = (self.get_integration(self._WEBHOOK_SERVICE) or {}).get("items", [])
        return [{key: value for key, value in item.items() if key != "secret"} for item in items]

    def create_webhook(self, data):
        item = {
            "id": uuid.uuid4().hex,
            "name": data["name"].strip(), "url": data["url"].strip(), "secret": data["secret"],
            "events": sorted(set(data["events"])), "enabled": bool(data.get("enabled", True)),
            "allow_private": bool(data.get("allow_private", False)),
            "format": data.get("format") or "json",
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
        config["items"] = remaining
        self.set_integration(self._WEBHOOK_SERVICE, config)
        return True

    def enqueue_webhook_event(self, event, payload):
        hooks = (self.get_integration(self._WEBHOOK_SERVICE) or {}).get("items", [])
        event_id = uuid.uuid4().hex
        query = """INSERT INTO webhook_deliveries
            (event_id, webhook_id, event_type, url, secret, allow_private, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)"""
        if self.db_type in ("mysql", "mariadb", "postgres"):
            query = query.replace("?", "%s")
        targets = [hook for hook in hooks if hook.get("enabled", True) and event in hook.get("events", [])]
        # Chat notifications need readable names; looked up once, and only when one is due.
        text = None
        if any(hook.get("format", "json") != "json" for hook in targets):
            text = describe_event(event, payload, *self._webhook_event_names(payload))
        inserted = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for hook in targets:
                fmt = hook.get("format", "json")
                if fmt == "json":
                    url, body = hook["url"], json.dumps({"version": 1, "event": event, "data": payload})
                else:
                    url, body = render_notification(fmt, hook["url"], text)
                cursor.execute(query, (event_id, hook["id"], event, url, hook["secret"],
                                       int(bool(hook.get("allow_private", False))), body))
                inserted += 1
            conn.commit()
        return inserted

    def _webhook_event_names(self, payload):
        """Title and job name an event refers to, or None where unknown.

        :param payload: Webhook event data (``tmdb_id``/``media_type`` and/or ``job_id``).
        :return: Tuple ``(title, job_name)``.
        """
        title = job_name = None
        if payload.get("tmdb_id") and payload.get("media_type"):
            title = (self.get_metadata(str(payload["tmdb_id"]), payload["media_type"]) or {}).get("title")
        if payload.get("job_id") is not None:
            ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT name FROM discover_jobs WHERE id={ph}", (payload["job_id"],))
                row = cursor.fetchone()
                job_name = row[0] if row else None
        return title, job_name

    # Delivery rows for a user's personal destination carry this webhook_id prefix.
    _PERSONAL_PREFIX = "user:"

    def get_personal_notification(self, user_id):
        """A user's own notification destination, or None.

        :param user_id: SuggestArr account id.
        :return: ``{'format', 'url', 'allow_private'}`` or None.
        """
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT notify_config FROM auth_users WHERE id={ph}", (user_id,))
            row = cursor.fetchone()
        try:
            return json.loads(row[0]) if row and row[0] else None
        except (TypeError, ValueError):
            return None

    def set_personal_notification(self, user_id, config):
        """Save (or with None, remove) a user's own notification destination."""
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE auth_users SET notify_config={ph} WHERE id={ph}",
                           (json.dumps(config) if config else None, user_id))
            conn.commit()

    def enqueue_personal_notification(self, user_id, event, text):
        """Queue a chat message to one user's own destination, if they set one.

        :return: True when a delivery was queued.
        """
        config = self.get_personal_notification(user_id)
        if not config or not config.get("url"):
            return False
        url, body = render_notification(config["format"], config["url"], text)
        query = """INSERT INTO webhook_deliveries
            (event_id, webhook_id, event_type, url, secret, allow_private, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)"""
        if self.db_type in ("mysql", "mariadb", "postgres"):
            query = query.replace("?", "%s")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Chat services do not check signatures; the secret only keeps the row uniform.
            cursor.execute(query, (uuid.uuid4().hex, f"{self._PERSONAL_PREFIX}{user_id}", event, url,
                                   uuid.uuid4().hex, int(bool(config.get("allow_private"))), body))
            conn.commit()
        return True

    def get_title_owner_ids(self, media_type, tmdb_id, media_service):
        """SuggestArr accounts a requested title belongs to.

        The owner recorded on its suggestion, plus the account with a verified link
        to the media user it was requested for.

        :return: Set of account ids (possibly empty).
        """
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        owners = set()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT owner_id FROM pending_requests WHERE media_type={ph} AND tmdb_id={ph} "
                           f"AND owner_id IS NOT NULL", (media_type, str(tmdb_id)))
            owners.update(int(row[0]) for row in cursor.fetchall())
            cursor.execute(f"SELECT DISTINCT user_id FROM requests WHERE media_type={ph} AND tmdb_request_id={ph} "
                           f"AND user_id IS NOT NULL", (media_type, str(tmdb_id)))
            media_users = [row[0] for row in cursor.fetchall()]
        for media_user in media_users:
            owner = self.resolve_suggestion_owner(media_service, media_user)
            if owner is not None:
                owners.add(int(owner))
        return owners

    def list_webhook_deliveries(self, max_items=100):
        ph = "%s" if self.db_type in ("mysql", "mariadb", "postgres") else "?"
        # Personal destinations belong to their users; administrators see only shared webhooks.
        query = ("SELECT id,event_id,webhook_id,event_type,url,status,retry_count,next_attempt_at,last_error,created_at,updated_at "
                 f"FROM webhook_deliveries WHERE webhook_id NOT LIKE '{self._PERSONAL_PREFIX}%' ORDER BY id DESC LIMIT " + ph)
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
