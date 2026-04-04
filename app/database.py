import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from .models import Device, DeviceStatus

class Database:
    def __init__(self, db_path: str = "devices.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    imei TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'disconnected',
                    battery_level INTEGER DEFAULT 0,
                    is_charging BOOLEAN DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    connected_at TIMESTAMP
                )
            """)
    
    def get_all_devices(self) -> List[Device]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC")
            rows = cursor.fetchall()
            return [Device(**dict(row)) for row in rows]
    
    def get_device(self, device_id: str) -> Optional[Device]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
            row = cursor.fetchone()
            return Device(**dict(row)) if row else None
    
    def upsert_device(self, device: Device):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO devices (id, name, imei, status, battery_level, is_charging, last_seen, connected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    status=excluded.status,
                    battery_level=excluded.battery_level,
                    is_charging=excluded.is_charging,
                    last_seen=excluded.last_seen,
                    connected_at=excluded.connected_at
            """, (
                device.id, device.name, device.imei, device.status,
                device.battery_level, device.is_charging, device.last_seen,
                device.connected_at
            ))
            conn.commit()
    
    def update_status(self, device_id: str, status: DeviceStatus):
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.utcnow().isoformat()
            if status == DeviceStatus.CONNECTED:
                conn.execute("""
                    UPDATE devices 
                    SET status = ?, last_seen = ?, connected_at = ?
                    WHERE id = ?
                """, (status, now, now, device_id))
            else:
                conn.execute("""
                    UPDATE devices 
                    SET status = ?, last_seen = ?
                    WHERE id = ?
                """, (status, now, device_id))
            conn.commit()

db = Database()