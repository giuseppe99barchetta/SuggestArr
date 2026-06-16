from flask import Flask

from api_service.blueprints.logs import routes


def test_read_logs_returns_latest_page_with_offset(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("".join(f"line {index}\n" for index in range(1, 11)), encoding="utf-8")

    logs = routes.read_logs(log_file=str(log_file), limit=3, offset=2)

    assert logs == ["line 6\n", "line 7\n", "line 8\n"]


def test_read_logs_returns_empty_when_offset_exceeds_file(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("line 1\nline 2\n", encoding="utf-8")

    logs = routes.read_logs(log_file=str(log_file), limit=3, offset=5)

    assert logs == []


def test_get_logs_passes_limit_and_offset_query_params(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(routes.logs_bp, url_prefix="/api")
    captured = {}

    def fake_read_logs(limit, offset):
        captured["limit"] = limit
        captured["offset"] = offset
        return ["line 1\n"]

    monkeypatch.setattr(routes, "read_logs", fake_read_logs)

    response = app.test_client().get("/api/logs?limit=25&offset=50")

    assert response.status_code == 200
    assert response.get_json() == ["line 1\n"]
    assert captured == {"limit": 25, "offset": 50}


def test_get_logs_clamps_invalid_query_params(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(routes.logs_bp, url_prefix="/api")
    captured = {}

    def fake_read_logs(limit, offset):
        captured["limit"] = limit
        captured["offset"] = offset
        return []

    monkeypatch.setattr(routes, "read_logs", fake_read_logs)

    response = app.test_client().get("/api/logs?limit=bad&offset=-5")

    assert response.status_code == 200
    assert captured == {"limit": routes.DEFAULT_LOG_LIMIT, "offset": 0}
