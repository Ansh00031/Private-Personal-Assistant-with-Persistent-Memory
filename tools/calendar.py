# path: tools/calendar.py
"""Calendar tool: manage personal events with 2-step confirmation."""

import re
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from memory.db import get_connection, transaction
from skills import SkillResult
from tools.actions import registry


def handle_calendar(user_input: str, context: dict, router) -> SkillResult:
    """Route calendar operations."""
    lower = user_input.lower()

    if any(w in lower for w in ["delete", "remove", "cancel meeting", "cancel event"]):
        return delete_event(user_input, context, router)
    elif any(w in lower for w in ["update", "edit", "reschedule", "modify event"]):
        return update_event(user_input, context, router)
    elif any(w in lower for w in ["create", "add", "schedule", "new event", "new meeting", "set appointment"]):
        return create_event(user_input, context, router)
    elif any(w in lower for w in ["read", "show", "list", "upcoming", "today", "my calendar", "my schedule", "events"]):
        return list_events(user_input)

    return SkillResult(True, "Calendar command not recognized. Try: schedule [event], list events, reschedule [id], or cancel [id].")


def _extract_id(text: str) -> Optional[int]:
    """Helper to extract an ID from user text."""
    match = re.search(r'#?(\d+)', text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def create_event(user_input: str, context: dict, router) -> SkillResult:
    """Propose calendar event creation (step 1 of 2). Changes nothing until confirmed."""
    title = ""
    start_time = ""
    description = ""

    # Parse details with nano model if available
    if router and hasattr(router, "chat"):
        try:
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
            prompt = (
                f"Current time is {now_iso}. Extract calendar event details as JSON from this request:\n"
                f"Request: {user_input}\n\n"
                f"Respond with JSON ONLY in this exact format:\n"
                f'{{"title": "meeting title", "start_time": "YYYY-MM-DD HH:MM:SS", "description": "optional notes"}}'
            )
            resp, _ = router.chat(
                messages=[{"role": "user", "content": prompt}],
                model="nano",
                temperature=0.1,
                max_tokens=300,
            )
            # Find JSON block
            m = re.search(r'\{.*\}', resp, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                title = data.get("title", "").strip()
                start_time = data.get("start_time", "").strip()
                description = data.get("description", "").strip()
        except Exception:
            pass

    if not title:
        # Fallback simple parsing
        cleaned = re.sub(r'^(schedule|add|create|set)\s+(a\s+)?(meeting|event|appointment)\s*', '', user_input, flags=re.I)
        title = cleaned.strip() or "Calendar Event"

    if not start_time:
        # Default start time: tomorrow at 10:00 AM
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.strftime("%Y-%m-%d 10:00:00")

    def _execute(payload: dict) -> dict:
        with transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO events (title, start_time, end_time, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (payload["title"], payload["start_time"], payload.get("end_time"), payload.get("description", ""))
            )
            event_id = cur.lastrowid
            conn.commit()
            return {"event_id": event_id, "title": payload["title"], "start_time": payload["start_time"]}

    summary = f"Schedule event: \"{title}\" at {start_time}"
    action = registry.propose(
        tool_name="calendar",
        action_type="create",
        summary=summary,
        payload={"title": title, "start_time": start_time, "description": description},
        execute_fn=_execute,
    )

    return SkillResult(
        success=True,
        output=f"Proposed scheduling event: \"{title}\" at {start_time}. Please confirm to add to your calendar.",
        requires_confirmation=True,
        confirmation_prompt=f"Add event \"{title}\" on {start_time} to your calendar?",
        action_id=action.action_id,
    )


def list_events(user_input: str) -> SkillResult:
    """List upcoming active calendar events. Read operations are direct."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, start_time, end_time, description
            FROM events
            WHERE deleted_at IS NULL
            ORDER BY start_time ASC LIMIT 25
        """).fetchall()

    if not rows:
        return SkillResult(True, "Your calendar has no scheduled events.")

    lines = ["Your scheduled events:"]
    for r in rows:
        desc = f" - {r['description']}" if r["description"] else ""
        lines.append(f"  [{r['id']}] {r['title']} at {r['start_time']}{desc}")
    return SkillResult(True, "\n".join(lines))


def update_event(user_input: str, context: dict, router) -> SkillResult:
    """Propose updating a calendar event (step 1 of 2). Changes nothing until confirmed."""
    event_id = _extract_id(user_input)
    if not event_id:
        return SkillResult(False, "Please specify the ID of the event to reschedule/update (e.g. 'reschedule event #1 to Friday at 3pm').")

    with get_connection() as conn:
        existing = conn.execute("SELECT id, title, start_time FROM events WHERE id = ? AND deleted_at IS NULL", (event_id,)).fetchone()
    if not existing:
        return SkillResult(False, f"Event #{event_id} not found.")

    new_time = None
    # Extract date/time if specified
    m = re.search(r'\b(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)\b', user_input)
    if m:
        new_time = m.group(1)
        if len(new_time) == 10:
            new_time += " 10:00:00"
    else:
        new_time = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 14:00:00")

    def _execute(payload: dict) -> dict:
        with transaction() as conn:
            conn.execute(
                "UPDATE events SET start_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload["start_time"], payload["event_id"])
            )
            conn.commit()
            return {"event_id": payload["event_id"], "updated": True, "start_time": payload["start_time"]}

    summary = f"Reschedule event #{event_id} (\"{existing['title']}\") to {new_time}"
    action = registry.propose(
        tool_name="calendar",
        action_type="update",
        summary=summary,
        payload={"event_id": event_id, "start_time": new_time},
        execute_fn=_execute,
        target_id=str(event_id),
    )

    return SkillResult(
        success=True,
        output=f"Proposed rescheduling event #{event_id} (\"{existing['title']}\") to {new_time}. Please confirm.",
        requires_confirmation=True,
        confirmation_prompt=f"Reschedule event #{event_id} to {new_time}?",
        action_id=action.action_id,
    )


def delete_event(user_input: str, context: dict, router) -> SkillResult:
    """Propose cancelling/deleting a calendar event (step 1 of 2). Changes nothing until confirmed."""
    event_id = _extract_id(user_input)
    if not event_id:
        return SkillResult(False, "Please specify the ID of the event to cancel (e.g. 'cancel event #3').")

    with get_connection() as conn:
        existing = conn.execute("SELECT id, title, start_time FROM events WHERE id = ? AND deleted_at IS NULL", (event_id,)).fetchone()
    if not existing:
        return SkillResult(False, f"Event #{event_id} not found or already cancelled.")

    event_title = existing["title"]
    event_time = existing["start_time"]

    def _execute(payload: dict) -> dict:
        with transaction() as conn:
            conn.execute(
                "UPDATE events SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload["event_id"],)
            )
            conn.commit()
            return {"event_id": payload["event_id"], "cancelled": True}

    summary = f"Cancel event #{event_id} (\"{event_title}\" on {event_time})"
    action = registry.propose(
        tool_name="calendar",
        action_type="delete",
        summary=summary,
        payload={"event_id": event_id},
        execute_fn=_execute,
        target_id=str(event_id),
    )

    return SkillResult(
        success=True,
        output=f"Proposed cancelling event #{event_id} (\"{event_title}\" on {event_time}). Please confirm.",
        requires_confirmation=True,
        confirmation_prompt=f"Cancel event #{event_id} (\"{event_title}\") permanently?",
        action_id=action.action_id,
    )
