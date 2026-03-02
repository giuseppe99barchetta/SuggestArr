"""
Seer Queue Worker — drains the pending_requests table with retry + exponential backoff.

Registered in app.py as a fixed-interval APScheduler job (every 2 minutes,
max_instances=1 to prevent overlap).
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone

from api_service.config.logger_manager import LoggerManager
from api_service.services.config_service import ConfigService
from api_service.db.database_manager import DatabaseManager
from api_service.services.jellyseer.seer_client import SeerClient

MAX_RETRIES = 5
WORKER_BATCH = 50

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


async def _run_worker() -> int:
    """Core async drain loop.

    :return: Number of items successfully submitted.
    """
    db = DatabaseManager()

    # Recover rows stuck in 'submitting' from a previous crash
    db.reset_stale_inflight(cutoff_minutes=10)

    items = db.get_due_requests(max_items=WORKER_BATCH)
    if not items:
        logger.debug("Queue worker: nothing to process.")
        return 0

    logger.info("Queue worker: processing %d item(s).", len(items))

    env = ConfigService.get_runtime_config()
    seer = SeerClient(
        env.get('SEER_API_URL', ''),
        env.get('SEER_TOKEN', ''),
        seer_user_name=env.get('SEER_USER_NAME'),
        seer_password=env.get('SEER_USER_PSW'),
        session_token=env.get('SEER_SESSION_TOKEN'),
        number_of_seasons=env.get('NUMBER_OF_SEASONS', 'all'),
        exclude_downloaded=False,
        exclude_watched=False,  # pre-checks already done at enqueue time
    )
    async with seer:
        await seer.init()

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
                db.mark_pending_failed(row_id, retry_count)
                continue

            # Skip if the item was submitted by another path while it sat in the queue
            if db.check_request_exists(media_type, tmdb_id):
                logger.debug("Queue worker: %s tmdb:%s already in requests, marking submitted.", media_type, tmdb_id)
                db.mark_pending_submitted(row_id, retry_count)
                continue

            # Mark in-flight so a concurrent worker invocation skips this row
            db.mark_pending_submitting(row_id, retry_count)

            try:
                success = await seer.submit_queued_request(payload)
            except Exception as exc:
                logger.error("Queue worker: unexpected error submitting %s tmdb:%s — %s",
                             media_type, tmdb_id, exc, exc_info=True)
                success = False

            if success:
                # Persist to the canonical requests table (idempotent INSERT OR IGNORE).
                # Metadata was already saved at enqueue time by SeerClient.request_media.
                source_id = payload.get('_source_id')
                user_id = payload.get('_user_id')
                rationale = payload.get('_rationale')
                is_anime = bool(payload.get('_is_anime', False))

                db.save_request(media_type, tmdb_id, source_id, user_id,
                                is_anime=is_anime, rationale=rationale)

                db.mark_pending_submitted(row_id, retry_count)
                logger.info("Queue worker: submitted %s tmdb:%s.", media_type, tmdb_id)
                submitted += 1
            else:
                new_retry = retry_count + 1
                if new_retry >= MAX_RETRIES:
                    db.mark_pending_failed(row_id, new_retry)
                    logger.error(
                        "Queue worker: %s tmdb:%s permanently failed after %d retries.",
                        media_type, tmdb_id, new_retry,
                    )
                else:
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
        loop.close()
