from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
from datetime import datetime
import uuid
from ..models import Device, DeviceCreate, DeviceStatus, BatteryUpdate
from ..database import db
from ..websocket.manager import manager
from ..device_discovery import (
    discover_bluetooth_devices,
    discover_android_devices,
    discover_apple_mobile_devices,
    discover_macos_usb_devices,
    discover_wifi_devices,
)

router = APIRouter()


def _merge_discovered_device(existing: Device | None, discovered: Device) -> Device:
    if not existing:
        return discovered

    if discovered.battery_level == 0 and existing.battery_level > 0:
        discovered = discovered.model_copy(
            update={
                "battery_level": existing.battery_level,
                "is_charging": existing.is_charging,
                "battery_display": existing.battery_display,
            }
        )

    return discovered

@router.get("/devices", response_model=List[Device])
async def get_devices():
    """Get all devices (both connected and disconnected)"""
    return db.get_all_devices()

@router.get("/devices/connected", response_model=List[Device])
async def get_connected_devices():
    """Get only connected devices with battery info"""
    devices = db.get_all_devices()
    return [d for d in devices if d.status == DeviceStatus.CONNECTED]

@router.get("/devices/disconnected", response_model=List[Device])
async def get_disconnected_devices():
    """Get only disconnected devices"""
    devices = db.get_all_devices()
    return [d for d in devices if d.status == DeviceStatus.DISCONNECTED]


@router.post("/devices/scan")
async def scan_devices():
    """Scan locally connected devices and sync them to the DB."""
    discovered = [
        *discover_android_devices(),
        *discover_apple_mobile_devices(),
        *discover_macos_usb_devices(),
        *discover_wifi_devices(),
        *discover_bluetooth_devices(),
    ]
    discovered_ids = {d.id for d in discovered}

    existing = db.get_all_devices()
    existing_by_id = {device.id: device for device in existing}
    for device in existing:
        if (
            (
                device.id.startswith("adb-")
                or device.id.startswith("apple-")
                or device.id.startswith("usb-")
                or device.id.startswith("wifi-")
                or device.id.startswith("bluetooth-")
            )
            and device.id not in discovered_ids
        ):
            db.update_status(device.id, DeviceStatus.DISCONNECTED)

    for device in discovered:
        db.upsert_device(_merge_discovered_device(existing_by_id.get(device.id), device))

    return {
        "discovered": len(discovered),
        "device_ids": sorted(discovered_ids),
    }

@router.post("/devices/connect")
async def connect_device(device: DeviceCreate):
    """Register or update a connected device"""
    device_id = str(uuid.uuid4())
    device_obj = Device(
        id=device_id,
        name=device.name,
        imei=device.imei,
        connection_type="manual",
        status=DeviceStatus.CONNECTED,
        battery_level=device.battery_level,
        battery_display=device.battery_display or (f"{device.battery_level}%" if device.battery_level > 0 else ""),
        is_charging=device.is_charging,
        last_seen=datetime.utcnow(),
        connected_at=datetime.utcnow()
    )
    db.upsert_device(device_obj)
    
    # Broadcast to all connected clients
    await manager.broadcast({
        "type": "device_connected",
        "device": device_obj.dict()
    })
    
    return device_obj

@router.post("/devices/{device_id}/disconnect")
async def disconnect_device(device_id: str):
    """Mark device as disconnected"""
    db.update_status(device_id, DeviceStatus.DISCONNECTED)
    device = db.get_device(device_id)
    
    await manager.broadcast({
        "type": "device_disconnected",
        "device_id": device_id,
        "device": device.dict() if device else None
    })
    
    return {"status": "disconnected"}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    device_id = None
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "register":
                device_id = data.get("device_id")
                if device_id:
                    manager.device_connections[device_id] = websocket
                    db.update_status(device_id, DeviceStatus.CONNECTED)
                    
            elif data.get("type") == "battery_update":
                update = BatteryUpdate(**data)
                db.update_status(update.device_id, DeviceStatus.CONNECTED)
                device = db.get_device(update.device_id)
                if device:
                    device.battery_level = update.battery_level
                    device.is_charging = update.is_charging
                    device.last_seen = datetime.utcnow()
                    device.battery_display = f"{update.battery_level}%" if device.connection_type != "bluetooth" else "No battery input"
                    db.upsert_device(device)
                    
                    # Broadcast battery update to all UI clients
                    await manager.broadcast({
                        "type": "battery_update",
                        "device_id": update.device_id,
                        "battery_level": update.battery_level,
                        "is_charging": update.is_charging,
                        "battery_display": device.battery_display,
                    })
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket, device_id)
        if device_id:
            db.update_status(device_id, DeviceStatus.DISCONNECTED)
            await manager.broadcast({
                "type": "device_disconnected",
                "device_id": device_id
            })