.PHONY: help test test-unit test-integration test-coverage test-watch build up down logs clean

help:
	@echo "Device Manager Backend - Testing Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make test              - Run all tests"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests only"
	@echo "  make test-coverage     - Run tests with coverage report"
	@echo "  make build             - Build Docker images"
	@echo "  make up                - Start all services (db, backend)"
	@echo "  make down              - Stop all services"
	@echo "  make logs              - View service logs"
	@echo "  make clean             - Clean up containers and volumes"

test:
	@docker-compose run --rm test pytest tests/ -v

test-unit:
	@docker-compose run --rm test pytest tests/ -m unit -v

test-integration:
	@docker-compose run --rm test pytest tests/ -m integration -v

test-coverage:
	@docker-compose run --rm test pytest tests/ -v --cov=app --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

build:
	@docker-compose build

up:
	@docker-compose up -d db backend
	@echo "Services started. API available at http://localhost:8000"

down:
	@docker-compose down

logs:
	@docker-compose logs -f backend

clean:
	@docker-compose down -v
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@find . -type d -name .pytest_cache -exec rm -rf {} +
	@find . -type d -name htmlcov -exec rm -rf {} +
	@echo "Cleanup complete"
