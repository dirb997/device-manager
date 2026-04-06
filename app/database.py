import os
from datetime import datetime
from typing import List, Optional

import psycopg
from psycopg.rows import dict_row

from .models import Device, DeviceStatus

class Database:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:diego@localhost:5433/device_manager",
        )
        self.init_db()

    def _connect(self):
        return psycopg.connect(self.database_url)
    
    def init_db(self):
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    imei TEXT UNIQUE NOT NULL,
                    connection_type TEXT NOT NULL DEFAULT 'manual',
                    status TEXT DEFAULT 'disconnected',
                    battery_level INTEGER DEFAULT 0,
                    battery_display TEXT DEFAULT '',
                    is_charging BOOLEAN DEFAULT FALSE,
                    last_seen TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    connected_at TIMESTAMP WITHOUT TIME ZONE
                )
            """)
                cursor.execute("""
                ALTER TABLE devices
                ADD COLUMN IF NOT EXISTS connection_type TEXT NOT NULL DEFAULT 'manual'
            """)
                cursor.execute("""
                ALTER TABLE devices
                ADD COLUMN IF NOT EXISTS battery_display TEXT DEFAULT ''
            """)
            conn.commit()
    
    def get_all_devices(self) -> List[Device]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT * FROM devices ORDER BY last_seen DESC")
                rows = cursor.fetchall()
                return [Device(**dict(row)) for row in rows]
    
    def get_device(self, device_id: str) -> Optional[Device]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT * FROM devices WHERE id = %s", (device_id,))
                row = cursor.fetchone()
                return Device(**dict(row)) if row else None
    
    def upsert_device(self, device: Device):
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO devices (id, name, imei, connection_type, status, battery_level, battery_display, is_charging, last_seen, connected_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    connection_type=excluded.connection_type,
                    status=excluded.status,
                    battery_level=excluded.battery_level,
                    battery_display=excluded.battery_display,
                    is_charging=excluded.is_charging,
                    last_seen=excluded.last_seen,
                    connected_at=excluded.connected_at
            """, (
                device.id,
                device.name,
                device.imei,
                device.connection_type,
                device.status.value if hasattr(device.status, "value") else device.status,
                device.battery_level,
                getattr(device, "battery_display", ""),
                device.is_charging,
                device.last_seen,
                device.connected_at,
            ))
            conn.commit()
    
    def update_status(self, device_id: str, status: DeviceStatus):
        with self._connect() as conn:
            now = datetime.utcnow()
            with conn.cursor() as cursor:
                if status == DeviceStatus.CONNECTED:
                    cursor.execute("""
                        UPDATE devices 
                        SET status = %s, last_seen = %s, connected_at = %s
                        WHERE id = %s
                    """, (status.value, now, now, device_id))
                else:
                    cursor.execute("""
                        UPDATE devices 
                        SET status = %s, last_seen = %s
                        WHERE id = %s
                    """, (status.value, now, device_id))
            conn.commit()

db = Database()