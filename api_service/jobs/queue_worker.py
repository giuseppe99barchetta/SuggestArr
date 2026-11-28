"""
Seer Queue Worker — drains the pending_requests table with retry + exponential backoff.

Registered in app.py as a fixed-interval APScheduler job (every 2 minutes,
max_instances=1 to prevent overlap).
"""
import asyncio
import json
import math
import time
from contextlib import AsyncExitStack
from datetime import datetime, timedelta, timezone

from api_service.config.logger_manager import LoggerManager
from api_service.exceptions.api_exceptions import is_transport_error
from api_service.services.config_service import ConfigService
from api_service.db.database_manager import DatabaseManager
from api_service.services.arr.arr_request_client import ArrRequestClient
from api_service.services.plex.watchlist_client import PlexWatchlistClient
from api_service.services.seer.seer_client import SeerClient, normalize_seer_url, parse_seer_timestamp
from api_service.utils.asyncio_loop import close_event_loop
from api_service.observability.metrics import INTEGRATION_ERRORS, QUEUE_RETRIES

MAX_RETRIES = 5
WORKER_BATCH = 50
# time.monotonic() of the last Seer delivery, kept across cycles so SEER_REQUEST_DELAY also
# spaces the last request of one cycle and the first of the next (one worker runs at a time).
_last_seer_send = None
# shortcut: while SEER_REQUEST_DELAY is on, a cycle sends at most 1 + 100 // delay Seer requests
# (capped at WORKER_BATCH; 2 at 60 s) and leaves the rest queued, so the pauses keep a run near the 2-minute
# schedule; time spent on Radarr/Sonarr does not count. A long delay therefore caps Seer
# throughput. get_due_requests puts new rows first, so a retry behind 50+ new rows waits for the
# backlog to drain; retries inside the batch go first.
# Radarr/Sonarr rows in the batch go first; one behind 50+ older Seer rows (only after switching
# REQUEST_BACKEND with Seer requests still queued) waits until those drain.
SEER_PACING_SECONDS = 100
# A backend that cannot be reached is retried at a fixed pace without counting as a failed attempt,
# and given up on only after this long of continuous unavailability.
UNAVAILABLE_RETRY_SECONDS = 300
BACKEND_OUTAGE_MAX_DAYS = 7

logger = LoggerManager.get_logger("QueueWorker")


def _backoff_seconds(retry_count: int) -> int:
    """Exponential backoff: 30 s → 60 s → 120 s → 240 s → 480 s (capped at 1 h).

    :param retry_count: The new retry count *after* incrementing.
    :return: Seconds to wait before the next attempt.
    """
    return min(30 * (2 ** retry_count), 3600)


def _next_attempt_at(retry_count: int) -> datetime:
    """Return a UTC datetime offset by the backoff for *retry_count*.

    :param retry_count: The new retry count after incrementing.
    :return: Naive UTC datetime for the next eligible attempt.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=_backoff_seconds(retry_count))


def _destination(backend: str, media_type: str) -> str:
    """Name the real instance a row is delivered to, so one down instance does not hold back the others.

    :param backend: 'seer' or 'arr' (the backend recorded when the row was enqueued).
    :param media_type: 'movie' or 'tv'.
    :return: 'seer', 'radarr' or 'sonarr'.
    """
    if backend == 'arr':
        return 'radarr' if media_type == 'movie' else 'sonarr'
    return 'seer'


def _as_naive_utc(value):
    """Normalize a DB timestamp (datetime or ISO text) to a naive UTC datetime; None stays None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _is_seer_row(item) -> bool:
    """True when a queued row is delivered to Seer (rows queued before ``_backend`` existed are Seer's)."""
    try:
        return (json.loads(item['payload']).get('_backend') or 'seer') == 'seer'
    except (ValueError, TypeError, AttributeError):
        return True  # corrupt payloads are reported when their turn comes


def _seer_request_delay(env) -> float:
    """
    Seconds to wait between two Seer requests in one worker cycle (SEER_REQUEST_DELAY).

    :param env: Runtime configuration.
    :return: The delay, clamped to 0-60 like the settings field; 0 when unset or invalid.
    """
    try:
        delay = float(env.get('SEER_REQUEST_DELAY') or 0)
    except (TypeError, ValueError):
        return 0.0
    return min(max(delay, 0.0), 60.0) if math.isfinite(delay) else 0.0


async def _run_worker() -> int:
    """Core async drain loop.

    :return: Number of items successfully submitted.
    """
    db = DatabaseManager()
    env = ConfigService.get_runtime_config()

    expired = db.expire_pending_approvals(int(env.get('AUTO_REJECT_APPROVAL_DAYS') or 0))
    if expired:
        logger.info("Queue worker: automatically rejected %d expired approval(s).", expired)

    # Recover rows stuck in 'submitting' from a previous crash
    db.reset_stale_inflight(cutoff_minutes=10)

    items = db.get_due_requests(max_items=WORKER_BATCH)
    if not items:
        logger.debug("Queue worker: nothing to process.")
        return 0
    # Radarr/Sonarr rows first: the Seer pause below must not hold them back. Among Seer rows,
    # retries go before new ones, so a paced cycle does not keep pushing them back.
    items.sort(key=lambda item: (_is_seer_row(item), not item.get('retry_count')))

    logger.info("Queue worker: processing %d item(s).", len(items))

    # Each row is delivered by the backend recorded when it was enqueued, never by the
    # current setting, so switching REQUEST_BACKEND cannot reroute queued requests.
    clients = {}
    down = set()  # backends that cannot be built, and destinations found unreachable, in this cycle

    def park_unavailable(item, backend, destination, reason, claimed=False):
        """Keep the row queued, or fail it once the outage has lasted BACKEND_OUTAGE_MAX_DAYS.

        A row cancelled or rejected after it was read is left alone: failing needs the claim (which only
        succeeds on a still-queued row) and parking only updates a queued or sending row.

        :param claimed: True when the caller already claimed the row for delivery.
        """
        since = _as_naive_utc(item.get('unavailable_since'))
        # The current time, not the cycle's start: a paced cycle can run for minutes.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if since is not None and now - since >= timedelta(days=BACKEND_OUTAGE_MAX_DAYS):
            if not claimed and not db.mark_pending_submitting(item['id'], item['retry_count']):
                logger.info("Queue worker: delivery id=%s is no longer queued; skipped.", item['id'])
                return
            db.mark_pending_failed(item['id'], item['retry_count'],
                                   f"Backend unreachable for {BACKEND_OUTAGE_MAX_DAYS} days")
            try:
                db.enqueue_webhook_event("request.failed", {
                    "tmdb_id": str(item['tmdb_id']), "media_type": item['media_type'],
                    "job_id": item.get("job_id"), "execution_id": item.get("execution_id"),
                    "delivery_id": item['id'], "retry_count": item['retry_count'],
                    "reason": "backend_unreachable",
                })
            except Exception as exc:
                logger.error("Unable to queue request.failed webhook: %s", exc)
            logger.error("Queue worker: %s unreachable for %d days; delivery id=%s failed.",
                         destination, BACKEND_OUTAGE_MAX_DAYS, item['id'])
            return
        if not db.mark_pending_unavailable(item['id'], now + timedelta(seconds=UNAVAILABLE_RETRY_SECONDS),
                                           reason):
            logger.info("Queue worker: delivery id=%s is no longer queued; left as is.", item['id'])
            return
        INTEGRATION_ERRORS.labels(service=backend).inc()

    async def client_for(backend, stack):
        if backend not in clients:
            try:
                if backend == 'arr':
                    client = ArrRequestClient(env, env.get('FILTER_NUM_SEASONS') or 'all', False, False,
                                              env.get('REQUEST_FIRST_SEASON_ONLY', False))
                elif backend == 'plex_watchlist':
                    client = PlexWatchlistClient(env, env.get('FILTER_NUM_SEASONS') or 'all', False, False,
                                                 env.get('REQUEST_FIRST_SEASON_ONLY', False))
                else:
                    client = SeerClient(
                        env.get('SEER_API_URL', ''),
                        env.get('SEER_TOKEN', ''),
                        seer_user_name=env.get('SEER_USER_NAME'),
                        seer_password=env.get('SEER_USER_PSW'),
                        session_token=env.get('SEER_SESSION_TOKEN'),
                        number_of_seasons=env.get('FILTER_NUM_SEASONS') or 'all',
                        exclude_downloaded=False,
                        exclude_watched=False,  # pre-checks already done at enqueue time
                        request_first_season_only=env.get('REQUEST_FIRST_SEASON_ONLY', False),
                    )
                await stack.enter_async_context(client)
                await client.init()
                clients[backend] = client
            except Exception as exc:
                logger.error("Queue worker: the %s backend is not usable: %s", backend, exc)
                clients[backend] = None
        return clients[backend]

    # Pause between Seer requests (#118): a burst makes Seer drop notifications. Applied before
    # claiming the row, so nothing sits in 'submitting' while the worker waits.
    global _last_seer_send
    seer_delay = _seer_request_delay(env)
    # Bounded before int(): a tiny delay would make the quotient infinite.
    seer_cap = min(WORKER_BATCH, 1 + int(min(SEER_PACING_SECONDS // seer_delay, WORKER_BATCH))) if seer_delay else WORKER_BATCH
    seer_posts = 0

    def already_submitted(item, payload):
        """Close a row that another path (e.g. AI Search) already requested while it sat in the queue."""
        if not db.check_request_exists(item['media_type'], item['tmdb_id']):
            return False
        # Claim first, as a delivery does: a row cancelled in the meantime must stay cancelled.
        if not db.mark_pending_submitting(item['id'], item['retry_count']):
            logger.info("Queue worker: delivery id=%s is no longer queued; skipped.", item['id'])
            return True
        logger.info("Queue worker: delivery id=%s from job run id=%s was already submitted.",
                    item['id'], item.get('execution_id'))
        db.mark_pending_submitted(item['id'], item['retry_count'])
        try:
            db.enqueue_webhook_event("request.submitted", {
                "tmdb_id": str(item['tmdb_id']), "media_type": item['media_type'], "job_id": item.get("job_id"),
                "execution_id": item.get("execution_id"), "delivery_id": item['id'],
                **({"rationale": payload["_rationale"]} if payload.get("_rationale") else {}),
            })
        except Exception as exc:
            logger.error("Unable to queue request.submitted webhook: %s", exc)
        return True

    async with AsyncExitStack() as stack:
        submitted = 0

        for item in items:
            row_id = item['id']
            tmdb_id = item['tmdb_id']
            media_type = item['media_type']
            retry_count = item['retry_count']
            try:
                payload = json.loads(item['payload'])
            except (json.JSONDecodeError, TypeError) as exc:
                logger.error(
                    "Queue worker: corrupt payload for %s tmdb:%s (row %s) — %s. Marking as failed.",
                    media_type, tmdb_id, row_id, exc,
                )
                db.mark_pending_failed(row_id, retry_count, "Corrupt queued payload")
                try:
                    db.enqueue_webhook_event("request.failed", {
                        "tmdb_id": str(tmdb_id), "media_type": media_type,
                        "job_id": item.get("job_id"), "execution_id": item.get("execution_id"),
                        "delivery_id": row_id, "reason": "corrupt_payload",
                    })
                except Exception as webhook_exc:
                    logger.error("Unable to queue request.failed webhook: %s", webhook_exc)
                continue

            if already_submitted(item, payload):
                continue

            backend = payload.get('_backend') or 'seer'  # rows queued before the field existed are Seer's
            destination = _destination(backend, media_type)
            if destination in down or backend in down:
                park_unavailable(item, backend, destination, f"{destination.capitalize()} is unavailable")
                continue
            client = None
            try:
                client = await client_for(backend, stack)
            except Exception as exc:  # pragma: no cover - client_for already catches everything
                logger.error("Queue worker: %s backend could not be prepared: %s", backend, exc)
            if client is None:
                down.add(backend)
                park_unavailable(item, backend, destination, f"The {backend} backend is not usable")
                continue

            if backend == 'seer' and seer_delay:
                if seer_posts >= seer_cap:
                    # Seer rows come last in the batch, so everything left waits for the next cycle.
                    logger.info("Queue worker: %d Seer request(s) sent with SEER_REQUEST_DELAY=%ss; "
                                "the rest stay queued for the next cycle.", seer_posts, seer_delay)
                    break
                wait = 0.0
                if _last_seer_send is not None:
                    wait = max(seer_delay - (time.monotonic() - _last_seer_send), 0.0)
                if wait:
                    await asyncio.sleep(wait)
                    # Another path may have requested the title during the pause.
                    if already_submitted(item, payload):
                        continue

            # Claim the row: a concurrent worker, or a cancellation since it was read, wins over this one.
            if not db.mark_pending_submitting(row_id, retry_count):
                logger.info("Queue worker: delivery id=%s is no longer queued; skipped.", row_id)
                continue
            try:
                try:
                    success = await client.submit_queued_request(payload)
                finally:
                    if backend == 'seer':
                        # Measured once Seer has answered, so preparation (login, defaults) adds to the gap.
                        _last_seer_send = time.monotonic()
                        seer_posts += 1
            except Exception as exc:
                if is_transport_error(exc):
                    # Not a verdict on the request: keep it queued without spending a retry.
                    down.add(destination)
                    logger.warning("Queue worker: %s is unavailable (%s); delivery id=%s stays queued.",
                                   destination, exc, row_id)
                    park_unavailable(item, backend, destination, f"{destination.capitalize()} is unavailable",
                                     claimed=True)
                    continue
                logger.error("Queue worker: unexpected error submitting %s tmdb:%s — %s",
                             media_type, tmdb_id, exc, exc_info=True)
                success = False

            if success:
                # Persist to the canonical requests table (idempotent INSERT OR IGNORE).
                # Metadata was already saved at enqueue time by SeerClient.request_media.
                source_id = payload.get('_source_id')
                source_origin = payload.get('_source_origin')
                user_id = payload.get('_user_id')
                rationale = payload.get('_rationale')
                is_anime = bool(payload.get('_is_anime', False))

                db.save_request(media_type, tmdb_id, source_id, user_id,
                                is_anime=is_anime, rationale=rationale,
                                source_origin=source_origin)

                db.mark_pending_submitted(row_id, retry_count)
                # Expiry tracking must never turn a successful delivery into a retry.
                if isinstance(success, dict):
                    try:
                        remote_id = success.get('id')
                        if type(remote_id) is not int or remote_id <= 0:
                            raise ValueError('Missing remote ID')
                        db.track_seer_request(
                            row_id, remote_id, parse_seer_timestamp(success['createdAt']),
                            normalize_seer_url(env.get('SEER_API_URL', '')),
                        )
                    except Exception:
                        logger.warning('Delivery %s could not be tracked for expiry; excluded from expiry.', row_id)
                logger.info("Queue worker: delivery id=%s from job run id=%s submitted.", row_id, item.get('execution_id'))
                try:
                    db.enqueue_webhook_event("request.submitted", {
                        "tmdb_id": str(tmdb_id), "media_type": media_type, "job_id": item.get("job_id"),
                        "execution_id": item.get("execution_id"), "delivery_id": row_id,
                        **({"rationale": payload["_rationale"]} if payload.get("_rationale") else {}),
                    })
                except Exception as exc:
                    logger.error("Unable to queue request.submitted webhook: %s", exc)
                submitted += 1
            else:
                INTEGRATION_ERRORS.labels(service=backend).inc()
                new_retry = retry_count + 1
                if new_retry >= MAX_RETRIES:
                    db.mark_pending_failed(row_id, new_retry, "%s rejected the request after maximum retries"
                                           % ("Seer" if backend == 'seer' else "Radarr/Sonarr"))
                    try:
                        db.enqueue_webhook_event("request.failed", {
                            "tmdb_id": str(tmdb_id), "media_type": media_type,
                            "job_id": item.get("job_id"), "execution_id": item.get("execution_id"),
                            "delivery_id": row_id, "retry_count": new_retry,
                        })
                    except Exception as exc:
                        logger.error("Unable to queue request.failed webhook: %s", exc)
                    logger.error(
                        "Queue worker: %s tmdb:%s permanently failed after %d retries.",
                        media_type, tmdb_id, new_retry,
                    )
                else:
                    QUEUE_RETRIES.inc()
                    next_at = _next_attempt_at(new_retry)
                    db.increment_pending_retry(row_id, new_retry, next_at)
                    logger.warning(
                        "Queue worker: %s tmdb:%s retry %d scheduled at %s.",
                        media_type, tmdb_id, new_retry, next_at,
                    )

        return submitted


def run_queue_worker() -> None:
    """Synchronous entry point called by APScheduler (runs in a background thread).

    Creates its own event loop so it is isolated from the main async context.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        submitted = loop.run_until_complete(_run_worker())
        if submitted:
            logger.info("Queue worker cycle complete: %d submission(s).", submitted)
    except Exception as e:
        logger.error("Queue worker cycle failed: %s", e, exc_info=True)
    finally:
        close_event_loop(loop, logger)
