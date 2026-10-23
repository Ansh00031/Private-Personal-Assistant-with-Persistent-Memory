# path: tests/test_chat_smoke.py
"""Smoke test for the chat endpoint, including multi-turn history and morning brief."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from memory.db import init_db
import app


def test_chat_smoke_nano():
    """Post a message to /chat with LLM client stubbed (nano) and assert 200 with reply."""
    init_db()
    client = TestClient(app.app)

    mock_chat_resp = Mock()
    mock_chat_resp.choices = [Mock(message=Mock(content="Hello, I am your assistant!"))]

    mock_emb_resp = Mock()
    mock_emb_resp.data = [Mock(embedding=[0.05] * 1024)]

    with patch.object(app.router.client.chat.completions, "create", return_value=mock_chat_resp), \
         patch.object(app.router.client.embeddings, "create", return_value=mock_emb_resp):
        response = client.post("/chat", json={"message": "Hello assistant", "model": "nano"})
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello, I am your assistant!"
        assert data["model_used"] == "nano"
        assert "memories_retrieved" in data


def test_chat_smoke_ultra():
    """Post a message to /chat with LLM client stubbed (ultra) and assert 200 with reply."""
    init_db()
    client = TestClient(app.app)

    mock_chat_resp = Mock()
    mock_chat_resp.choices = [Mock(message=Mock(content="Ultra response here."))]

    mock_emb_resp = Mock()
    mock_emb_resp.data = [Mock(embedding=[0.05] * 1024)]

    with patch.object(app.router.client.chat.completions, "create", return_value=mock_chat_resp), \
         patch.object(app.router.client.embeddings, "create", return_value=mock_emb_resp):
        response = client.post("/chat", json={"message": "Deep question", "model": "ultra"})
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Ultra response here."
        assert data["model_used"] == "ultra"


def test_chat_multi_turn_history():
    """Verify that multi-turn history sent in request is forwarded to the LLM context."""
    init_db()
    client = TestClient(app.app)

    mock_chat_resp = Mock()
    mock_chat_resp.choices = [Mock(message=Mock(content="Certainly! Updated timetable is below."))]

    mock_emb_resp = Mock()
    mock_emb_resp.data = [Mock(embedding=[0.05] * 1024)]

    with patch.object(app.router.client.chat.completions, "create", return_value=mock_chat_resp) as mock_create, \
         patch.object(app.router.client.embeddings, "create", return_value=mock_emb_resp):
        history = [
            {"role": "user", "content": "Make my timetable for college 9am to 4pm"},
            {"role": "assistant", "content": "| Time | Activity |\n|---|---|\n| 9:00 - 10:00 | Math |"}
        ]
        response = client.post("/chat", json={
            "message": "Add biology class at 2pm",
            "model": "nano",
            "history": history
        })
        assert response.status_code == 200
        assert response.json()["response"] == "Certainly! Updated timetable is below."

        # The first call to completions.create is the chat router call
        chat_call = mock_create.call_args_list[0]
        call_kwargs = chat_call[1] if chat_call[1] else chat_call.kwargs
        messages_sent = call_kwargs.get("messages", [])

        # Check that user's previous turn and assistant's previous turn are in the sent messages
        roles_contents = [(m["role"], m["content"]) for m in messages_sent]
        assert ("user", "Make my timetable for college 9am to 4pm") in roles_contents
        assert ("assistant", "| Time | Activity |\n|---|---|\n| 9:00 - 10:00 | Math |") in roles_contents
        assert ("user", "Add biology class at 2pm") in roles_contents


def test_morning_brief_endpoint():
    """Verify that POST /morning-brief generates a brief response successfully."""
    init_db()
    client = TestClient(app.app)

    mock_chat_resp = Mock()
    mock_chat_resp.choices = [Mock(message=Mock(content="Good morning! Here is your daily summary."))]

    mock_emb_resp = Mock()
    mock_emb_resp.data = [Mock(embedding=[0.05] * 1024)]

    with patch.object(app.router.client.chat.completions, "create", return_value=mock_chat_resp), \
         patch.object(app.router.client.embeddings, "create", return_value=mock_emb_resp):
        response = client.post("/morning-brief")
        assert response.status_code == 200
        data = response.json()
        assert "brief" in data
        assert data["brief"].startswith("Good morning!")
        assert data["model_used"] == "nano"

def test_health_endpoint():
    """Verify that GET /health returns structured operational health metadata."""
    init_db()
    client = TestClient(app.app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "encryption" in data
    assert "models" in data
    assert "nano" in data["models"]
    assert "ultra" in data["models"]
    assert "daily_cost_usd" in data
    assert "daily_cost_cap_usd" in data


def test_chat_rate_limiting():
    """Verify that exceeding RATE_LIMIT_RPM returns HTTP 429."""
    init_db()
    client = TestClient(app.app)
    original_rpm = app.RATE_LIMIT_RPM
    app.RATE_LIMIT_RPM = 2
    app._request_counts.clear()

    mock_chat_resp = Mock()
    mock_chat_resp.choices = [Mock(message=Mock(content="ok"))]
    mock_emb_resp = Mock()
    mock_emb_resp.data = [Mock(embedding=[0.05] * 1024)]

    try:
        with patch.object(app.router.client.chat.completions, "create", return_value=mock_chat_resp), \
             patch.object(app.router.client.embeddings, "create", return_value=mock_emb_resp):
            r1 = client.post("/chat", json={"message": "msg 1"})
            assert r1.status_code == 200
            r2 = client.post("/chat", json={"message": "msg 2"})
            assert r2.status_code == 200
            r3 = client.post("/chat", json={"message": "msg 3"})
            assert r3.status_code == 429
            assert "Rate limit exceeded" in r3.json()["detail"]
    finally:
        app.RATE_LIMIT_RPM = original_rpm
        app._request_counts.clear()

