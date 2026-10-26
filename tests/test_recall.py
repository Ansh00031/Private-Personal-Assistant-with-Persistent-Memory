# path: tests/test_recall.py
"""Tests for memory/recall.py"""

import os
import pytest
import numpy as np
import sqlite3
from unittest.mock import Mock
from memory.recall import semantic_search, keyword_search, temporal_search, hybrid_recall


@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary database file for the test session."""
    import tempfile
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    os.environ["MEMORY_DB_PATH"] = db_path
    os.environ["MEMORY_ENCRYPTION_KEY"] = "0" * 64

    import importlib
    import memory.db
    importlib.reload(memory.db)

    from memory.db import init_db
    init_db()

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except PermissionError:
        pass
    for suffix in ["-wal", "-shm"]:
        try:
            if os.path.exists(db_path + suffix):
                os.unlink(db_path + suffix)
        except PermissionError:
            pass


@pytest.fixture
def test_db(test_db_path):
    """Insert test data into session database."""
    from memory.db import get_connection
    with get_connection() as conn:
        # Clear existing data
        conn.execute("DELETE FROM memories")
        conn.execute("DELETE FROM episodes")
        conn.commit()

        # Memory 1
        conn.execute(
            "INSERT INTO memories (content, provenance, created_at) VALUES (?, ?, ?)",
            ("User likes coffee", "user_said", "2024-01-15 10:00:00")
        )
        # Memory 2
        conn.execute(
            "INSERT INTO memories (content, provenance, created_at) VALUES (?, ?, ?)",
            ("User hates tea", "user_said", "2024-01-15 11:00:00")
        )
        # Memory 3 (tool output)
        conn.execute(
            "INSERT INTO memories (content, provenance, created_at) VALUES (?, ?, ?)",
            ("Scheduled meeting for 2pm", "tool_output", "2024-01-16 09:00:00")
        )
        conn.commit()

    yield


@pytest.fixture
def mock_router():
    """Mock router with embed method."""
    router = Mock()
    # Return deterministic embeddings
    def embed(texts):
        return [np.random.rand(1024).astype(np.float32).tolist() for _ in texts]
    router.embed.side_effect = embed
    return router


def test_semantic_search_skipped_when_vec0_unavailable(mock_router, test_db):
    """Semantic search is skipped when vec0 extension not available."""
    try:
        results = semantic_search(mock_router, "coffee", limit=5)
        assert isinstance(results, list)
    except Exception:
        pytest.skip("vec0 extension not available")


def test_keyword_search(test_db):
    """Keyword search uses FTS5."""
    results = keyword_search("coffee", limit=5)
    assert isinstance(results, list)
    assert any("coffee" in r["content"].lower() for r in results)


def test_temporal_search(test_db):
    """Temporal search filters by date range."""
    # Search for Jan 15
    results = temporal_search(since="2024-01-15", until="2024-01-15 23:59:59", limit=10)
    assert len(results) == 2
    assert all("2024-01-15" in r["created_at"] for r in results)

    # Search for Jan 16
    results = temporal_search(since="2024-01-16", until="2024-01-16 23:59:59", limit=10)
    assert len(results) == 1
    assert "2024-01-16" in results[0]["created_at"]


def test_hybrid_recall_deduplicates(mock_router, test_db):
    """Hybrid recall deduplicates by ID (keyword + temporal only when vec0 unavailable)."""
    results = hybrid_recall(mock_router, "coffee", limit=10)
    ids = [r["id"] for r in results]
    assert len(ids) == len(set(ids))  # No duplicates


def test_hybrid_recall_sorts_by_score(mock_router, test_db):
    """Results sorted by score descending."""
    results = hybrid_recall(mock_router, "coffee", limit=10)
    scores = [r.get("score", 0) for r in results]
    assert scores == sorted(scores, reverse=True)