import os
import sqlite3
from contextlib import closing
from typing import List, Dict, Any, Optional


class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            db_path = os.path.join(base_dir, "transcriptions.db")

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS transcriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        language TEXT,
                        duration_seconds REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """)

                # Default settings if not previously set
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES "
                    "('language', 'auto');"
                )
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES "
                    "('hotkey_mode', 'toggle');"
                )
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES "
                    "('model_size', 'large-v3-turbo');"
                )
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES "
                    "('device', 'cuda');"
                )
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES "
                    "('compute_type', 'float16');"
                )
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES "
                    "('copy_to_clipboard', 'true');"
                )

            conn.commit()

    def add_transcription(
        self, text: str, language: str = "pt", duration_seconds: float = 0.0
    ) -> int:
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO transcriptions "
                    "(text, language, duration_seconds) VALUES (?, ?, ?);",
                    (text.strip(), language, duration_seconds)
                )
                return cursor.lastrowid

    def get_transcriptions(
        self, search_query: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            if search_query:
                cursor.execute(
                    "SELECT * FROM transcriptions WHERE text LIKE ? "
                    "ORDER BY created_at DESC LIMIT ?;",
                    (f"%{search_query}%", limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM transcriptions ORDER BY created_at DESC "
                    "LIMIT ?;",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_transcription(self, item_id: int) -> bool:
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM transcriptions WHERE id = ?;",
                    (item_id,)
                )
                return cursor.rowcount > 0

    def clear_history(self) -> bool:
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transcriptions;")
                return True

    def get_setting(self, key: str, default: str = "") -> str:
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with closing(self._get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
                    (key, str(value))
                )
