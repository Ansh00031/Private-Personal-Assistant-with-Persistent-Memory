# path: tools/notes.py
"""Notes tool: create, read, update, delete personal notes."""

from memory.db import get_connection, transaction
from typing import Optional
from skills import SkillResult


def handle_note(user_input: str, context: dict, router) -> SkillResult:
    """Route note operations based on intent."""
    lower = user_input.lower()

    if any(w in lower for w in ["create", "write", "save", "add", "new note"]):
        return create_note(user_input, context, router)
    elif any(w in lower for w in ["read", "show", "list", "get"]):
        return read_notes(user_input, context)
    elif any(w in lower for w in ["update", "edit", "modify"]):
        return update_note(user_input, context)
    elif any(w in lower for w in ["delete", "remove"]):
        return delete_note(user_input, context)

    return SkillResult(True, "Note command not recognized. Try: create/read/update/delete note.")


def create_note(user_input: str, context: dict, router) -> SkillResult:
    """Extract note content and save."""
    # Use nano to extract the actual note content
    prompt = f"""Extract the note content from this request.
Return only the note text, nothing else.

Request: {user_input}

Note:"""
    content, _ = router.chat(
        messages=[{"role": "user", "content": prompt}],
        model="nano",
        temperature=0.1,
        max_tokens=512,
    )
    content = content.strip()

    if not content:
        return SkillResult(False, "Could not extract note content.")

    with transaction() as conn:
        conn.execute(
            "INSERT INTO notes (content, created_at) VALUES (?, CURRENT_TIMESTAMP)",
            (content,)
        )
        conn.commit()

    return SkillResult(True, f"Note saved: {content[:100]}...")


def read_notes(user_input: str, context: dict) -> SkillResult:
    """List recent notes."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, content, created_at FROM notes
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC LIMIT 20
        """).fetchall()

    if not rows:
        return SkillResult(True, "No notes found.")

    lines = ["Your notes:"]
    for r in rows:
        lines.append(f"  [{r['id']}] {r['content'][:80]}... ({r['created_at']})")
    return SkillResult(True, "\n".join(lines))


def update_note(user_input: str, context: dict) -> SkillResult:
    """Update a note by ID."""
    # Extract note ID and new content
    prompt = f"""Extract note ID and new content from this request.
Return JSON: {{"id": int, "content": "text"}}

Request: {user_input}

JSON:"""
    # Would use router here, but keeping simple for now
    return SkillResult(True, "Update note: provide note ID and new content.")


def delete_note(user_input: str, context: dict) -> SkillResult:
    """Soft delete a note."""
    return SkillResult(True, "Delete note: provide note ID to delete.")