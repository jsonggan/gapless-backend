.DEFAULT_GOAL := help

# Use bash for recipes where available; harmless on most setups.
SHELL := /bin/sh

UV ?= uv
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: help install dev run services services-down up down logs migrate revision \
        lint format format-check typecheck test test-cov check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (incl. dev) and pre-commit hooks
	$(UV) sync --extra dev
	$(UV) run pre-commit install

services: ## Start Postgres + Redis in the background
	docker compose up -d db redis

services-down: ## Stop Postgres + Redis
	docker compose stop db redis

migrate: ## Apply database migrations
	$(UV) run alembic upgrade head

revision: ## Create a new migration: make revision m="message"
	$(UV) run alembic revision --autogenerate -m "$(m)"

dev: services migrate ## Start dependencies, migrate, then run the API with auto-reload
	$(UV) run uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

run: ## Run the API without auto-reload (no service/migration setup)
	$(UV) run uvicorn app.main:app --host $(HOST) --port $(PORT)

up: ## Run the full stack (api + db + redis) via docker compose
	docker compose up

down: ## Stop and remove all docker compose containers
	docker compose down

logs: ## Tail docker compose logs
	docker compose logs -f

lint: ## Lint with ruff
	$(UV) run ruff check app

format: ## Auto-format and fix lint issues
	$(UV) run ruff format app
	$(UV) run ruff check --fix app

format-check: ## Check formatting without writing changes
	$(UV) run ruff format --check app

typecheck: ## Type-check with mypy
	$(UV) run mypy app

test: ## Run the test suite
	$(UV) run pytest

test-cov: ## Run tests with an HTML coverage report
	$(UV) run pytest --cov-report=html

check: lint typecheck test ## Run lint, typecheck, and tests

clean: ## Remove caches and coverage artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
