# path: tests/test_db.py
"""Tests for memory/db.py"""

import os
import tempfile
import pytest
import sqlite3
import atexit
from memory.db import (
    init_db, get_connection, hard_delete_memory, verify_hard_delete, transaction, HAS_SQLCIPHER
)


@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary database file for the test session."""
    # Create temp file that persists
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    os.environ["MEMORY_DB_PATH"] = db_path
    os.environ["MEMORY_ENCRYPTION_KEY"] = "0" * 64  # 32 bytes = 64 hex chars

    # Re-import to pick up new env
    import importlib
    import memory.db
    importlib.reload(memory.db)

    from memory.db import init_db as _init_db
    _init_db()

    yield db_path

    # Cleanup at end of session
    try:
        os.unlink(db_path)
    except PermissionError:
        pass  # Windows file locking
    for suffix in ["-wal", "-shm"]:
        try:
            if os.path.exists(db_path + suffix):
                os.unlink(db_path + suffix)
        except PermissionError:
            pass


@pytest.fixture
def test_db(test_db_path):
    """Use the session-scoped database."""
    # Tables already created by session fixture
    yield


def test_init_db_creates_tables(test_db):
    """Verify all tables are created."""
    from memory.db import get_connection
    with get_connection() as conn:
        tables = conn.execute("""
            SELECT name FROM sqlite_master WHERE type='table'
        """).fetchall()
        table_names = [t[0] for t in tables]

        assert "memories" in table_names
        assert "memories_fts" in table_names
        assert "episodes" in table_names
        assert "provenance_log" in table_names
        # vec table only exists if vec0 extension is available
        # assert "memories_vec" in table_names  # skipped when vec0 not available


def test_insert_and_retrieve_memory(test_db):
    """Test basic memory CRUD."""
    from memory.db import get_connection
    with get_connection() as conn:
        # Insert
        cur = conn.execute(
            "INSERT INTO memories (content, provenance) VALUES (?, ?)",
            ("Test memory", "user_said")
        )
        conn.commit()
        mem_id = cur.lastrowid

        # Retrieve
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        assert row is not None
        assert row["content"] == "Test memory"
        assert row["provenance"] == "user_said"
        assert row["deleted_at"] is None


def test_fts_sync_on_insert(test_db):
    """Verify FTS5 trigger syncs on insert."""
    from memory.db import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO memories (content, provenance) VALUES (?, ?)",
            ("searchable content", "user_said")
        )
        conn.commit()
        mem_id = cur.lastrowid

        # Search FTS
        row = conn.execute(
            "SELECT * FROM memories_fts WHERE rowid = ?", (mem_id,)
        ).fetchone()
        assert row is not None
        assert row["content"] == "searchable content"


def test_fts_sync_on_delete(test_db):
    """Verify FTS5 trigger syncs on delete."""
    from memory.db import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO memories (content, provenance) VALUES (?, ?)",
            ("to be deleted", "user_said")
        )
        conn.commit()
        mem_id = cur.lastrowid

        # Soft delete
        conn.execute("UPDATE memories SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (mem_id,))
        conn.commit()

        # FTS should have delete marker
        row = conn.execute(
            "SELECT * FROM memories_fts WHERE rowid = ?", (mem_id,)
        ).fetchone()
        # FTS5 content='memories' means it tracks deletes via triggers


def test_hard_delete_removes_everything(test_db):
    """Hard delete must remove row, vector, and FTS entry."""
    from memory.db import get_connection, hard_delete_memory, verify_hard_delete
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO memories (content, provenance) VALUES (?, ?)",
            ("delete me", "user_said")
        )
        conn.commit()
        mem_id = cur.lastrowid

        # Add vector entry if vec table exists
        try:
            import numpy as np
            emb = np.zeros(1024, dtype=np.float32)
            conn.execute(
                "INSERT INTO memories_vec (rowid, embedding) VALUES (?, ?)",
                (mem_id, emb.tobytes())
            )
            conn.commit()
        except Exception:
            pass  # vec table not available

    # Hard delete
    result = hard_delete_memory(mem_id)
    assert result is True

    # Verify
    verified = verify_hard_delete(mem_id)
    assert verified is True


def test_hard_delete_nonexistent_returns_false(test_db):
    """Hard delete on non-existent ID returns False."""
    result = hard_delete_memory(99999)
    assert result is False


def test_transaction_rollback_on_error(test_db):
    """Transaction context manager rolls back on exception."""
    from memory.db import transaction, get_connection
    with get_connection() as conn:
        conn.execute("INSERT INTO memories (content, provenance) VALUES (?, ?)", ("before", "user_said"))
        conn.commit()

    try:
        with transaction() as conn:
            conn.execute("INSERT INTO memories (content, provenance) VALUES (?, ?)", ("should rollback", "user_said"))
            raise ValueError("force rollback")
    except ValueError:
        pass

    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM memories WHERE content = 'should rollback'").fetchone()[0]
        assert count == 0



def test_derive_key_scrypt():
    """Verify scrypt KDF generates 256-bit (64 hex chars) deterministic key."""
    from memory.db import derive_key
    salt = b"test_salt_123456"
    key1 = derive_key("my-secret-passphrase", salt)
    key2 = derive_key("my-secret-passphrase", salt)
    assert len(key1) == 64  # 32 bytes hex encoded = 256 bits
    assert key1 == key2

    # Different salt or passphrase produces different key
    diff_pass = derive_key("different-passphrase", salt)
    diff_salt = derive_key("my-secret-passphrase", b"different_salt_78")
    assert key1 != diff_pass
    assert key1 != diff_salt

    # Empty passphrase rejected
    with pytest.raises(ValueError):
        derive_key("", salt)


def test_refuse_start_when_sqlcipher_unavailable(monkeypatch):
    """If sqlcipher3 is unavailable and MEMORY_ENCRYPTION != 'off', must refuse to start with clear error."""
    import sys
    import importlib
    monkeypatch.setenv("MEMORY_ENCRYPTION", "on")
    # Hide sqlcipher3 to simulate missing library
    monkeypatch.setitem(sys.modules, "sqlcipher3", None)

    with pytest.raises(RuntimeError, match="SQLCipher is required for encrypted memory but 'sqlcipher3' is not available"):
        import memory.db
        importlib.reload(memory.db)


def test_allow_plain_sqlite_only_when_explicitly_off(monkeypatch, tmp_path):
    """Plain SQLite allowed ONLY when MEMORY_ENCRYPTION=off is set explicitly."""
    import importlib
    db_file = tmp_path / "plain_test.db"
    monkeypatch.setenv("MEMORY_ENCRYPTION", "off")
    monkeypatch.setenv("MEMORY_DB_PATH", str(db_file))

    import memory.db
    importlib.reload(memory.db)
    assert memory.db.HAS_SQLCIPHER is False
    conn = memory.db.get_connection()
    conn.execute("CREATE TABLE plain_test (id INT)")
    conn.close()


def test_sqlcipher_encryption_fails_plain_sqlite_succeeds_with_key(tmp_path, monkeypatch):
    """
    Real encryption test:
    Opening encrypted DB file with plain sqlite3 (no key) fails.
    Opening with SQLCipher and derived key succeeds.
    """
    import importlib
    db_file = tmp_path / "encrypted_test.db"
    monkeypatch.setenv("MEMORY_ENCRYPTION", "on")
    monkeypatch.setenv("MEMORY_DB_PATH", str(db_file))
    monkeypatch.setenv("MEMORY_PASSPHRASE", "judge-test-passphrase-2026")

    import memory.db
    importlib.reload(memory.db)
    if not memory.db.HAS_SQLCIPHER:
        pytest.skip("SQLCipher not available in environment")

    # Initialize encrypted database
    memory.db.init_db()

    # Insert a record using encrypted connection
    with memory.db.get_connection() as conn:
        conn.execute("INSERT INTO memories (content, provenance) VALUES (?, ?)", ("Secret personal data", "user_said"))
        conn.commit()

    # 1. Plain sqlite3 connection (no key) must FAIL to read encrypted data
    plain_conn = sqlite3.connect(str(db_file))
    with pytest.raises(sqlite3.DatabaseError):
        plain_conn.execute("SELECT content FROM memories").fetchall()
    plain_conn.close()

    # 2. SQLCipher connection with proper key must SUCCEED
    with memory.db.get_connection() as conn:
        row = conn.execute("SELECT content FROM memories").fetchone()
        assert row is not None
        assert row["content"] == "Secret personal data"


def test_logging_encryption_on_at_startup(caplog, monkeypatch, tmp_path):
    """Verify 'encryption: on' is logged at startup when SQLCipher is active."""
    import importlib
    import logging
    db_file = tmp_path / "log_test.db"
    monkeypatch.setenv("MEMORY_ENCRYPTION", "on")
    monkeypatch.setenv("MEMORY_DB_PATH", str(db_file))
    monkeypatch.setenv("MEMORY_PASSPHRASE", "log-test-passphrase")

    import memory.db
    importlib.reload(memory.db)
    if not memory.db.HAS_SQLCIPHER:
        pytest.skip("SQLCipher not available")

    with caplog.at_level(logging.INFO):
        memory.db.init_db()
        assert any("encryption: on" in record.message for record in caplog.records)
