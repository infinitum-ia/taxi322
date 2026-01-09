# Repository Guidelines

## Project Structure & Module Organization
- The FastAPI entrypoint is `app/main.py`, which wires the LangGraph agent graph, routes, and shared state for taxi dispatch.
- `app/agents/` keeps the sequential taxi graph plus helpers, `app/models/`, `app/tools/`, `app/services/`, and `app/api/` organize domain models, utilities, orchestration, and REST endpoints.
- Configuration and LLM wiring live in `app/core/`, while logs, data snapshots, and helper scripts stay in `logs/` and the repo root (e.g., `test_taxi_flow.py`).
- Tests sit under `tests/` and the handful of root-level `test_*.py` files that exercise specific flows; dependency files (`requirements*.txt`, `pyproject.toml`) describe runtime and dev tooling.
- Keep `.env` local and follow `.env.example` if you need to replicate the setup.

## Build, Test, and Development Commands
- `uv venv` - create the project-specific virtual environment that other `uv` commands re-use.
- `uv pip install -r requirements.txt` (or `requirements-dev.txt`) - installs production and development dependencies.
- `cp .env.example .env` and set `OPENAI_API_KEY` (plus optional `LLM_MODEL`, `CHECKPOINTER_TYPE`, `DEBUG`) before launching the API.
- `uv run uvicorn app.main:app --reload` - dev server with Swagger/Redoc at `http://localhost:8000`.
- `uv run pytest` - executes every test under `tests/` plus the root helper scripts.
- `uv run black app/ tests/` and `uv run ruff check app/ tests/` - formatting and linting gates before commits.

## Coding Style & Naming Conventions
- Stick to Python conventions: 4-space indentation, `snake_case` for functions/modules, `PascalCase` for Pydantic models, and descriptive identifiers tied to the taxi domain (e.g., `taxi_state`, `zone_tools`).
- Formatting is centralized in Black and Ruff; run them locally (`uv run black ...`, `uv run ruff ...`) and fix warnings before pushing.
- Tests, helpers, and scripts should use clear `test_` prefixes so pytest discovers them automatically.

## Testing Guidelines
- Pytest is the primary framework; place new tests in `tests/` or the purposeful root scripts, always starting filenames with `test_`.
- Focus coverage on the four specialized agents, address parsing, and dispatch helpers that mirror the conversational workflows described in the README.
- Run `uv run pytest` (and rerun after changing business logic) before opening PRs.

## Commit & Pull Request Guidelines
- Follow the conventional commit prefixes already in history (`feat:`, `fix:`, `docs:`, etc.) and keep messages action-oriented.
- PRs should include a concise description, linked issue or context, a checklist of commands/tests you executed, and screenshots or logs only when necessary to demonstrate UI/API changes.

## Security & Configuration Tips
- Never commit `.env`; share only `.env.example` and keep API keys out of git history.
- Optional toggles such as `ZONE_VALIDATION_STRICT` or `DISPATCH_API_URL` live in README notes; mirror them in staging or CI before enabling.
