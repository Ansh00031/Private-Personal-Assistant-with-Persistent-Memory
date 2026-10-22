# path: tools/calendar.py
"""Calendar tool: manage events (stubbed, requires confirmation for writes)."""

from memory.db import get_connection, transaction
from typing import Optional
from skills import SkillResult
from datetime import datetime


def handle_calendar(user_input: str, context: dict, router) -> SkillResult:
    """Route calendar operations."""
    lower = user_input.lower()

    if any(w in lower for w in ["create", "add", "schedule", "new event"]):
        return create_event(user_input, context, router)
    elif any(w in lower for w in ["read", "show", "list", "upcoming", "today"]):
        return list_events(user_input)
    elif any(w in lower for w in ["update", "edit", "modify", "reschedule"]):
        return update_event(user_input)
    elif any(w in lower for w in ["delete", "remove", "cancel"]):
        return delete_event(user_input)

    return SkillResult(True, "Calendar command not recognized. Try: create/read/update/delete event.")


def create_event(user_input: str, context: dict, router) -> SkillResult:
    """Extract event details and create (requires confirmation)."""
    prompt = f"""Extract event details from this request.
Return JSON: {{
  "title": "event title",
  "start": "ISO datetime",
  "end": "ISO datetime",
  "description": "optional"
}}

Request: {user_input}

JSON:"""
    # Would use router to extract, returning stub for now
    return SkillResult(
        True,
        "Event creation requires: title, start time, end time. This requires confirmation.",
        requires_confirmation=True,
        confirmation_prompt="Create this calendar event?"
    )


def list_events(user_input: str) -> SkillResult:
    """List upcoming events."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, start_time, end_time, description
            FROM events
            WHERE deleted_at IS NULL AND start_time >= datetime('now')
            ORDER BY start_time ASC LIMIT 20
        """).fetchall()

    if not rows:
        return SkillResult(True, "No upcoming events.")

    lines = ["Upcoming events:"]
    for r in rows:
        start = r["start_time"]
        lines.append(f"  [{r['id']}] {r['title']} at {start}")
        if r["description"]:
            lines.append(f"      {r['description']}")
    return SkillResult(True, "\n".join(lines))


def update_event(user_input: str) -> SkillResult:
    """Update an event (requires confirmation)."""
    return SkillResult(
        True,
        "Update event: provide event ID and new details. Requires confirmation.",
        requires_confirmation=True,
        confirmation_prompt="Update this event?"
    )


def delete_event(user_input: str) -> SkillResult:
    """Delete an event (requires confirmation)."""
    return SkillResult(
        True,
        "Delete event: provide event ID. Requires confirmation.",
        requires_confirmation=True,
        confirmation_prompt="Delete this event permanently?"
    )