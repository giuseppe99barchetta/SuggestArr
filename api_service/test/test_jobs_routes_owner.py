from unittest.mock import MagicMock

from flask import Flask

from api_service.blueprints.jobs import routes as jobs_routes


def _job_payload():
    return {
        "name": "Owner scoped recommendations",
        "job_type": "recommendation",
        "media_type": "both",
        "filters": {},
        "schedule_type": "preset",
        "schedule_value": "daily",
        "max_results": 10,
        "user_ids": ["media-user"],
    }


def test_create_job_sets_owner_id_none_when_no_current_user(monkeypatch):
    repository = MagicMock()
    repository.create_job.return_value = 1
    monkeypatch.setattr(jobs_routes, "JobRepository", MagicMock(return_value=repository))
    monkeypatch.setattr(jobs_routes, "get_job_manager", MagicMock())

    app = Flask(__name__)
    app.register_blueprint(jobs_routes.jobs_bp, url_prefix="/api/jobs")

    with app.test_client() as client:
        response = client.post("/api/jobs", json=_job_payload())

    assert response.status_code == 201
    repository.create_job.assert_called_once()
    call_args = repository.create_job.call_args[0][0]
    assert call_args["owner_id"] is None
