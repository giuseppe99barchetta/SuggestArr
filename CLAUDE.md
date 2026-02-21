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

## Architecture Notes
- Backend: Flask-based API with RESTful endpoints in blueprints/
- Frontend: Vue.js 3 with component-based architecture
- Testing: pytest for backend, unit tests with detailed assertions
- Documentation: Include docstrings for all functions/classes
