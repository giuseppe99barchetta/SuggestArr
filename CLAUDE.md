# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SuggestArr automates media content recommendations and download requests for media servers (Jellyfin, Plex, Emby). It retrieves recently watched content, finds similar titles via TMDb API, and sends automated requests to Jellyseer/Overseerr.

This is a **Flask + Vue 3** full-stack application with a Python backend and a Vue 3 frontend.

## Architecture

### Backend (Python/Flask)

The backend follows a **modular blueprint pattern**:

- **`api_service/app.py`**: Flask application factory with blueprint registration
- **`api_service/automate_process.py`**: `ContentAutomation` class orchestrates the main automation workflow
- **`api_service/blueprints/`**: Flask blueprints for API routes organized by domain:
  - `automation/` - Force run and automation control
  - `config/` - Configuration management
  - `jellyfin/` - Jellyfin/Emby API endpoints
  - `plex/` - Plex API endpoints
  - `seer/` - Jellyseer/Overseerr API endpoints
  - `logs/` - Application logs access
- **`api_service/services/`**: External API clients (Jellyfin, Plex, TMDb, Jellyseer/Overseerr)
- **`api_service/handler/`**: Business logic handlers (`jellyfin_handler.py`, `plex_handler.py`) that coordinate between services
- **`api_service/db/`**: Database layer with support for SQLite, PostgreSQL, and MySQL/MariaDB
- **`api_service/config/`**: Configuration management, cron jobs (APScheduler), and logger
- **`api_service/utils/`**: Shared utilities
- **`api_service/exceptions/`**: Custom exception classes

### Frontend (Vue 3)

- **`client/src/`**: Vue 3 application with Vue Router
- **`client/src/components/`**: Vue components including ConfigWizard, LogsComponent, RequestsPage
- Build output goes to `client/dist/` → copied to `static/` for Flask to serve

### Configuration

All configuration is stored in YAML format:
- **`config/config_files/config.yaml`**: Main configuration file (created at runtime if missing)
- Configuration is loaded via `api_service/config/config.py`
- Database file (if using SQLite): `config/config_files/requests.db`

### Automation Flow

1. **Cron Job**: APScheduler triggers automation based on `CRON_TIMES` config
2. **ContentAutomation**: Factory pattern async initialization
3. **Media Handlers**: `JellyfinHandler` or `PlexHandler` process recent items
4. **TMDb Search**: Find similar content based on watch history
5. **Jellyseer Request**: Submit filtered requests to Jellyseer/Overseerr

## Development Commands

### Backend (Python)

```bash
# Install dependencies
cd api_service
pip install -r requirements.txt
pip install -r requirements.dev.txt  # For testing

# Run Flask app directly (development)
python -m api_service.app

# Run with uvicorn (production-like)
cd ..  # Back to project root
uvicorn api_service.app:asgi_app --host 0.0.0.0 --port 5000

# Run tests
cd api_service
pytest
pytest api_service/test/test_config.py  # Run specific test file
```

### Frontend (Vue)

```bash
cd client

# Install dependencies
npm install

# Development server with hot reload
npm run serve

# Build for production
npm run build

# Lint
npm run lint
```

### Docker

```bash
# Build development image
docker build . -f ./docker/Dockerfile --target dev --tag suggestarr:nightly

# Build production image
docker build . -f ./docker/Dockerfile --tag suggestarr:latest

# Run with docker-compose
docker-compose up
```

## Key Configuration Variables

Configuration is managed through `config/config_files/config.yaml`:

- **Media Server**: `SELECTED_SERVICE` (jellyfin/plex/emby), API URLs and tokens
- **TMDb**: `TMDB_API_KEY` for content discovery
- **Jellyseer/Overseerr**: `SEER_API_URL`, `SEER_TOKEN`, optional user credentials
- **Automation**: `CRON_TIMES` (cron expression), `MAX_CONTENT_CHECKS`, `MAX_SIMILAR_MOVIE`, `MAX_SIMILAR_TV`
- **Database**: `DB_TYPE` (sqlite/postgres/mysql/mariadb) with connection params
- **Filtering**: TMDB thresholds, genre exclusions, streaming service filters, language filters

## Testing Strategy

- Tests are in `api_service/test/`
- `conftest.py` sets up pytest fixtures
- Run tests before committing changes: `cd api_service && pytest`

## Important Notes

- The Flask app serves the built Vue frontend from `static/` directory
- The app uses ASGI via `WsgiToAsgi` wrapper for async support (required for async clients)
- Cron jobs are managed by APScheduler, configured at startup if `CRON_TIMES` is set
- Database manager supports multiple backends via `DB_TYPE` environment variable
- Handlers use async/await pattern extensively - ensure to use `await` when calling service methods
- Port defaults to 5000 but can be customized via `SUGGESTARR_PORT` environment variable
