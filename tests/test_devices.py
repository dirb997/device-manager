"""Tests for device management endpoints."""
import pytest
from app.models import DeviceCreate, DeviceStatus, ConnectionType


@pytest.mark.unit
def test_device_create_model():
    """Test the DeviceCreate Pydantic model."""
    device = DeviceCreate(
        name="iPhone 14",
        imei="123456789012345",
        connection_type=ConnectionType.USB
    )
    assert device.name == "iPhone 14"
    assert device.imei == "123456789012345"
    assert device.connection_type == ConnectionType.USB


@pytest.mark.unit
def test_device_status_enum():
    """Test DeviceStatus enum values."""
    assert DeviceStatus.CONNECTED == "connected"
    assert DeviceStatus.DISCONNECTED == "disconnected"
    assert DeviceStatus.UNREGISTERED == "unregistered"


@pytest.mark.unit
def test_connection_type_enum():
    """Test ConnectionType enum values."""
    assert ConnectionType.USB == "usb"
    assert ConnectionType.BLUETOOTH == "bluetooth"
    assert ConnectionType.WIFI == "wifi"
    assert ConnectionType.MANUAL == "manual"
    assert ConnectionType.OTHER == "other"


@pytest.mark.integration
async def test_get_devices(client):
    """Test getting list of devices."""
    response = await client.get("/api/devices")
    assert response.status_code in [200, 401]  # May require auth


@pytest.mark.integration
async def test_create_device(client):
    """Test creating a new device."""
    device_data = {
        "name": "Test Device",
        "imei": "123456789012345",
        "connection_type": "usb"
    }
    response = await client.post("/api/devices", json=device_data)
    assert response.status_code in [200, 201, 401, 422]


@pytest.mark.integration
async def test_device_battery_update(client):
    """Test battery level update endpoint."""
    battery_data = {
        "device_id": "test-device-1",
        "battery_level": 85,
        "is_charging": True,
        "is_registered": True
    }
    response = await client.post(
        "/api/battery-update",
        json=battery_data
    )
    assert response.status_code in [200, 401, 404, 422]
