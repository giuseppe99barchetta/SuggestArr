# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands
- Backend Docker: `docker build . -f ./docker/Dockerfile --target dev --tag suggestarr:nightly`
- Frontend serve (dev): `cd client && npm run serve`
- Frontend build: `cd client && npm run build --skip-plugins @vue/cli-plugin-eslint`
- Frontend lint: `cd client && npm run lint`
- Backend tests: `cd api_service && python -m pytest`
- Single test: `cd api_service && python -m pytest test/test_file.py::TestClass::test_function -v`
- Local Flask: `cd api_service && python app.py` (defaults to port 5000, set SUGGESTARR_PORT to override)

## Code Style Guidelines
- Python: PEP 8, snake_case for functions/variables, PascalCase for classes
- Vue: ESLint with Vue3-essential and ESLint recommended configs
- JavaScript: camelCase for variables/functions, PascalCase for components
- Docstrings: Required for all Python functions/classes with detailed param/return descriptions
- Logging: Use `logger = LoggerManager.get_logger(__name__)` pattern (not print statements)
- Error handling: Use custom exceptions from `api_service/exceptions/` directory

## Architecture Overview

### Backend (Flask + Python)
- **Entry point**: [api_service/app.py](api_service/app.py) - App factory pattern with blueprint registration
- **Blueprints**: RESTful API endpoints organized by service under [api_service/blueprints/](api_service/blueprints/)
  - `jellyfin/`, `plex/`, `seer/`, `tmdb/`, `automation/`, `logs/`, `config/`
- **Services**: External API client implementations in [api_service/services/](api_service/services/)
  - `JellyfinClient`, `PlexClient`, `SeerClient`, `TMDbClient` - handle HTTP communication with external services
- **Handlers**: Business logic layer in [api_service/handler/](api_service/handler/)
  - `JellyfinHandler`, `PlexHandler` - orchestrate between services and blueprints
- **Database**: Database abstraction layer in [api_service/db/](api_service/db/)
  - `database_manager.py` - Main database interface
  - `connection_pool.py` - Connection pooling for PostgreSQL/MySQL
  - `adapters/` - Database-specific adapters (SQLite, PostgreSQL, MySQL)
  - `adapter_factory.py` - Factory pattern for adapter selection
- **Automation**: [api_service/automate_process.py](api_service/automate_process.py)
  - `ContentAutomation` class - Core automation workflow that retrieves recently watched content, finds similar titles via TMDb, and submits requests to Jellyseer/Overseer
- **Configuration**: [api_service/config/](api_service/config/)
  - `config.py` - Environment variable loading
  - `logger_manager.py` - Centralized logging configuration
  - `cron_jobs.py` - APScheduler cron job management

### Frontend (Vue.js 3)
- **Entry point**: [client/src/main.js](client/src/main.js)
- **Router**: [client/src/router/index.js](client/src/router/index.js) - Vue Router configuration
- **Components**: [client/src/components/](client/src/components/) - Reusable Vue components
- **API layer**: [client/src/api/](client/src/api/) - Axios-based API clients
- **Stores**: [client/src/stores/](client/src/stores/) - State management (if using Pinia/Vuex)
- **Build output**: [static/](static/) - Compiled frontend served by Flask

### Key Design Patterns
- **App Factory**: Flask app created via `create_app()` for testability
- **Blueprint Pattern**: Modular route organization by domain
- **Service Layer**: External API clients separated from business logic
- **Handler Layer**: Business logic separated from routing
- **Database Adapter Pattern**: Abstraction for multiple database backends
- **Async Factory**: `ContentAutomation.create()` for async initialization

### Database Support
- SQLite (default): No external dependencies, single file
- PostgreSQL: Connection pooling via `connection_pool.py`
- MySQL: Connection pooling via `connection_pool.py`
- Configuration: Set via environment variables in `config_files/`

### Environment Configuration
- Config files stored in `config/config_files/` (gitignored)
- Loaded via `load_env_vars()` in [api_service/config/config.py](api_service/config/config.py)
- Key vars: `SELECTED_SERVICE`, `TMDB_API_KEY`, `CRON_TIMES`, `LOG_LEVEL`, `SUGGESTARR_PORT`

### Testing
- Framework: pytest
- Test location: [api_service/test/](api_service/test/)
- Test structure: `test_*.py` files with detailed assertions
- Fixtures: Defined in [api_service/conftest.py](api_service/conftest.py)
