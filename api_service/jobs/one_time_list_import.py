"""Run a one-time list import in the background, with durable progress and retry."""
import json
import threading

from api_service.config.logger_manager import LoggerManager
from api_service.db.list_import_repository import ListImportRepository
from api_service.jobs.list_import_automation import ListImportAutomation
from api_service.services.public_lists import PublicListError
from api_service.utils.asyncio_loop import run_coroutine_sync

logger = LoggerManager.get_logger('OneTimeListImport')


async def execute_import(owner_id, run_id, token=None):
    repository = ListImportRepository()
    token = token or repository.claim(owner_id, run_id)
    if not token:
        return
    run = repository.get(owner_id, run_id)
    offset, scanned, requested = run['scan_offset'], run['scanned_count'], run['requested_count']
    automation = None
    try:
        automation = await ListImportAutomation.from_config(json.loads(run['config_json']), owner_id)
        # Process bounded batches until the end, rather than the scheduled-job cap.
        automation.SCAN_LIMIT = 100
        while True:
            base_scanned, base_requested = scanned, requested
            def progress(current_offset, checked, queued):
                return repository.update(run_id, token, current_offset,
                                         base_scanned + checked, base_requested + queued)
            result = await automation.run(start_offset=offset, progress=progress)
            offset = automation.next_offset
            scanned += result.results_count
            requested += result.requested_count
            if not result.success:
                repository.update(run_id, token, offset, scanned, requested, 'failed', result.error_message)
                return
            if automation.scan_complete:
                repository.update(run_id, token, 0, scanned, requested, 'completed')
                return
    except Exception as exc:
        message = str(exc) if isinstance(exc, PublicListError) else 'Import failed. Retry to continue safely.'
        repository.update(run_id, token, offset, scanned, requested, 'failed', message)
        logger.error('One-time list import %s failed (%s).', run_id, type(exc).__name__)
    finally:
        if automation:
            await automation._close_clients()


def start_import(owner_id, run_id):
    token = ListImportRepository().claim(owner_id, run_id)
    if not token:
        return
    # Browser navigation does not stop the import; interrupted server runs can resume.
    threading.Thread(target=lambda: run_coroutine_sync(execute_import(owner_id, run_id, token), logger), daemon=True).start()
