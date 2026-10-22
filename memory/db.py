# path: memory/db.py
"""SQLite (SQLCipher) schema and encryption for memory storage."""

import os
import hashlib
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Encryption configuration: "on" by default. Only "off" explicitly allows plain sqlite3 for tests.
MEMORY_ENCRYPTION = os.getenv("MEMORY_ENCRYPTION", "on").strip().lower()

if MEMORY_ENCRYPTION == "off":
    sqlite3_cipher = sqlite3
    HAS_SQLCIPHER = False
else:
    try:
        import sqlcipher3 as sqlite3_cipher
        HAS_SQLCIPHER = True
    except ImportError as e:
        raise RuntimeError(
            "SQLCipher is required for encrypted memory but 'sqlcipher3' is not available. "
            "Please install sqlcipher3 or run in Docker. "
            "Plain SQLite is allowed ONLY when MEMORY_ENCRYPTION=off is set explicitly (for tests only)."
        ) from e

DB_OperationalError = getattr(sqlite3_cipher, "OperationalError", sqlite3.OperationalError)
DB_DatabaseError = getattr(sqlite3_cipher, "DatabaseError", sqlite3.DatabaseError)

DB_PATH = Path(os.getenv("MEMORY_DB_PATH", "data/memory.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_salt_for_path(db_path: Path) -> bytes:
    """Retrieve or create persistent salt for key derivation."""
    salt_env = os.getenv("MEMORY_SALT")
    if salt_env:
        return salt_env.encode("utf-8")

    salt_file = db_path.with_suffix(".salt")
    if salt_file.exists():
        try:
            return salt_file.read_bytes()
        except Exception as e:
            logger.warning(f"Could not read salt file, generating fallback: {e}")

    # Generate 16 bytes of cryptographically secure random salt
    salt = os.urandom(16)
    try:
        salt_file.parent.mkdir(parents=True, exist_ok=True)
        salt_file.write_bytes(salt)
    except Exception as e:
        logger.warning(f"Could not persist salt file: {e}")
    return salt


def derive_key(passphrase: str, salt: bytes) -> str:
    """
    Derive 256-bit encryption key from passphrase using scrypt KDF (RFC 7914).
    Returns 64 hex characters (32 bytes). Never store or log this value.
    """
    if not passphrase:
        raise ValueError("Passphrase cannot be empty")
    key_bytes = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32
    )
    return key_bytes.hex()


def get_connection(db_path_override: Optional[Path] = None, passphrase_override: Optional[str] = None):
    """Get database connection (encrypted via SQLCipher if enabled) with WAL mode and vec extension."""
    target_path = db_path_override or Path(os.getenv("MEMORY_DB_PATH", str(DB_PATH)))
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3_cipher.connect(str(target_path))

    if HAS_SQLCIPHER:
        passphrase = passphrase_override or os.getenv("MEMORY_PASSPHRASE") or os.getenv("MEMORY_ENCRYPTION_KEY")
        if not passphrase:
            conn.close()
            raise ValueError("MEMORY_PASSPHRASE (or MEMORY_ENCRYPTION_KEY) environment variable not set")

        salt = get_salt_for_path(target_path)
        raw_key_hex = derive_key(passphrase, salt)
        conn.execute(f"PRAGMA key = \"x'{raw_key_hex}'\"")
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
    if HAS_SQLCIPHER:
        logger.info("encryption: on")
    else:
        logger.warning("encryption: off (plain SQLite)")

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
        except (DB_OperationalError, sqlite3.OperationalError):
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
        except (DB_OperationalError, sqlite3.OperationalError):
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
        except (DB_OperationalError, sqlite3.OperationalError):
            vec = None
        # Check FTS
        fts = conn.execute("SELECT 1 FROM memories_fts WHERE rowid = ?", (memory_id,)).fetchone()
        return main is None and vec is None and fts is None
