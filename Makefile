# nwvault-legacy - Aegis Stack Project
# Developer-friendly commands for Docker workflow

COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

#=============================================================================
# CORE DOCKER COMMANDS
#=============================================================================

build: ## Build Docker image
	@echo "Building Docker image..."
	@$(COMPOSE_DEV) build webserver

serve: build ## Run all services (builds if needed)
	@echo "Starting services... (Press Ctrl+C to stop)"
	@$(COMPOSE_DEV) --profile dev up --remove-orphans

serve-bg: ## Run all services in background
	@echo "Starting services in background..."
	@$(COMPOSE_DEV) --profile dev up -d --remove-orphans

stop: ## Gracefully stop all services
	@echo "Stopping services..."
	@$(COMPOSE_DEV) --profile dev down --remove-orphans

clean: ## Clean up project containers, networks, volumes, and images
	@echo "Cleaning up project Docker resources..."
	@$(COMPOSE_DEV) down --remove-orphans --volumes --rmi all 2>/dev/null || true

#=============================================================================
# DEVELOPER WORKFLOW COMMANDS (the ones you'll actually use)
#=============================================================================

rebuild: build serve ## Build images and start services

refresh: clean build serve ## Nuclear reset - clean everything and rebuild

restart: stop serve ## Quick restart (no rebuild)

#=============================================================================
# DEBUGGING AND LOGS
#=============================================================================

logs: ## Follow logs from all services
	@echo "Following all service logs..."
	@docker compose logs -f

logs-web: ## Follow webserver logs only
	@echo "Following webserver logs..."
	@docker compose logs -f webserver

logs-worker: ## Follow worker logs only
	@echo "Following worker logs..."
	@docker compose logs -f worker-system worker-load-test

logs-redis: ## Follow Redis logs only
	@echo "Following Redis logs..."
	@docker compose logs -f redis

shell: ## Open shell in webserver container
	@echo "Opening shell in webserver container..."
	@docker compose exec webserver /bin/bash

shell-worker: ## Open shell in worker container
	@echo "Opening shell in worker container..."
	@docker compose exec worker-system /bin/bash

ps: ## Show running containers
	@echo "Docker containers status:"
	@docker compose ps

#=============================================================================
# REDIS DEBUGGING
#=============================================================================

redis-cli: ## Connect to Redis CLI
	@echo "Connecting to Redis CLI..."
	@docker compose exec redis redis-cli

redis-stats: ## Show Redis memory and stats
	@echo "Redis statistics:"
	@docker compose exec redis redis-cli info memory

redis-keys: ## Show all Redis keys
	@echo "Redis keys:"
	@docker compose exec redis redis-cli keys "*"

redis-reset: ## Clear all Redis data
	@echo "Clearing all Redis data..."
	@docker compose exec redis redis-cli flushall

#=============================================================================
# HEALTH AND TESTING
#=============================================================================

health: ## Check system health status
	@echo "Checking system health..."
	@uv run nwvault-legacy health status

health-detailed: ## Detailed system health information
	@echo "Detailed system health..."
	@uv run nwvault-legacy health status --detailed

health-json: ## System health as JSON
	@uv run nwvault-legacy health status --json

health-probe: ## Health probe (exits 1 if unhealthy)
	@uv run nwvault-legacy health probe

test: ## Run tests locally
	@echo "Running tests..."
	@uv run pytest

test-verbose: ## Run tests with verbose output
	@echo "Running tests (verbose)..."
	@uv run pytest -v

#=============================================================================
# CODE QUALITY (local development tools)
#=============================================================================

lint: ## Check code style with ruff
	@echo "Running linting..."
	@uv run ruff check .

fix: ## Auto-fix linting and formatting issues
	@echo "Auto-fixing code issues..."
	@uv run ruff check . --fix
	@uv run ruff format .

format: ## Format code with ruff
	@echo "Formatting code..."
	@uv run ruff format .

typecheck: ## Run type checking with ty
	@echo "Running type checking..."
	@uv run ty check

check: lint typecheck test ## Run all code quality checks
	@echo "All checks completed successfully!"

#=============================================================================
# PROJECT MANAGEMENT
#=============================================================================

install: ## Install/sync dependencies with uv
	@echo "Installing dependencies..."
	@uv sync --all-extras

deps-update: ## Update dependencies
	@echo "Updating dependencies..."
	@uv sync --upgrade

clean-cache: ## Clean Python cache files
	@echo "Cleaning Python cache files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

#=============================================================================
# DOCUMENTATION
#=============================================================================

docs-serve: ## Serve documentation locally (http://localhost:8001)
	@echo "Serving documentation on http://localhost:8001"
	@uv run mkdocs serve --dev-addr 0.0.0.0:8001

docs-build: ## Build static documentation
	@echo "Building documentation..."
	@uv run mkdocs build

#=============================================================================
# DATABASE MIGRATIONS
#=============================================================================

migrate: ## Apply database migrations
	@echo "Applying database migrations..."
	@docker compose exec webserver uv run alembic -c alembic/alembic.ini upgrade head

migrate-check: ## Check migration status
	@echo "Checking migration status..."
	@docker compose exec webserver uv run alembic -c alembic/alembic.ini current

migrate-history: ## Show migration history
	@echo "Migration history:"
	@docker compose exec webserver uv run alembic -c alembic/alembic.ini history --verbose

migrate-fix: ## Auto-fix schema mismatches after upgrade (safe: only adds, never drops)
	@echo "Checking for schema mismatches..."
	@docker compose exec webserver uv run python -m app.cli.migrate_fix
	@echo "Applying fix migration..."
	@docker compose exec webserver uv run alembic -c alembic/alembic.ini upgrade head
	@echo "Schema fix complete"

migrate-reset: ## Reset database (WARNING: destructive)
	@echo "WARNING: This will destroy all data in the database!"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@docker compose exec webserver uv run alembic -c alembic/alembic.ini downgrade base
	@docker compose exec webserver uv run alembic -c alembic/alembic.ini upgrade head
	@echo "Database reset complete"




#=============================================================================
# WORKER DEBUGGING (arq)
#=============================================================================

worker-test: ## Test workers in burst mode (process and exit)
	@echo "Testing system worker in burst mode..."
	@uv run python -m arq app.components.worker.queues.system.WorkerSettings --burst

#=============================================================================
# HELP AND INFO
#=============================================================================

status: ## Show current system status
	@echo "Current system status:"
	@echo
	@echo "Docker containers:"
	@docker compose ps || echo "No containers running"
	@echo
	@echo "Dependencies:"
	@uv pip list | head -20 || echo "Dependencies not installed"

help: ## Show this help message
	@echo "nwvault-legacy development commands:"
	@echo
	@echo "WORKFLOW COMMANDS (start here):"
	@echo "  make refresh      - Nuclear reset (clean + build + serve)"
	@echo "  make rebuild      - Build and serve"
	@echo "  make restart      - Quick restart"
	@echo
	@echo "CORE COMMANDS:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "TIP: Use 'make refresh' when everything is broken!"

.PHONY: build serve stop clean rebuild refresh restart logs logs-web logs-worker logs-redis shell shell-worker ps redis-cli redis-stats redis-keys redis-reset health health-detailed health-json health-probe test test-verbose lint fix format typecheck check install deps-update clean-cache docs-serve docs-build migrate migrate-check migrate-history migrate-reset worker-test status help

# Default target - show help
.DEFAULT_GOAL := help
