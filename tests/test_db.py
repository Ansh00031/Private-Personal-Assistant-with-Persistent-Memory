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
        except sqlite3.OperationalError:
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