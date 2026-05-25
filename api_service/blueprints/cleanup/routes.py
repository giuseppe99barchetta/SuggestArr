"""Cleanup blueprint — settings + manual run + audit log for the cleanup automation."""

from flask import Blueprint, jsonify, request

from api_service.auth.limiter import limiter
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.jobs.cleanup_automation import execute_cleanup_job, _run_lock as _shared_run_lock

cleanup_bp = Blueprint("cleanup", __name__)
_run_lock = _shared_run_lock
logger = LoggerManager.get_logger("CleanupRoute")


@cleanup_bp.route("/settings", methods=["GET"])
def cleanup_settings_get():
    try:
        return jsonify({"status": "success", "settings": DatabaseManager().get_cleanup_settings()}), 200
    except Exception as exc:
        logger.error("Failed to fetch cleanup settings: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@cleanup_bp.route("/settings", methods=["POST"])
@limiter.limit("30 per minute")
def cleanup_settings_set():
    try:
        data = request.json or {}
        enabled = data.get("enabled")
        dry_run = data.get("dry_run")
        grace_days = data.get("grace_days")

        if grace_days is not None:
            try:
                grace_days = int(grace_days)
            except (TypeError, ValueError):
                return jsonify({"status": "error", "message": "grace_days must be an integer"}), 400
            if grace_days < 1 or grace_days > 365:
                return jsonify({"status": "error", "message": "grace_days must be between 1 and 365"}), 400

        for key, value in (("enabled", enabled), ("dry_run", dry_run)):
            if value is not None and not isinstance(value, bool):
                return jsonify({"status": "error", "message": f"{key} must be a boolean"}), 400

        settings = DatabaseManager().update_cleanup_settings(
            enabled=enabled, dry_run=dry_run, grace_days=grace_days
        )
        return jsonify({"status": "success", "settings": settings}), 200
    except Exception as exc:
        logger.error("Failed to update cleanup settings: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@cleanup_bp.route("/run", methods=["POST"])
async def cleanup_run_now():
    if not _run_lock.acquire(blocking=False):
        return jsonify({
            "status": "error",
            "code": "already_running",
            "message": "A cleanup run is already in progress. Please wait for it to finish.",
        }), 409
    try:
        data = request.json or {}
        override_dry_run = data.get("dry_run")
        if override_dry_run is not None and not isinstance(override_dry_run, bool):
            return jsonify({"status": "error", "message": "dry_run must be a boolean"}), 400
        result = await execute_cleanup_job(force_run=True, override_dry_run=override_dry_run)
        return jsonify({"status": "success", "result": result}), 200
    except Exception as exc:
        logger.error("Manual cleanup run failed: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        try:
            _run_lock.release()
        except RuntimeError:
            pass


@cleanup_bp.route("/log", methods=["GET"])
def cleanup_log_list():
    try:
        try:
            limit = int(request.args.get("limit", 100))
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(500, limit))
        rows = DatabaseManager().get_cleanup_log(limit=limit)
        return jsonify({"status": "success", "log": rows}), 200
    except Exception as exc:
        logger.error("Failed to fetch cleanup log: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500
