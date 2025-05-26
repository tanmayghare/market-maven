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

# Database operations
db-migrate:
	python -m market_maven.cli db migrate

db-seed:
	python -m market_maven.cli db seed

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

# Database operations
db-init:
	python -c "from market_maven.core.database import create_tables; import asyncio; asyncio.run(create_tables())"

db-reset:
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
	@echo "  make docker-run     # Run with Docker"
	@echo "  make coverage       # Run tests with coverage"
	@echo "  make perf-test      # Run performance tests" 