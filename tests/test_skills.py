# path: tests/test_skills.py
"""Tests for skills.py"""

import pytest
from unittest.mock import Mock
from skills import SkillEngine, RecallSkill, NoteSkill, CalendarSkill, FileSkill, SkillResult
from llm import ModelRouter


@pytest.fixture
def mock_router():
    router = Mock(spec=ModelRouter)
    router.chat.return_value = ("Mock response", "nano")
    router.embed.return_value = [[0.1] * 1024]
    return router


@pytest.fixture
def engine(mock_router):
    return SkillEngine(mock_router)


def test_recall_skill_can_handle(mock_router):
    """RecallSkill triggers on memory keywords."""
    skill = RecallSkill()
    assert skill.can_handle("what did i say yesterday", {})
    assert skill.can_handle("remember my name", {})
    assert skill.can_handle("find my notes", {})
    assert not skill.can_handle("hello there", {})


def test_note_skill_can_handle(mock_router):
    """NoteSkill triggers on note keywords."""
    skill = NoteSkill()
    assert skill.can_handle("create a note", {})
    assert skill.can_handle("write down this", {})
    assert skill.can_handle("save this for later", {})
    assert not skill.can_handle("hello", {})


def test_calendar_skill_can_handle(mock_router):
    """CalendarSkill triggers on calendar keywords."""
    skill = CalendarSkill()
    assert skill.can_handle("schedule a meeting", {})
    assert skill.can_handle("add to calendar", {})
    assert skill.can_handle("appointment tomorrow", {})
    assert not skill.can_handle("hello", {})


def test_file_skill_can_handle(mock_router):
    """FileSkill triggers on file keywords."""
    skill = FileSkill()
    assert skill.can_handle("read file", {})
    assert skill.can_handle("write to file", {})
    assert skill.can_handle("save this to a file", {})
    assert not skill.can_handle("hello", {})


def test_skill_engine_routes_to_first_match(mock_router):
    """Engine returns first matching skill."""
    engine = SkillEngine(mock_router)
    engine.register(RecallSkill())
    engine.register(NoteSkill())

    # "remember" matches both, but RecallSkill registered first
    skill = engine.route("remember this", {})
    assert isinstance(skill, RecallSkill)


def test_skill_result_requires_confirmation():
    """SkillResult can require confirmation."""
    result = SkillResult(
        True,
        "Action needed",
        requires_confirmation=True,
        confirmation_prompt="Confirm?"
    )
    assert result.requires_confirmation is True
    assert result.confirmation_prompt == "Confirm?"


def test_skill_result_no_confirmation():
    """SkillResult without confirmation."""
    result = SkillResult(True, "Done")
    assert result.requires_confirmation is False
    assert result.confirmation_prompt is None