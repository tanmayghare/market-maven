# MarketMaven - Production-grade AI Market Intelligence Agent
# Makefile for development, testing, and deployment

.PHONY: help install install-dev setup clean test lint format security docker-build docker-run docker-stop

# Default target
help:
	@echo "MarketMaven - AI Market Intelligence Agent"
	@echo ""
	@echo "Available commands:"
	@echo "  install      Install production dependencies"
	@echo "  install-dev  Install development dependencies"
	@echo "  setup        Set up development environment"
	@echo "  clean        Clean up build artifacts and cache"
	@echo "  test         Run all tests"
	@echo "  lint         Run linting checks"
	@echo "  format       Format code with black and isort"
	@echo "  security     Run security checks"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run with Docker Compose"
	@echo "  docker-stop  Stop Docker services"

# Installation targets
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -e ".[dev]"

setup: install-dev
	pre-commit install
	mkdir -p logs data
	cp env.example .env
	@echo "Development environment set up!"
	@echo "Please edit .env with your API keys"

# Cleaning
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/

# Testing
test:
	pytest tests/ -v --cov=market_maven --cov-report=html --cov-report=term

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-performance:
	pytest tests/performance/ -v

# Code quality
lint:
	black --check market_maven tests
	isort --check-only market_maven tests
	mypy market_maven --ignore-missing-imports
	flake8 market_maven tests

format:
	black market_maven tests
	isort market_maven tests

security:
	bandit -r market_maven
	safety check

# Docker operations
docker-build:
	docker build -t market-maven:latest .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f market-maven

# Development commands
dev-run:
	python -m market_maven.cli interactive

dev-analyze:
	python -m market_maven.cli analyze AAPL

dev-health:
	python -m market_maven.cli health

# Production commands
prod-deploy:
	docker-compose -f docker-compose.prod.yml up -d

prod-logs:
	docker-compose -f docker-compose.prod.yml logs -f

prod-stop:
	docker-compose -f docker-compose.prod.yml down

# Monitoring
monitor-start:
	docker-compose up -d prometheus grafana

monitor-stop:
	docker-compose stop prometheus grafana

# Database operations (new enhanced commands)
db-init:
	python -m market_maven.cli database init

db-init-force:
	python -m market_maven.cli database init --force

db-reset:
	python -m market_maven.cli database reset

db-status:
	python -m market_maven.cli database status

db-cleanup:
	python -m market_maven.cli database cleanup

db-cleanup-90d:
	python -m market_maven.cli database cleanup --days 90

# Alembic migrations
db-migrate-create:
	alembic revision --autogenerate -m "$(MSG)"

db-migrate-up:
	alembic upgrade head

db-migrate-down:
	alembic downgrade -1

db-migrate-history:
	alembic history

db-migrate-current:
	alembic current

# Backup and restore
backup:
	docker-compose exec postgres pg_dump -U marketmaven marketmaven > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore:
	@read -p "Enter backup file name: " backup_file; \
	docker-compose exec -T postgres psql -U marketmaven marketmaven < $$backup_file

# CI/CD simulation
ci-test: clean lint security test

ci-build: ci-test docker-build

ci-deploy: ci-build
	@echo "Deployment simulation complete"

# Performance testing
perf-test:
	python -m pytest tests/performance/ -v --benchmark-only

# Load testing
load-test:
	locust -f tests/load/locustfile.py --host=http://localhost:8000

# Code coverage
coverage:
	pytest tests/ --cov=market_maven --cov-report=html --cov-report=term --cov-report=xml

# Type checking
typecheck:
	mypy market_maven --strict

# Documentation
docs-build:
	sphinx-build -b html docs/ docs/_build/

docs-serve:
	python -m http.server 8080 -d docs/_build/

# API Server operations
api-start:
	python -m market_maven.api.main

api-dev:
	uvicorn market_maven.api.main:app --reload --host 0.0.0.0 --port 8000

api-docs:
	@echo "API documentation available at:"
	@echo "  - Swagger UI: http://localhost:8000/docs"
	@echo "  - ReDoc: http://localhost:8000/redoc"
	@echo "  - OpenAPI JSON: http://localhost:8000/openapi.json"

# Trading operations
trade-test:
	python -m tests.integration.test_ibapi_integration

trade-dry-run:
	python -m market_maven.cli trade AAPL BUY 10 --dry-run

# Legacy database operations (use new db-* commands instead)
db-legacy-init:
	python -c "from market_maven.core.database import create_tables; import asyncio; asyncio.run(create_tables())"

db-legacy-reset:
	python -c "from market_maven.core.database import drop_tables, create_tables; import asyncio; asyncio.run(drop_tables()); asyncio.run(create_tables())"

# Cache operations
cache-clear:
	python -c "from market_maven.core.cache import cache_manager; import asyncio; asyncio.run(cache_manager.redis_cache.clear_pattern('*'))"

cache-stats:
	python -c "from market_maven.core.cache import cache_manager; import asyncio; print(asyncio.run(cache_manager.redis_cache.get_stats()))"

# Quick start for new developers
quickstart: setup db-init
	@echo "Running quick health check..."
	python -m market_maven.cli health
	@echo ""
	@echo "MarketMaven is ready! Try these commands:"
	@echo "  make dev-analyze    # Analyze a stock"
	@echo "  make dev-run        # Start interactive mode"
	@echo "  make api-dev        # Start API server in dev mode"
	@echo "  make trade-test     # Test IBAPI integration"
	@echo "  make db-status      # Check database status"
	@echo "  make docker-run     # Run with Docker"
	@echo "  make coverage       # Run tests with coverage"

# All-in-one development setup
dev-setup: setup db-init
	@echo "🚀 Starting complete development environment..."
	@echo "1. Database initialized"
	@echo "2. Starting API server in development mode..."
	make api-dev &
	@echo "3. API server starting at http://localhost:8000"
	@echo "4. API docs available at http://localhost:8000/docs"
	@echo ""
	@echo "✅ Development environment ready!"

# Production setup validation
prod-check:
	@echo "🔍 Running production readiness checks..."
	make lint
	make security
	make test
	make db-status
	@echo "✅ Production checks complete!"

# Enhanced help with new commands
help-enhanced:
	@echo "MarketMaven - AI Market Intelligence Agent"
	@echo "=========================================="
	@echo ""
	@echo "🏗️  Setup Commands:"
	@echo "  setup           Set up development environment"
	@echo "  quickstart      Quick setup with database"
	@echo "  dev-setup       Complete development environment"
	@echo ""
	@echo "🗄️  Database Commands:"
	@echo "  db-init         Initialize database with tables and data"
	@echo "  db-status       Check database health and status"
	@echo "  db-reset        Reset database (DANGER: deletes all data)"
	@echo "  db-cleanup      Clean up old data (30 days)"
	@echo "  db-migrate-*    Alembic migration commands"
	@echo ""
	@echo "🌐 API Commands:"
	@echo "  api-dev         Start API server in development mode"
	@echo "  api-start       Start API server in production mode"
	@echo "  api-docs        Show API documentation URLs"
	@echo ""
	@echo "💼 Trading Commands:"
	@echo "  trade-test      Test Interactive Brokers integration"
	@echo "  trade-dry-run   Execute a dry-run trade"
	@echo ""
	@echo "🧪 Development Commands:"
	@echo "  dev-analyze     Analyze a stock (AAPL)"
	@echo "  dev-run         Start interactive CLI mode"
	@echo "  dev-health      Check system health"
	@echo ""
	@echo "🔍 Quality Assurance:"
	@echo "  test           Run all tests"
	@echo "  lint           Run code quality checks"
	@echo "  security       Run security scans"
	@echo "  coverage       Run tests with coverage report"
	@echo ""
	@echo "🐳 Docker Commands:"
	@echo "  docker-build   Build Docker image"
	@echo "  docker-run     Run with Docker Compose"
	@echo "  docker-stop    Stop Docker services"
	@echo ""
	@echo "📊 Monitoring:"
	@echo "  monitor-start  Start Prometheus/Grafana"
	@echo "  prod-check     Run production readiness checks" 