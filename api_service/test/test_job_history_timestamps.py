from datetime import datetime

from api_service.db.job_repository import JobRepository


def _repository_without_database():
    return JobRepository.__new__(JobRepository)


def test_history_tuple_serializes_database_datetimes_as_iso_strings():
    repository = _repository_without_database()
    started_at = datetime(2026, 9, 8, 14, 30, 0)
    finished_at = datetime(2026, 9, 8, 14, 31, 5)

    history = repository._row_to_history_dict((
        1, 2, started_at, finished_at, 'completed', 3, 1, None, 'Daily', 'manual'
    ))

    assert history['started_at'] == '2026-09-08T14:30:00'
    assert history['finished_at'] == '2026-09-08T14:31:05'


def test_history_mapping_serializes_datetimes_and_preserves_text_values():
    repository = _repository_without_database()
    history = repository._row_to_history_dict({
        'id': 1,
        'started_at': datetime(2026, 9, 8, 14, 30, 0),
        'finished_at': '2026-09-08T14:31:05',
        'status': 'completed',
    })

    assert history['started_at'] == '2026-09-08T14:30:00'
    assert history['finished_at'] == '2026-09-08T14:31:05'
