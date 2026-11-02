import sqlite3
import os
import json
import time
import threading
import contextlib
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from ..utils_logging import get_logger

logger = get_logger("db")

from ..paths import get_db_path


class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> 'DatabaseManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = DatabaseManager(db_path)
            return cls._instance

    @contextlib.contextmanager
    def _get_connection(self):
        """
        Provides SQLite connection with retry-with-backoff for transient 'database is locked' errors.
        """
        max_retries = 5
        base_delay = 0.05
        conn = None
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
                conn.row_factory = sqlite3.Row
                break
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() and attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning(f"Database locked, retrying connect in {sleep_time:.2f}s (attempt {attempt+1})")
                    time.sleep(sleep_time)
                else:
                    raise

        try:
            yield conn
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    get_connection = _get_connection

    def _execute_with_retry(self, func, max_retries: int = 5):
        base_delay = 0.05
        for attempt in range(max_retries):
            try:
                return func()
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() and attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning(f"Database locked on query, retrying in {sleep_time:.2f}s (attempt {attempt+1})")
                    time.sleep(sleep_time)
                else:
                    raise

    def init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    keys_per_min INTEGER NOT NULL DEFAULT 0,
                    mouse_events_per_min INTEGER NOT NULL DEFAULT 0,
                    active_window_title TEXT,
                    active_process_name TEXT,
                    idle_seconds REAL NOT NULL DEFAULT 0.0
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS energy_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    energy_level INTEGER NOT NULL,
                    prompt_type TEXT DEFAULT 'periodic_checkin',
                    notes TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nudge_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    nudge_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    action TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nudge_decision_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    nudge_type TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    keys_per_min INTEGER DEFAULT 0,
                    mouse_events_per_min INTEGER DEFAULT 0,
                    idle_seconds REAL DEFAULT 0.0,
                    continuous_active_min REAL DEFAULT 0.0,
                    continuous_typing_min REAL DEFAULT 0.0,
                    is_in_flow INTEGER DEFAULT 0,
                    metadata TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recovery_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    details TEXT
                )
            ''')
            conn.commit()

    def log_activity(self, keys_per_min: int, mouse_events_per_min: int,
                     active_window_title: Optional[str], active_process_name: Optional[str],
                     idle_seconds: float, timestamp: Optional[str] = None) -> int:
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Deduplication check if exact timestamp is passed
                if timestamp:
                    cursor.execute('SELECT id FROM activity_log WHERE timestamp = ?', (timestamp,))
                    existing = cursor.fetchone()
                    if existing:
                        logger.info(f"Skipping duplicate activity log for timestamp {timestamp}")
                        return existing['id']
                    cursor.execute('''
                        INSERT INTO activity_log (timestamp, keys_per_min, mouse_events_per_min, active_window_title, active_process_name, idle_seconds)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (timestamp, keys_per_min, mouse_events_per_min, active_window_title, active_process_name, idle_seconds))
                else:
                    cursor.execute('''
                        INSERT INTO activity_log (keys_per_min, mouse_events_per_min, active_window_title, active_process_name, idle_seconds)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (keys_per_min, mouse_events_per_min, active_window_title, active_process_name, idle_seconds))
                conn.commit()
                return cursor.lastrowid
        return self._execute_with_retry(_op)

    def log_energy(self, energy_level: int, prompt_type: str = 'periodic_checkin', notes: Optional[str] = None, timestamp: Optional[str] = None) -> int:
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if timestamp:
                    cursor.execute('''
                        INSERT INTO energy_log (timestamp, energy_level, prompt_type, notes)
                        VALUES (?, ?, ?, ?)
                    ''', (timestamp, energy_level, prompt_type, notes))
                else:
                    cursor.execute('''
                        INSERT INTO energy_log (energy_level, prompt_type, notes)
                        VALUES (?, ?, ?)
                    ''', (energy_level, prompt_type, notes))
                conn.commit()
                return cursor.lastrowid
        return self._execute_with_retry(_op)

    def log_nudge(self, nudge_type: str, message: str, action: str, timestamp: Optional[str] = None) -> int:
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if timestamp:
                    cursor.execute('''
                        INSERT INTO nudge_log (timestamp, nudge_type, message, action)
                        VALUES (?, ?, ?, ?)
                    ''', (timestamp, nudge_type, message, action))
                else:
                    cursor.execute('''
                        INSERT INTO nudge_log (nudge_type, message, action)
                        VALUES (?, ?, ?)
                    ''', (nudge_type, message, action))
                conn.commit()
                return cursor.lastrowid
        return self._execute_with_retry(_op)

    def log_nudge_decision(self, nudge_type: str, decision: str, reason: str,
                           keys_per_min: int = 0, mouse_events_per_min: int = 0,
                           idle_seconds: float = 0.0, continuous_active_min: float = 0.0,
                           continuous_typing_min: float = 0.0, is_in_flow: bool = False,
                           metadata: Optional[Union[str, Dict[str, Any]]] = None, timestamp: Optional[str] = None) -> int:
        def _op():
            meta_str = json.dumps(metadata) if isinstance(metadata, (dict, list)) else metadata
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if timestamp:
                    cursor.execute('''
                        INSERT INTO nudge_decision_log (
                            timestamp, nudge_type, decision, reason, keys_per_min, mouse_events_per_min,
                            idle_seconds, continuous_active_min, continuous_typing_min, is_in_flow, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (timestamp, nudge_type, decision, reason, keys_per_min, mouse_events_per_min,
                          idle_seconds, continuous_active_min, continuous_typing_min, 1 if is_in_flow else 0, meta_str))
                else:
                    cursor.execute('''
                        INSERT INTO nudge_decision_log (
                            nudge_type, decision, reason, keys_per_min, mouse_events_per_min,
                            idle_seconds, continuous_active_min, continuous_typing_min, is_in_flow, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (nudge_type, decision, reason, keys_per_min, mouse_events_per_min,
                          idle_seconds, continuous_active_min, continuous_typing_min, 1 if is_in_flow else 0, meta_str))
                conn.commit()
                return cursor.lastrowid
        return self._execute_with_retry(_op)

    def log_recovery_event(self, event_type: str, details: Optional[str] = None, timestamp: Optional[str] = None) -> int:
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if timestamp:
                    cursor.execute('''
                        INSERT INTO recovery_log (timestamp, event_type, details)
                        VALUES (?, ?, ?)
                    ''', (timestamp, event_type, details))
                else:
                    cursor.execute('''
                        INSERT INTO recovery_log (event_type, details)
                        VALUES (?, ?)
                    ''', (event_type, details))
                conn.commit()
                return cursor.lastrowid
        return self._execute_with_retry(_op)

    def set_setting(self, key: str, value: str):
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value=excluded.value,
                        updated_at=CURRENT_TIMESTAMP
                ''', (key, value))
                conn.commit()
        return self._execute_with_retry(_op)

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        def _op():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                row = cursor.fetchone()
                return row['value'] if row else default
        return self._execute_with_retry(_op)

    def get_recent_activity(self, limit: int = 60) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM activity_log ORDER BY timestamp DESC, id DESC LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_activity_last_minutes(self, minutes: int = 5) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM activity_log 
                WHERE timestamp >= datetime('now', '-' || ? || ' minutes')
                ORDER BY timestamp DESC, id DESC
            ''', (minutes,))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute('''
                    SELECT * FROM activity_log ORDER BY timestamp DESC, id DESC LIMIT ?
                ''', (minutes,))
                rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_recent_energy(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM energy_log ORDER BY timestamp DESC, id DESC LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_nudge_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM nudge_decision_log ORDER BY timestamp DESC, id DESC LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_database_size_bytes(self) -> int:
        try:
            return os.path.getsize(self.db_path)
        except Exception:
            return 0
