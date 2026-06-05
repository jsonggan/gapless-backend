# gapless-backend

Learn exactly what you don't know. AI-generated, depth-calibrated learning paths for technical professionals.

## Project Structure

```
gapless-backend/
├── app/                       # Main application code
│   ├── api/                   # API layer (routes, dependencies)
│   │   └── v1/                # API version 1 endpoints
│   ├── core/                  # Core utilities (config, security, logging)
│   ├── crud/                  # Database CRUD operations
│   ├── db/                    # SQLAlchemy base, session, engine
│   ├── models/                # SQLAlchemy ORM models
│   ├── schemas/               # Pydantic request/response schemas
│   ├── tests/                 # pytest test suite
│   └── main.py                # FastAPI application entry point
├── alembic/                   # Database migration scripts
├── .github/workflows/         # CI/CD pipelines
├── pyproject.toml             # Dependencies & tool configuration
├── alembic.ini                # Alembic configuration
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml         # Local orchestration (API + Postgres)
├── .dockerignore              # Docker build exclusions
├── .env / .env.example        # Environment variables
└── AGENTS.md                  # AI agent guidelines & conventions
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 14+ (or Docker for containerized development)

### Installation

```bash
# Clone and enter the repo
cd gapless-backend

# Install dependencies
uv sync --all-extras

# Copy environment variables
cp .env.example .env
# Edit .env with your local database credentials

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload
```

The API will be available at [http://localhost:8000](http://localhost:8000).

### Docker Quick Start

If you prefer Docker, you can spin up the entire stack (API + PostgreSQL) without installing Python or Postgres locally:

```bash
# Start everything with hot-reload enabled
docker compose up --build

# The API will be available at http://localhost:8000
# Postgres will be exposed on port 5432

# Run tests inside the container
docker compose exec api pytest

# Run migrations manually
docker compose exec api alembic upgrade head

# Stop everything
docker compose down

# Stop and remove volumes (wipes database data)
docker compose down -v
```

### Interactive Docs

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Development

### Running Tests

```bash
uv run pytest
```

### Linting & Formatting

```bash
uv run ruff check app
uv run ruff check --fix app
uv run ruff format app
```

### Type Checking

```bash
uv run mypy app
```

### Database Migrations

```bash
# Generate a new migration
uv run alembic revision --autogenerate -m "add users table"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```

## Tech Stack

- **FastAPI** — Modern, fast web framework
- **SQLAlchemy 2.0** — Async ORM
- **Alembic** — Database migrations
- **PostgreSQL** — Primary database
- **Pydantic** — Data validation & settings
- **pytest** — Testing framework
- **Ruff** — Lightning-fast linter & formatter
- **Docker** — Containerization for local development and deployment
- **structlog** — Structured logging

## License

MIT
