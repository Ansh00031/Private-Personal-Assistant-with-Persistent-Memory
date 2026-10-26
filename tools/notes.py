# path: tools/notes.py
"""Notes tool: create, read, update, delete personal notes with 2-step confirmation."""

import re
import json
from typing import Optional
from memory.db import get_connection, transaction
from skills import SkillResult
from tools.actions import registry


def handle_note(user_input: str, context: dict, router) -> SkillResult:
    """Route note operations based on intent."""
    lower = user_input.lower()

    if any(w in lower for w in ["delete", "remove", "trash"]):
        return delete_note(user_input, context, router)
    elif any(w in lower for w in ["update", "edit", "modify", "change note"]):
        return update_note(user_input, context, router)
    elif any(w in lower for w in ["create", "write", "save", "add", "new note", "take note", "remember this note", "note:"]):
        return create_note(user_input, context, router)
    elif any(w in lower for w in ["read", "show", "list", "get notes", "my notes", "view notes"]):
        return read_notes(user_input, context)

    return SkillResult(True, "Note command not recognized. Try: create note, list notes, update note [id], or delete note [id].")


def _extract_id(text: str) -> Optional[int]:
    """Helper to extract an ID from user text."""
    match = re.search(r'#?(\d+)', text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def create_note(user_input: str, context: dict, router) -> SkillResult:
    """Propose note creation (step 1 of 2). Changes nothing until confirmed."""
    content = ""
    if router and hasattr(router, "chat"):
        try:
            prompt = f"Extract the note content from this request. Return only the note text, nothing else.\n\nRequest: {user_input}\n\nNote:"
            extracted, _ = router.chat(
                messages=[{"role": "user", "content": prompt}],
                model="nano",
                temperature=0.1,
                max_tokens=512,
            )
            content = extracted.strip()
        except Exception:
            content = ""

    if not content:
        # Fallback regex extraction
        cleaned = re.sub(r'^(please\s+)?(create|save|add|write down|take)\s+(a\s+)?note(\s*:|\s+that|\s+about)?\s*', '', user_input, flags=re.I)
        content = cleaned.strip()

    if not content:
        return SkillResult(False, "Could not extract note content. Please specify what you would like to note down.")

    # Step 1: Propose action
    def _execute(payload: dict) -> dict:
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO notes (content, created_at, updated_at) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (payload["content"],)
            )
            note_id = cur.lastrowid
            conn.commit()
            return {"note_id": note_id, "content": payload["content"]}

    summary = f"Create note: \"{content[:60]}{'...' if len(content) > 60 else ''}\""
    action = registry.propose(
        tool_name="notes",
        action_type="create",
        summary=summary,
        payload={"content": content},
        execute_fn=_execute,
    )

    return SkillResult(
        success=True,
        output=f"Proposed note creation: \"{content}\". Please confirm to save to your private notes.",
        requires_confirmation=True,
        confirmation_prompt=f"Save note: \"{content[:80]}\"?",
        action_id=action.action_id,
    )


def read_notes(user_input: str, context: dict) -> SkillResult:
    """List recent non-deleted notes. Read operations are direct and require no confirmation."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, content, created_at, updated_at
            FROM notes
            WHERE deleted_at IS NULL
            ORDER BY id DESC LIMIT 25
        """).fetchall()

    if not rows:
        return SkillResult(True, "You have no saved notes.")

    lines = ["Your saved notes:"]
    for r in rows:
        preview = r["content"].replace("\n", " ")
        if len(preview) > 75:
            preview = preview[:72] + "..."
        lines.append(f"  [{r['id']}] {preview} ({r['created_at']})")
    return SkillResult(True, "\n".join(lines))


def update_note(user_input: str, context: dict, router) -> SkillResult:
    """Propose note update (step 1 of 2). Changes nothing until confirmed."""
    note_id = _extract_id(user_input)
    if not note_id:
        return SkillResult(False, "Please specify the ID of the note to update (e.g., 'update note #1 to buy groceries').")

    # Check note exists
    with get_connection() as conn:
        existing = conn.execute("SELECT id, content FROM notes WHERE id = ? AND deleted_at IS NULL", (note_id,)).fetchone()
    if not existing:
        return SkillResult(False, f"Note #{note_id} not found.")

    # Extract new content
    cleaned = re.sub(rf'^.*?(update|edit|modify)\s+note\s+#?{note_id}\s+(to|with)?\s*', '', user_input, flags=re.I).strip()
    new_content = cleaned if cleaned else user_input

    def _execute(payload: dict) -> dict:
        with transaction() as conn:
            conn.execute(
                "UPDATE notes SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload["content"], payload["note_id"])
            )
            conn.commit()
            return {"note_id": payload["note_id"], "updated": True}

    summary = f"Update note #{note_id} to: \"{new_content[:60]}{'...' if len(new_content) > 60 else ''}\""
    action = registry.propose(
        tool_name="notes",
        action_type="update",
        summary=summary,
        payload={"note_id": note_id, "content": new_content},
        execute_fn=_execute,
        target_id=str(note_id),
    )

    return SkillResult(
        success=True,
        output=f"Proposed update to note #{note_id}: \"{new_content}\". Please confirm to apply changes.",
        requires_confirmation=True,
        confirmation_prompt=f"Update note #{note_id} to: \"{new_content[:80]}\"?",
        action_id=action.action_id,
    )


def delete_note(user_input: str, context: dict, router) -> SkillResult:
    """Propose note deletion (step 1 of 2). Changes nothing until confirmed."""
    note_id = _extract_id(user_input)
    if not note_id:
        return SkillResult(False, "Please specify the ID of the note to delete (e.g., 'delete note #2').")

    with get_connection() as conn:
        existing = conn.execute("SELECT id, content FROM notes WHERE id = ? AND deleted_at IS NULL", (note_id,)).fetchone()
    if not existing:
        return SkillResult(False, f"Note #{note_id} not found or already deleted.")

    note_preview = existing["content"][:40]

    def _execute(payload: dict) -> dict:
        with transaction() as conn:
            conn.execute(
                "UPDATE notes SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload["note_id"],)
            )
            conn.commit()
            return {"note_id": payload["note_id"], "deleted": True}

    summary = f"Delete note #{note_id} (\"{note_preview}\")"
    action = registry.propose(
        tool_name="notes",
        action_type="delete",
        summary=summary,
        payload={"note_id": note_id},
        execute_fn=_execute,
        target_id=str(note_id),
    )

    return SkillResult(
        success=True,
        output=f"Proposed deleting note #{note_id} (\"{note_preview}\"). Please confirm.",
        requires_confirmation=True,
        confirmation_prompt=f"Delete note #{note_id} (\"{note_preview}\") permanently?",
        action_id=action.action_id,
    )
