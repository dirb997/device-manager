# Backend Testing Guide

Ethos DMS project uses **pytest** for unit and integration testing, running inside Docker containers for consistency.

## Quick Start

### Run all tests in Docker
```bash
docker-compose run --rm test pytest tests/ -v
```

### Run specific test file
```bash
docker-compose run --rm test pytest tests/test_main.py -v
```

### Run specific test
```bash
docker-compose run --rm test pytest tests/test_main.py::test_health_check -v
```

### Run only unit tests (fast)
```bash
docker-compose run --rm test pytest -m unit -v
```

### Run only integration tests
```bash
docker-compose run --rm test pytest -m integration -v
```

## Local Testing (Without Docker)

If you prefer to run tests locally, you need:

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up test database:**
   ```bash
   export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/device_manager_test"
   psql -U postgres -h localhost -p 5433 -c "CREATE DATABASE device_manager_test;"
   ```

3. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures and configuration
├── test_main.py         # Main app endpoint tests
├── test_auth.py         # Authentication tests
└── test_devices.py      # Device management tests
```

## Test Categories

Tests are organized by marker:

- **`@pytest.mark.unit`** - Fast unit tests (no database)
- **`@pytest.mark.integration`** - Integration tests (requires database)
- **`@pytest.mark.auth`** - Authentication-related tests
- **`@pytest.mark.device`** - Device-related tests
- **`@pytest.mark.websocket`** - WebSocket tests

## Available Fixtures

### `client`
Async HTTP client for testing API endpoints.

```python
async def test_example(client):
    response = await client.get("/health")
    assert response.status_code == 200
```

### `db_session`
Fresh database session for each test (auto-rolled back).

```python
async def test_with_db(db_session):
    # Use db_session for database queries
    pass
```

### `auth_headers`
Pre-configured authentication headers for protected endpoints.

```python
async def test_protected(client, auth_headers):
    response = await client.get("/api/protected", headers=auth_headers)
    assert response.status_code == 200
```

## Docker Compose Commands

### Set up databases
```bash
docker-compose up db db-test -d
```

### Run tests once
```bash
docker-compose run --rm test pytest tests/ -v
```

### Run tests with watch mode (requires installing pytest-watch)
```bash
docker-compose run --rm test ptw tests/
```

### Get test coverage report
```bash
docker-compose run --rm test pytest tests/ --cov=app --cov-report=html
```

### Clean up
```bash
docker-compose down
docker-compose down -v  # Also remove volumes
```

## Adding New Tests

1. Create a new file in `tests/` with prefix `test_` (e.g., `test_my_feature.py`)
2. Use appropriate markers: `@pytest.mark.unit` or `@pytest.mark.integration`
3. Import fixtures from `conftest.py` if needed
4. Run: `docker-compose run --rm test pytest tests/test_my_feature.py -v`

Example:
```python
import pytest

@pytest.mark.unit
def test_my_unit_test():
    assert 1 + 1 == 2

@pytest.mark.integration
async def test_my_api_endpoint(client):
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
```

## Troubleshooting

### "Connection refused" when running tests
Make sure test databases are running:
```bash
docker-compose up db-test -d
```

### "ModuleNotFoundError: No module named 'app'"
The PYTHONPATH should be set automatically. If not:
```bash
export PYTHONPATH=/app:$PYTHONPATH
docker-compose run --rm test pytest tests/ -v
```

### Tests pass locally but fail in Docker
Ensure `.env` file is present and DATABASE_URL is correctly configured.

## CI/CD Integration

Add to your GitHub Actions workflow:
```yaml
- name: Run tests
  run: docker-compose run --rm test pytest tests/ -v --tb=short
```

