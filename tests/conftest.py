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

from app.database import Database


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Set up test database before running tests.
    Initializes schema and replaces the app's db instance with test database.
    """
    # Create and initialize the test database with schema
    test_db = Database(TEST_DATABASE_URL)
    test_db.init_db()
    
    # Monkey-patch the app.database module to use test database
    import app.database
    original_get_db = app.database.get_db
    
    # Replace get_db to return our test instance
    app.database.get_db = lambda: test_db
    app.database._db_instance = test_db
    
    # Also patch any already-imported references in route modules
    import app.routes.devices
    import app.routes.auth
    app.routes.devices.db = test_db
    app.routes.auth.db = test_db
    
    # Patch auth.py if it imports db
    import app.auth
    if hasattr(app.auth, 'db'):
        app.auth.db = test_db
    
    yield
    
    # Restore original database function
    app.database.get_db = original_get_db
    app.database._db_instance = None
    
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
    The app uses the test database via monkey-patching in setup_test_db.
    """
    from app.main import app
    
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
