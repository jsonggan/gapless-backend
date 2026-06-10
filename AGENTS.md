# Gapless Backend — Agent Guide

## Project Overview

Gapless Backend is an API service built with **FastAPI**, **SQLAlchemy (async)**, **Alembic**, and **PostgreSQL**. It provides AI-generated, depth-calibrated learning paths for technical professionals.

## Tech Stack

| Layer            | Technology                           |
| ---------------- | ------------------------------------ |
| Framework        | FastAPI (async)                      |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic             |
| Database         | PostgreSQL (psycopg v3 async)        |
| Auth             | JWT (python-jose) + bcrypt (passlib) |
| Settings         | Pydantic Settings                    |
| Logging          | structlog                            |
| Testing          | pytest + pytest-asyncio + httpx      |
| Lint/Format      | Ruff                                 |
| Type Check       | mypy                                 |
| Package Mgr      | uv                                   |
| Containers       | Docker + Docker Compose              |

## Project Structure

```
gapless-backend/
├── app/                       # Main application code
│   ├── api/                   # API layer
│   │   ├── deps.py            # FastAPI dependencies (DB session, auth)
│   │   └── v1/                # API version 1
│   │       ├── api.py         # Router aggregation
│   │       └── endpoints/     # Route handlers (users, auth, etc.)
│   ├── core/                  # Core utilities
│   │   ├── config.py          # Pydantic settings (.env driven)
│   │   ├── security.py        # Password hashing & JWT helpers
│   │   └── logging.py         # structlog configuration
│   ├── crud/                  # CRUD operations per model
│   ├── db/                    # Database layer
│   │   ├── base.py            # SQLAlchemy Base, mixins
│   │   └── session.py         # Async engine & session factory
│   ├── models/                # SQLAlchemy ORM models
│   ├── schemas/               # Pydantic request/response models
│   ├── tests/                 # Test suite
│   │   ├── conftest.py        # Shared pytest fixtures
│   │   └── test_*.py          # Test modules
│   └── main.py                # FastAPI app factory & entry point
├── alembic/                   # Database migrations
│   ├── versions/              # Migration revision files
│   ├── env.py                 # Alembic environment
│   └── script.py.mako         # Migration script template
├── .github/workflows/ci.yml   # GitHub Actions CI
├── pyproject.toml             # Project metadata, deps, tool configs
├── alembic.ini                # Alembic configuration
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml         # Local orchestration (API + Postgres)
├── .dockerignore              # Docker build exclusions
├── .env                       # Local environment variables
├── .env.example               # Environment variable template
├── AGENTS.md                  # Agent guidelines
└── README.md                  # Human-facing documentation
```

## Coding Conventions

- **Python**: 3.11+ with modern typing (`list[str]`, `str | None`, etc.)
- **Async first**: All I/O (DB, HTTP) uses `async`/`await`
- **Ruff**: Enforced linting and formatting (`uv run ruff check .`, `uv run ruff format .`)
- **mypy**: Strict type checking (`uv run mypy app`)
- **Imports**: Use absolute imports within `app/`; Ruff handles sorting
- **Models**: All SQLAlchemy models inherit from `Base` and use `Mapped[]` + `mapped_column()`
- **Schemas**: Pydantic v2; use `ConfigDict(from_attributes=True)` for ORM-compatible schemas

## Common Commands

Run everything through `uv`:

```bash
# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Start development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run pre-commit hooks manually
uv run pre-commit run --all-files

# Lint & format
uv run ruff check app
uv run ruff check --fix app
uv run ruff format app

# Type check
uv run mypy app

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1
```

### Docker

```bash
# Start everything (API + PostgreSQL)
docker compose up --build

# Run migrations inside container
docker compose exec api alembic upgrade head

# Run tests inside container
docker compose exec api pytest

# Stop everything
docker compose down

# Stop and remove volumes
docker compose down -v
```

## Testing Guidelines

- Tests live in `app/tests/`
- Use `pytest-asyncio` for async tests; mark with `@pytest.mark.asyncio`
- Use the `client` fixture from `conftest.py` for API calls
- Use the `db` fixture for direct database operations
- Tests run against a separate `test_gapless` database automatically

## Adding a New Feature

Typical flow:

1. **Model** → `app/models/<name>.py`
2. **Schema** → `app/schemas/<name>.py`
3. **CRUD** → `app/crud/<name>.py`
4. **Endpoint** → `app/api/v1/endpoints/<name>.py`
5. **Wire router** → `app/api/v1/api.py`
6. **Migration** → `uv run alembic revision --autogenerate -m "add <name>"`
7. **Tests** → `app/tests/test_<name>.py`

## Important Notes

- When modifying DB structure, use Alembic via `uv run alembic ...` and include a migration file.
- Keep business logic out of endpoints — delegate to CRUD / services
- Maintain >= 80% test coverage (enforced in CI)
