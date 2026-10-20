"""Importing the app in tests must not start background jobs against test databases."""
from unittest.mock import patch


def test_importing_the_app_under_tests_starts_no_background_services():
    import api_service.app as app_module

    with patch.object(app_module, '_start_background_services') as start:
        import importlib
        importlib.reload(app_module)
    start.assert_not_called()


def test_a_running_server_starts_them():
    import importlib
    import os
    import api_service.app as app_module

    with patch.dict(os.environ, {'SUGGESTARR_DISABLE_BACKGROUND': '0'}), \
            patch('api_service.jobs.job_manager.JobManager.get_instance') as manager, \
            patch('api_service.db.database_manager.DatabaseManager') as db, \
            patch('api_service.jobs.system_job_sync.sync_system_job_from_config', return_value={'status': 'skipped'}):
        app_module._start_background_services()
    db.assert_called_once()
    manager.return_value.start.assert_called_once()
    job_ids = {call.kwargs.get('id') for call in manager.return_value.scheduler.add_job.call_args_list}
    assert {'seer_queue_worker', 'webhook_delivery_worker', 'seer_availability_sync'} <= job_ids
