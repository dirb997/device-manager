import os
import uuid
from datetime import datetime
from typing import List, Optional

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from app.models import Device, DeviceStatus, UserPublic

load_dotenv()

class Database:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://localhost:5433/device_manager",
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
                    connected_at TIMESTAMP WITHOUT TIME ZONE,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    jti TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    revoked_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
                cursor.execute("""
                ALTER TABLE devices
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            """)
                cursor.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
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
                INSERT INTO devices (id, name, imei, connection_type, status, battery_level, battery_display, is_charging, last_seen, connected_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    connection_type=excluded.connection_type,
                    status=excluded.status,
                    battery_level=excluded.battery_level,
                    battery_display=excluded.battery_display,
                    is_charging=excluded.is_charging,
                    last_seen=excluded.last_seen,
                    connected_at=excluded.connected_at
                        ,updated_at=excluded.updated_at
            """, (
                device.id,
                device.name,
                device.imei,
                device.connection_type.value if hasattr(device.connection_type, "value") else device.connection_type,
                device.status.value if hasattr(device.status, "value") else device.status,
                device.battery_level,
                getattr(device, "battery_display", ""),
                device.is_charging,
                device.last_seen,
                device.connected_at,
                device.updated_at
            ))
            conn.commit()

    def create_user(self, email: str, password_hash: str) -> UserPublic:
        user_id = str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (id, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, email, created_at, updated_at
                    """,
                    (user_id, email, password_hash),
                )
                row = cursor.fetchone()
            conn.commit()
        if not row:
            raise RuntimeError("Failed to create user")
        return UserPublic(**dict(row))

    def get_user_auth_by_email(self, email: str) -> Optional[dict]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT id, email, password_hash, created_at, updated_at FROM users WHERE email = %s",
                    (email,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[UserPublic]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT id, email, created_at, updated_at FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()
                return UserPublic(**dict(row)) if row else None

    def revoke_token(self, jti: str, user_id: str, expires_at: datetime) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO revoked_tokens (jti, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (jti) DO NOTHING
                    """,
                    (jti, user_id, expires_at),
                )
            conn.commit()

    def is_token_revoked(self, jti: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM revoked_tokens WHERE jti = %s LIMIT 1",
                    (jti,),
                )
                return cursor.fetchone() is not None
    
    def update_status(self, device_id: str, status: DeviceStatus):
        with self._connect() as conn:
            now = datetime.utcnow()
            with conn.cursor() as cursor:
                if status == DeviceStatus.CONNECTED:
                    cursor.execute("""
                        UPDATE devices 
                        SET status = %s, last_seen = %s, connected_at = %s, updated_at = %s
                        WHERE id = %s
                    """, (status.value, now, now, now, device_id))
                else:
                    cursor.execute("""
                        UPDATE devices 
                        SET status = %s, last_seen = %s, updated_at = %s
                        WHERE id = %s
                    """, (status.value, now, now, device_id))
            conn.commit()

db = Database()
