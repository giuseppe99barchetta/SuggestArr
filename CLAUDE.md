# SuggestArr Development Guide

## Build & Run Commands
- Backend: `docker build . -f ./docker/Dockerfile --target dev --tag suggestarr:nightly`
- Frontend serve: `cd client && npm run serve`
- Frontend build: `cd client && npm run build --skip-plugins @vue/cli-plugin-eslint`
- Frontend lint: `cd client && npm run lint`
- Run tests: `cd api_service && python -m pytest`
- Run single test: `cd api_service && python -m pytest test/test_file.py::TestClass::test_function -v`

## Code Style Guidelines
- Python: PEP 8, docstrings with detailed param/return descriptions
- Vue: ESLint with Vue3-essential and ESLint recommended configs
- Python naming: snake_case for functions/variables, PascalCase for classes
- JavaScript naming: camelCase for variables/functions, PascalCase for components
- Error handling: Use custom exceptions from exceptions/ directory
- Logging: Use `logger = LoggerManager.get_logger(__name__)` pattern

## Architecture Notes
- Backend: Flask-based API with RESTful endpoints in blueprints/
- Frontend: Vue.js 3 with component-based architecture
- Testing: pytest for backend, unit tests with detailed assertions
- Documentation: Include docstrings for all functions/classes
