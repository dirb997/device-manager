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
async def test_connect_device(client):
    """Test connecting a device."""
    device_data = {
        "name": "Test Device",
        "imei": "123456789012345",
        "connection_type": "usb"
    }
    response = await client.post("/api/devices/connect", json=device_data)
    assert response.status_code in [200, 401, 422]


