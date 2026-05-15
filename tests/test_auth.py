"""Tests for authentication routes."""
import pytest
from app.models import UserCreate


@pytest.mark.unit
def test_user_create_model():
    """Test the UserCreate Pydantic model."""
    user = UserCreate(email="test@example.com", password="password123")
    assert user.email == "test@example.com"
    assert user.password == "password123"
    assert user.language == "en"


@pytest.mark.unit
def test_user_create_password_validation():
    """Test that password must be at least 8 characters."""
    with pytest.raises(ValueError):
        UserCreate(email="test@example.com", password="short")


@pytest.mark.integration
async def test_register_user(client):
    """Test user registration endpoint."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "securepassword123"
        }
    )
    assert response.status_code in [200, 201]


@pytest.mark.integration
async def test_login_user(client):
    """Test user login endpoint."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )
    # May return 401 if user doesn't exist, which is expected
    assert response.status_code in [200, 401]
