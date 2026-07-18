import os
import uuid
from datetime import datetime
from typing import List, Optional

import psycopg
import sqlite3
from urllib.parse import urlparse
from dotenv import load_dotenv
from psycopg.rows import dict_row

from app.models import Device, DeviceStatus, UserPublic

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)

class Database:
    def __init__(self, database_url: str | None = None):
        env_url = os.getenv("DATABASE_URL")
        # If a database_url is provided explicitly use it, otherwise prefer env, otherwise fallback to sqlite file
        self.database_url = database_url or env_url

        # Decide whether to use sqlite or postgres
        if not self.database_url:
            # default to a local sqlite file inside the project
            db_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'device_manager.db')
            db_file = os.path.abspath(db_file)
            os.makedirs(os.path.dirname(db_file), exist_ok=True)
            self.database_url = f'sqlite:///{db_file}'

        # Ensure attribute exists early to avoid AttributeError during partial init
        self.use_sqlite = False

        parsed = urlparse(self.database_url)

        # If no scheme is present, try to infer intent:
        # - If it looks like a filesystem path or a .db file -> sqlite
        # - Otherwise assume postgres and prefix the scheme
        if not parsed.scheme:
            raw = self.database_url
            looks_like_file = raw.endswith('.db') or os.path.sep in raw or raw.startswith('.')
            if looks_like_file:
                db_file = os.path.abspath(raw)
                self.database_url = f'sqlite:///{db_file}'
                parsed = urlparse(self.database_url)
            else:
                # assume postgres DSN missing scheme
                self.database_url = f'postgresql://{raw}'
                parsed = urlparse(self.database_url)

        self.use_sqlite = parsed.scheme.startswith('sqlite')

        # Log chosen database mode for diagnostics
        if self.use_sqlite:
            logging.info(f"Using SQLite database at {self.database_url}")
        else:
            logging.info(f"Using Postgres database URL: {self.database_url}")

        self.init_db()

    def _connect(self):
        if self.use_sqlite:
            # sqlite URL is sqlite:///absolute/path or sqlite:///<path>
            parsed = urlparse(self.database_url)
            path = parsed.path
            # On Windows the path may start with /C: - sqlite3 accepts that
            conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            try:
                return psycopg.connect(self.database_url)
            except Exception as e:
                # If Postgres connection fails at startup, log and fallback to sqlite for local desktop usage.
                logging.error(f"Postgres connect failed: {e}; falling back to local SQLite database.")
                # create sqlite fallback file beside the project if not already
                db_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'device_manager.db')
                db_file = os.path.abspath(db_file)
                os.makedirs(os.path.dirname(db_file), exist_ok=True)
                self.database_url = f'sqlite:///{db_file}'
                self.use_sqlite = True
                parsed = urlparse(self.database_url)
                path = parsed.path
                conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
                conn.row_factory = sqlite3.Row
                return conn
    
    def init_db(self):
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    imei TEXT UNIQUE NOT NULL,
                    connection_type TEXT NOT NULL DEFAULT 'manual',
                    status TEXT DEFAULT 'disconnected',
                    battery_level INTEGER DEFAULT 0,
                    battery_display TEXT DEFAULT '',
                    is_charging BOOLEAN DEFAULT 0,
                    last_seen DATETIME DEFAULT (datetime('now')),
                    connected_at DATETIME,
                    updated_at DATETIME DEFAULT (datetime('now'))
                )
            """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    created_at DATETIME DEFAULT (datetime('now')),
                    updated_at DATETIME DEFAULT (datetime('now'))
                )
            """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    jti TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at DATETIME NOT NULL,
                    revoked_at DATETIME DEFAULT (datetime('now'))
                )
            """)
                conn.commit()
        else:
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
                        language TEXT NOT NULL DEFAULT 'en',
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
                conn.commit()
    
    def get_all_devices(self) -> List[Device]:
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM devices ORDER BY last_seen DESC")
                rows = cursor.fetchall()
                return [Device(**dict(row)) for row in [dict(r) for r in rows]]
        else:
            with self._connect() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute("SELECT * FROM devices ORDER BY last_seen DESC")
                    rows = cursor.fetchall()
                    return [Device(**dict(row)) for row in rows]
    
    def get_device(self, device_id: str) -> Optional[Device]:
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
                row = cursor.fetchone()
                return Device(**dict(row)) if row else None
        else:
            with self._connect() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute("SELECT * FROM devices WHERE id = %s", (device_id,))
                    row = cursor.fetchone()
                    return Device(**dict(row)) if row else None
    
    def upsert_device(self, device: Device):
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO devices (id, name, imei, connection_type, status, battery_level, battery_display, is_charging, last_seen, connected_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    connection_type=excluded.connection_type,
                    status=excluded.status,
                    battery_level=excluded.battery_level,
                    battery_display=excluded.battery_display,
                    is_charging=excluded.is_charging,
                    last_seen=excluded.last_seen,
                    connected_at=excluded.connected_at,
                    updated_at=excluded.updated_at
            """, (
                device.id,
                device.name,
                device.imei,
                device.connection_type.value if hasattr(device.connection_type, "value") else device.connection_type,
                device.status.value if hasattr(device.status, "value") else device.status,
                device.battery_level,
                getattr(device, "battery_display", ""),
                1 if device.is_charging else 0,
                device.last_seen,
                device.connected_at,
                device.updated_at,
            ))
                conn.commit()
        else:
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
                    device.updated_at,
                ))
                conn.commit()

    def create_user(self, email: str, password_hash: str, language: str = 'en') -> UserPublic:
        user_id = str(uuid.uuid4())
        user_language = (language or 'en').strip().lower()[:8] or 'en'
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (id, email, password_hash, language)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, email, password_hash, user_language),
                )
                conn.commit()
                cursor.execute("SELECT id, email, language, created_at, updated_at FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
        else:
            with self._connect() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (id, email, password_hash, language)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, email, language, created_at, updated_at
                        """,
                        (user_id, email, password_hash, user_language),
                    )
                    row = cursor.fetchone()
                conn.commit()
        if not row:
            raise RuntimeError("Failed to create user")
        return UserPublic(**dict(row))

    def get_user_auth_by_email(self, email: str) -> Optional[dict]:
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, email, password_hash, language, created_at, updated_at FROM users WHERE email = ?", (email,))
                row = cursor.fetchone()
                return dict(row) if row else None
        else:
            with self._connect() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT id, email, password_hash, language, created_at, updated_at FROM users WHERE email = %s",
                        (email,),
                    )
                    row = cursor.fetchone()
                    return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[UserPublic]:
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, email, language, created_at, updated_at FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                return UserPublic(**dict(row)) if row else None
        else:
            with self._connect() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT id, email, language, created_at, updated_at FROM users WHERE id = %s",
                        (user_id,),
                    )
                    row = cursor.fetchone()
                    return UserPublic(**dict(row)) if row else None

    def revoke_token(self, jti: str, user_id: str, expires_at: datetime) -> None:
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO revoked_tokens (jti, user_id, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (jti, user_id, expires_at),
                )
                conn.commit()
        else:
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
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM revoked_tokens WHERE jti = ? LIMIT 1", (jti,))
                return cursor.fetchone() is not None
        else:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT 1 FROM revoked_tokens WHERE jti = %s LIMIT 1",
                        (jti,),
                    )
                    return cursor.fetchone() is not None
    
    def update_status(self, device_id: str, status: DeviceStatus):
        now = datetime.utcnow()
        if self.use_sqlite:
            with self._connect() as conn:
                cursor = conn.cursor()
                if status == DeviceStatus.CONNECTED:
                    cursor.execute(
                        """
                        UPDATE devices 
                        SET status = ?, last_seen = ?, connected_at = ?, updated_at = ?
                        WHERE id = ?
                    """, (status.value, now, now, now, device_id))
                else:
                    cursor.execute(
                        """
                        UPDATE devices 
                        SET status = ?, last_seen = ?, updated_at = ?
                        WHERE id = ?
                    """, (status.value, now, now, device_id))
                conn.commit()
        else:
            with self._connect() as conn:
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


_db_instance = None

def get_db():
    """Get or create the database instance lazily."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


class _LazyDB:
    """Lazy proxy for the db instance to defer connection until needed."""
    def __getattr__(self, name):
        return getattr(get_db(), name)


db = _LazyDB()
