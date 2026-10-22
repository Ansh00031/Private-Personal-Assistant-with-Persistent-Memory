# path: memory/db.py
"""SQLite (SQLCipher) schema and encryption for memory storage."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# Try to import SQLCipher, fall back to standard sqlite3 for testing
try:
    import sqlcipher3 as sqlite3_cipher
    HAS_SQLCIPHER = True
except ImportError:
    sqlite3_cipher = sqlite3
    HAS_SQLCIPHER = False


DB_PATH = Path(os.getenv("MEMORY_DB_PATH", "data/memory.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Encryption key from env (32 bytes hex = 64 chars)
ENCRYPTION_KEY = os.getenv("MEMORY_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("MEMORY_ENCRYPTION_KEY environment variable not set (64 hex chars)")


def get_connection():
    """Get encrypted database connection with WAL mode and vec extension."""
    db_path = Path(os.getenv("MEMORY_DB_PATH", str(DB_PATH)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3_cipher.connect(db_path)
    if HAS_SQLCIPHER:
        conn.execute(f"PRAGMA key = \"x'{ENCRYPTION_KEY}'\"")
        conn.execute("PRAGMA cipher_page_size = 4096")
        conn.execute("PRAGMA kdf_iter = 256000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.enable_load_extension(True)
    try:
        conn.load_extension("vec0")
    except Exception:
        pass  # vec extension may not be available in all builds
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3_cipher.Row
    return conn


def init_db() -> None:
    """Initialize schema with FTS5 and vec tables."""
    with get_connection() as conn:
        # Memories table with provenance
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                provenance TEXT NOT NULL CHECK(provenance IN ('user_said', 'tool_output')),
                source_turn_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP NULL
            )
        """)

        # FTS5 for full-text search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                content='memories',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
                INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)

        # Vec index for semantic search (sqlite-vec) - optional
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(
                    embedding float[1024]
                )
            """)
        except sqlite3.OperationalError:
            pass  # vec0 extension not available

        # Episodes table for extracted facts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                memory_id INTEGER REFERENCES memories(id),
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP NULL
            )
        """)

        # Provenance audit log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provenance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER REFERENCES memories(id),
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


@contextmanager
def transaction():
    """Context manager for atomic transactions."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hard_delete_memory(memory_id: int) -> bool:
    """
    Hard delete a memory: removes row, vector, and FTS entry.
    Returns True if deleted, False if not found.
    """
    with transaction() as conn:
        # Check exists and get content for provenance
        row = conn.execute("SELECT id, content FROM memories WHERE id = ? AND deleted_at IS NULL", (memory_id,)).fetchone()
        if not row:
            return False

        content = row["content"]

        # Delete from vec (by rowid) - may not exist if vec0 not available
        try:
            conn.execute("DELETE FROM memories_vec WHERE rowid = ?", (memory_id,))
        except sqlite3.OperationalError:
            pass

        # Hard delete from memories (triggers FTS cleanup via memories_ad trigger)
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

        # Log provenance (after delete, but memory_id still valid for FK)
        conn.execute(
            "INSERT INTO provenance_log (memory_id, action, details) VALUES (?, 'hard_delete', '{}')",
            (memory_id,)
        )
        conn.commit()
        return True


def verify_hard_delete(memory_id: int) -> bool:
    """Verify memory is fully removed from all tables."""
    with get_connection() as conn:
        # Check main table (row should be completely gone)
        main = conn.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,)).fetchone()
        # Check vec (may not exist if vec0 not available)
        try:
            vec = conn.execute("SELECT 1 FROM memories_vec WHERE rowid = ?", (memory_id,)).fetchone()
        except sqlite3.OperationalError:
            vec = None
        # Check FTS
        fts = conn.execute("SELECT 1 FROM memories_fts WHERE rowid = ?", (memory_id,)).fetchone()
        return main is None and vec is None and fts is None