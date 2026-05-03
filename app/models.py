from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class DeviceStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNREGISTERED = "unregistered"


class ConnectionType(str, Enum):
    USB = "usb"
    BLUETOOTH = "bluetooth"
    WIFI = "wifi"
    MANUAL = "manual"
    OTHER = "other"

class DeviceBase(BaseModel):
    name: str
    imei: str
    connection_type: ConnectionType = ConnectionType.MANUAL
    is_charging: bool = False
    battery_level: int = 0  # 0-100
    battery_display: str = ""
    
class DeviceCreate(DeviceBase):
    pass

class Device(DeviceBase):
    id: str
    status: DeviceStatus
    last_seen: datetime
    connected_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class BatteryUpdate(BaseModel):
    device_id: str
    battery_level: int
    is_charging: bool
    is_registered: bool


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
