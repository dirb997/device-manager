"""Tests for the health check and main endpoints."""
import pytest


@pytest.mark.unit
async def test_health_check(client):
    """Test the health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.unit
async def test_app_title():
    """Test that the app has the correct title."""
    from app.main import app
    assert app.title == "Device Manager API"
    assert app.version == "1.0.0"
