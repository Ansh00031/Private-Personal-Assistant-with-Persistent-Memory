# path: tests/test_tools.py
"""Tests for Task 3: 2-step tool confirmation, real notes/calendar CRUD, sandbox, and audit log."""

import time
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient

from memory.db import init_db, get_connection
from tools.actions import registry, log_tool_audit
from tools.notes import handle_note, create_note, read_notes, update_note, delete_note
from tools.calendar import handle_calendar, create_event, list_events, update_event, delete_event
from tools.sandbox import run_tool, ToolAdapter, set_adapter, StubAdapter
import app


@pytest.fixture(autouse=True)
def clean_state():
    """Ensure DB and action registry are initialized and clean for each test."""
    init_db()
    registry.clear()
    with get_connection() as conn:
        conn.execute("DELETE FROM notes")
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM tool_audit_log")
        conn.commit()
    yield
    registry.clear()
    set_adapter(StubAdapter())


@pytest.fixture
def mock_router():
    router = Mock()
    router.chat.return_value = ("Buy almond milk and eggs", "nano")
    return router


def test_notes_unconfirmed_write_changes_nothing(mock_router):
    """An unconfirmed note create proposals must change nothing in database."""
    res = create_note("create note Buy groceries tomorrow", {}, mock_router)
    assert res.requires_confirmation is True
    assert res.action_id is not None

    # Database must still have 0 notes
    with get_connection() as conn:
        count = conn.execute("SELECT count(*) FROM notes WHERE deleted_at IS NULL").fetchone()[0]
        assert count == 0


def test_notes_confirmed_create_update_delete(mock_router):
    """Confirmed create, update, and delete must properly modify notes table."""
    # 1. Propose Create
    res_create = create_note("create note Important meeting ideas", {}, mock_router)
    assert res_create.requires_confirmation is True
    action_id = res_create.action_id

    # Confirm
    confirm_res = registry.confirm(action_id)
    assert confirm_res["success"] is True
    note_id = confirm_res["result"]["note_id"]

    # Verify in DB
    with get_connection() as conn:
        row = conn.execute("SELECT content FROM notes WHERE id = ?", (note_id,)).fetchone()
        assert row is not None
        assert "Buy almond milk and eggs" in row["content"]

    # 2. Propose Update
    mock_router.chat.return_value = ("Updated meeting agenda", "nano")
    res_update = update_note(f"update note #{note_id} to Revised project roadmap", {}, mock_router)
    assert res_update.requires_confirmation is True
    update_act_id = res_update.action_id

    # Unconfirmed -> DB still has old content
    with get_connection() as conn:
        row = conn.execute("SELECT content FROM notes WHERE id = ?", (note_id,)).fetchone()
        assert "Buy almond milk and eggs" in row["content"]

    # Confirm Update
    registry.confirm(update_act_id)
    with get_connection() as conn:
        row = conn.execute("SELECT content FROM notes WHERE id = ?", (note_id,)).fetchone()
        assert "Revised project roadmap" in row["content"]

    # 3. Read notes
    read_res = read_notes("list notes", {})
    assert f"[{note_id}]" in read_res.output
    assert "Revised project roadmap" in read_res.output

    # 4. Propose Delete
    res_delete = delete_note(f"delete note #{note_id}", {}, mock_router)
    assert res_delete.requires_confirmation is True
    del_act_id = res_delete.action_id

    # Unconfirmed -> still not deleted
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM notes WHERE id = ? AND deleted_at IS NULL", (note_id,)).fetchone()
        assert row is not None

    # Confirm Delete
    registry.confirm(del_act_id)
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM notes WHERE id = ? AND deleted_at IS NULL", (note_id,)).fetchone()
        assert row is None


def test_calendar_unconfirmed_and_confirmed_crud(mock_router):
    """Calendar events require confirmation; unconfirmed changes nothing, confirmed writes work."""
    # 1. Propose event
    res_create = create_event("schedule Project demo with judges", {}, mock_router)
    assert res_create.requires_confirmation is True
    action_id = res_create.action_id

    # Unconfirmed -> 0 events
    with get_connection() as conn:
        assert conn.execute("SELECT count(*) FROM events WHERE deleted_at IS NULL").fetchone()[0] == 0

    # Confirm event
    conf_res = registry.confirm(action_id)
    assert conf_res["success"] is True
    event_id = conf_res["result"]["event_id"]

    with get_connection() as conn:
        row = conn.execute("SELECT title, start_time FROM events WHERE id = ?", (event_id,)).fetchone()
        assert row is not None
        assert "Project demo" in row["title"]

    # List events
    list_res = list_events("show upcoming events")
    assert f"[{event_id}]" in list_res.output

    # 2. Reschedule
    res_update = update_event(f"reschedule event #{event_id} to 2026-10-28 14:00:00", {}, mock_router)
    assert res_update.requires_confirmation is True
    registry.confirm(res_update.action_id)

    with get_connection() as conn:
        row = conn.execute("SELECT start_time FROM events WHERE id = ?", (event_id,)).fetchone()
        assert "2026-10-28 14:00:00" in row["start_time"]

    # 3. Delete event
    res_del = delete_event(f"cancel event #{event_id}", {}, mock_router)
    assert res_del.requires_confirmation is True
    registry.confirm(res_del.action_id)

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM events WHERE id = ? AND deleted_at IS NULL", (event_id,)).fetchone()
        assert row is None


def test_actions_expired_rejected():
    """Actions past expiration cannot be confirmed."""
    def dummy_exec(p):
        return {"done": True}

    action = registry.propose("test_tool", "test_op", "Test operation", {}, dummy_exec, ttl_seconds=0.01)
    time.sleep(0.03)

    with pytest.raises(ValueError, match="expired"):
        registry.confirm(action.action_id)


def test_actions_repeated_confirmation_rejected():
    """An action cannot be confirmed twice."""
    called_count = 0
    def dummy_exec(p):
        nonlocal called_count
        called_count += 1
        return {"done": True}

    action = registry.propose("test_tool", "write", "Dummy write", {}, dummy_exec)
    res1 = registry.confirm(action.action_id)
    assert res1["success"] is True
    assert called_count == 1

    # Second confirmation must be rejected
    with pytest.raises(ValueError, match="already been confirmed"):
        registry.confirm(action.action_id)
    assert called_count == 1


def test_actions_cancelled_cannot_be_confirmed():
    """A cancelled action cannot be confirmed."""
    def dummy_exec(p):
        return {"done": True}

    action = registry.propose("test_tool", "delete", "Dummy delete", {}, dummy_exec)
    cancel_res = registry.cancel(action.action_id)
    assert cancel_res["status"] == "cancelled"

    with pytest.raises(ValueError, match="cancelled"):
        registry.confirm(action.action_id)


def test_tool_audit_log_records_metadata_without_sensitive_content():
    """tool_audit_log records tool_name, action, target_id, status but no sensitive contents."""
    log_tool_audit("notes", "propose_create", "note_123", "proposed")
    log_tool_audit("calendar", "confirm_delete", "event_456", "executed")

    with get_connection() as conn:
        rows = conn.execute("SELECT tool_name, action, target_id, status FROM tool_audit_log ORDER BY id ASC").fetchall()
        assert len(rows) == 2
        assert rows[0]["tool_name"] == "notes"
        assert rows[0]["action"] == "propose_create"
        assert rows[0]["target_id"] == "note_123"
        assert rows[0]["status"] == "proposed"

        assert rows[1]["tool_name"] == "calendar"
        assert rows[1]["action"] == "confirm_delete"
        assert rows[1]["target_id"] == "event_456"
        assert rows[1]["status"] == "executed"


def test_run_tool_path_traversal_blocked_and_timeout():
    """run_tool blocks path traversal outside sandbox and enforces timeouts."""
    # 1. Path traversal attempt blocked
    res_blocked = run_tool("files", {"path": "../../etc/passwd"})
    assert res_blocked["status"] == "error"
    assert "Path traversal blocked" in res_blocked["message"]

    # 2. Timeout enforcement
    class SlowToolAdapter(ToolAdapter):
        def run_tool(self, name: str, args: dict) -> dict:
            time.sleep(0.5)
            return {"done": True}

    set_adapter(SlowToolAdapter())
    res_timeout = run_tool("slow_tool", {}, timeout=0.05)
    assert res_timeout["status"] == "error"
    assert "timed out after" in res_timeout["message"]


def test_action_endpoints_via_api():
    """Test full HTTP API flow: propose -> confirm / cancel via /actions endpoints."""
    client = TestClient(app.app)

    # 1. Direct propose and confirm via API
    def dummy_exec(p):
        return {"created": True, "value": p.get("val")}

    action = registry.propose("api_test", "create", "API Test Action", {"val": 42}, dummy_exec)
    act_id = action.action_id

    # Confirm via POST /actions/{id}/confirm
    resp = client.post(f"/actions/{act_id}/confirm")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["action_id"] == act_id

    # Confirming again -> 400 Bad Request
    resp_again = client.post(f"/actions/{act_id}/confirm")
    assert resp_again.status_code == 400
    assert "already been confirmed" in resp_again.json()["detail"]

    # 2. Propose and Cancel via API
    action2 = registry.propose("api_test", "delete", "API Delete Action", {}, dummy_exec)
    act_id2 = action2.action_id

    resp_cancel = client.post(f"/actions/{act_id2}/cancel")
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "cancelled"

    # 3. Check tool audit log endpoint
    resp_audit = client.get("/tool-audit-log")
    assert resp_audit.status_code == 200
    audit_list = resp_audit.json()
    assert isinstance(audit_list, list)
    assert len(audit_list) > 0
