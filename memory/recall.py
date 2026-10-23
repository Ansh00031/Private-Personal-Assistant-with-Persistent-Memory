# path: memory/recall.py
"""Memory retrieval: semantic + keyword + temporal."""

from llm import ModelRouter
from memory.db import get_connection, DB_OperationalError
from typing import Optional
import numpy as np
import sqlite3


def semantic_search(
    router: ModelRouter,
    query: str,
    limit: int = 10,
    min_score: float = 0.7
) -> list[dict]:
    """Vector similarity search using sqlite-vec."""
    query_emb = router.embed([query])[0]
    # Convert to bytes for vec0
    emb_bytes = np.array(query_emb, dtype=np.float32).tobytes()

    with get_connection() as conn:
        try:
            rows = conn.execute("""
                SELECT m.id, m.content, m.provenance, m.created_at,
                       vec_distance_cosine(mv.embedding, ?) as distance
                FROM memories_vec mv
                JOIN memories m ON m.id = mv.rowid
                WHERE m.deleted_at IS NULL
                ORDER BY distance ASC
                LIMIT ?
            """, (emb_bytes, limit)).fetchall()
        except (DB_OperationalError, sqlite3.OperationalError):
            return []  # vec0 extension not available

    results = []
    for r in rows:
        score = 1.0 - r["distance"]
        if score >= min_score:
            results.append({
                "id": r["id"],
                "content": r["content"],
                "provenance": r["provenance"],
                "created_at": r["created_at"],
                "score": score,
            })
    return results


import re
import logging
logger = logging.getLogger(__name__)

def _escape_fts5(query: str) -> str:
    """Escape and format natural language query safely for FTS5 MATCH."""
    tokens = re.findall(r'\w+', query)
    if not tokens:
        return ""
    return " ".join(f'"{token}"' for token in tokens)


def keyword_search(query: str, limit: int = 10) -> list[dict]:
    """FTS5 full-text search."""
    safe_query = _escape_fts5(query)
    if not safe_query.strip():
        return []
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT m.id, m.content, m.provenance, m.created_at,
                       bm25(memories_fts) as rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ? AND m.deleted_at IS NULL
                ORDER BY rank ASC
                LIMIT ?
            """, (safe_query, limit)).fetchall()
        return [dict(r) for r in rows]
    except (DB_OperationalError, sqlite3.OperationalError) as e:
        logger.warning(f"FTS5 keyword search query error: {e}")
        return []


def temporal_search(
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 20
) -> list[dict]:
    """Retrieve memories by time range."""
    conditions = ["m.deleted_at IS NULL"]
    params = []

    if since:
        conditions.append("m.created_at >= ?")
        params.append(since)
    if until:
        conditions.append("m.created_at <= ?")
        params.append(until)

    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, content, provenance, created_at
            FROM memories m
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT ?
        """, params).fetchall()

    return [dict(r) for r in rows]


def hybrid_recall(
    router: ModelRouter,
    query: str,
    limit: int = 10,
    since: Optional[str] = None,
    until: Optional[str] = None
) -> list[dict]:
    """Combine semantic + keyword + temporal, deduplicate by ID."""
    sem = semantic_search(router, query, limit * 2)
    kw = keyword_search(query, limit * 2)
    temp = temporal_search(since, until, limit) if since or until else []

    # Merge by ID, prefer highest score
    merged = {}
    for r in sem:
        merged[r["id"]] = {**r, "source": "semantic"}
    for r in kw:
        if r["id"] in merged:
            merged[r["id"]]["source"] = "hybrid"
        else:
            merged[r["id"]] = {**r, "source": "keyword"}
    for r in temp:
        if r["id"] not in merged:
            merged[r["id"]] = {**r, "source": "temporal", "score": 0.5}

    # Sort by score desc
    results = sorted(merged.values(), key=lambda x: x.get("score", 0), reverse=True)
    return results[:limit]