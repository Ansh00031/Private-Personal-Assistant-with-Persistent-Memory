# path: memory/extract.py
"""Post-chat fact/episode extraction using LLM."""

from llm import ModelRouter
from memory.db import get_connection, transaction
from typing import Optional
import json


EXTRACTION_PROMPT = """Extract key facts and episodes from this conversation turn.
Return JSON with:
- facts: list of {{"fact": "extracted fact", "confidence": 0.0-1.0}}
- episodes: list of {{"summary": "episode summary", "memory_ids": [ids]}}

Only extract concrete, verifiable information the user explicitly stated.
Ignore greetings, meta-talk, and hypotheticals.

Conversation:
{conversation}

JSON:"""


def extract_facts_and_episodes(
    router: ModelRouter,
    conversation: str,
    memory_ids: list[int]
) -> dict:
    """Extract structured facts/episodes from conversation using nano model."""
    prompt = EXTRACTION_PROMPT.format(conversation=conversation)
    resp, _ = router.chat(
        messages=[{"role": "user", "content": prompt}],
        model="nano",
        temperature=0.1,
        max_tokens=1024,
    )

    try:
        data = json.loads(resp)
    except json.JSONDecodeError:
        return {"facts": [], "episodes": []}

    # Validate and store
    with transaction() as conn:
        for item in data.get("facts", []):
            fact = item.get("fact", "").strip()
            conf = float(item.get("confidence", 1.0))
            if fact:
                conn.execute(
                    "INSERT INTO episodes (fact, memory_id, confidence) VALUES (?, ?, ?)",
                    (fact, memory_ids[0] if memory_ids else None, conf)
                )

        for ep in data.get("episodes", []):
            summary = ep.get("summary", "").strip()
            mids = ep.get("memory_ids", [])
            if summary and mids:
                for mid in mids:
                    conn.execute(
                        "INSERT INTO episodes (fact, memory_id, confidence) VALUES (?, ?, ?)",
                        (summary, mid, 0.9)
                    )

        conn.commit()

    return data


def get_recent_episodes(limit: int = 50) -> list[dict]:
    """Retrieve recent episodes for context injection."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT fact, confidence, created_at FROM episodes
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]