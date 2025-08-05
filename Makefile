# Market Maven - Simplified Makefile for MVP

.PHONY: help install run test clean db-init db-reset api demo

# Default target
help:
	@echo "Market Maven - Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make run        - Run CLI health check"
	@echo "  make api        - Start API server"
	@echo "  make demo       - Run the demo script"
	@echo "  make db-init    - Initialize database"
	@echo "  make db-reset   - Reset database"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Clean up cache and temp files"

# Install dependencies
install:
	pip install -r requirements.txt

# Run CLI health check
run:
	python -m market_maven.cli health

# Start API server
api:
	uvicorn market_maven.api.main:app --reload --host 0.0.0.0 --port 8000

# Run demo
demo:
	python demo.py

# Database commands
db-init:
	python -m market_maven.cli database init

db-reset:
	python -m market_maven.cli database reset --force

# Run tests
test:
	pytest tests/unit -v

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov