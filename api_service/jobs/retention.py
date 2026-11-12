"""Daily housekeeping: delete rows nobody reads any more from the tables that only grow.

Only tables whose rows have no other reader are pruned. ``pending_requests``, ``request_expiry_log`` and
``job_execution_history`` are deliberately kept: replacements, the installation statistics and the run
history depend on them.
"""
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager.get_logger("Retention")

WEBHOOK_RETENTION_DAYS = 30
CLEANUP_LOG_RETENTION_DAYS = 90
STALE_LOCK_SECONDS = 3600


def run_retention() -> dict:
    """Prune expired sessions, finished webhook deliveries, old cleanup audit rows and stale locks.

    Each step is independent: one failing does not stop the others.

    :return: Number of rows deleted per step.
    """
    db = DatabaseManager()
    steps = {
        'refresh_tokens': db.cleanup_expired_refresh_tokens,
        'webhook_deliveries': lambda: db.prune_webhook_deliveries(WEBHOOK_RETENTION_DAYS),
        'cleanup_log': lambda: db.prune_cleanup_log(CLEANUP_LOG_RETENTION_DAYS),
        'submission_locks': lambda: db.purge_stale_submission_locks(STALE_LOCK_SECONDS),
    }
    deleted = {}
    for name, step in steps.items():
        try:
            deleted[name] = step()
        except Exception as exc:
            deleted[name] = 0
            logger.error("Retention step %s failed: %s", name, exc)
    logger.info("Retention finished: %s", deleted)
    return deleted
