from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class DeviceStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

class DeviceBase(BaseModel):
    name: str
    imei: str
    is_charging: bool = False
    battery_level: int = 0  # 0-100
    
class DeviceCreate(DeviceBase):
    pass

class Device(DeviceBase):
    id: str
    status: DeviceStatus
    last_seen: datetime
    connected_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class BatteryUpdate(BaseModel):
    device_id: str
    battery_level: int
    is_charging: bool