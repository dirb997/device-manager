import pytest
import asyncio
import os
from httpx import AsyncClient
from dotenv import load_dotenv

# Load test environment variables
load_dotenv()

# Test database setup
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5434/device_manager_test"
)

from app.main import app
from app.database import Database


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Set up test database before running tests.
    Creates all necessary tables via the Database class.
    """
    # Initialize the test database
    test_db = Database(TEST_DATABASE_URL)
    
    yield
    
    try:
        with test_db._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS revoked_tokens CASCADE")
                cursor.execute("DROP TABLE IF EXISTS devices CASCADE")
                cursor.execute("DROP TABLE IF EXISTS users CASCADE")
            conn.commit()
    except Exception as e:
        print(f"Cleanup error: {e}")


@pytest.fixture
async def client():
    """
    Provide an async HTTP client for testing API endpoints.
    Automatically uses TEST_DATABASE_URL via environment variable.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """
    Provide authentication headers for protected endpoints.
    This should be called in tests that require authentication.
    """
    return {
        "Authorization": "Bearer test-token"
    }


@pytest.fixture
def test_db():
    """
    Provide access to the test database.
    Useful for test setup/teardown and assertions.
    """
    return Database(TEST_DATABASE_URL)
