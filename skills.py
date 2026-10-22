# path: skills.py
"""Skill engine: declarative skills with pre/post conditions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from llm import ModelRouter
from memory.db import get_connection
from memory.recall import hybrid_recall


@dataclass
class SkillResult:
    success: bool
    output: str
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None


class Skill(ABC):
    """Base skill class. Subclass and register in SKILLS dict."""

    name: str
    description: str
    triggers: list[str]  # Keywords that may trigger this skill

    @abstractmethod
    def can_handle(self, user_input: str, context: dict) -> bool:
        """Return True if this skill should handle the input."""
        pass

    @abstractmethod
    def execute(self, user_input: str, context: dict, router: ModelRouter) -> SkillResult:
        """Execute the skill. Return result with optional confirmation requirement."""
        pass


class SkillEngine:
    """Routes user input to appropriate skill."""

    def __init__(self, router: ModelRouter):
        self.router = router
        self.skills: list[Skill] = []

    def register(self, skill: Skill) -> None:
        self.skills.append(skill)

    def route(self, user_input: str, context: dict) -> Optional[Skill]:
        """Find first matching skill."""
        for skill in self.skills:
            if skill.can_handle(user_input, context):
                return skill
        return None


# Built-in skills

class RecallSkill(Skill):
    name = "recall"
    description = "Search and retrieve memories"
    triggers = ["remember", "recall", "what did i", "find", "search"]

    def can_handle(self, user_input: str, context: dict) -> bool:
        return any(t in user_input.lower() for t in self.triggers)

    def execute(self, user_input: str, context: dict, router: ModelRouter) -> SkillResult:
        # Extract query from input
        results = hybrid_recall(router, user_input, limit=5)
        if not results:
            return SkillResult(True, "No relevant memories found.")

        lines = ["Here are the most relevant memories:"]
        for r in results:
            lines.append(f"- [{r['provenance']}] {r['content']} (score: {r.get('score', 0):.2f})")
        return SkillResult(True, "\n".join(lines))


class NoteSkill(Skill):
    name = "note"
    description = "Create, read, update, delete personal notes"
    triggers = ["note", "write down", "save", "remember this"]

    def can_handle(self, user_input: str, context: dict) -> bool:
        return any(t in user_input.lower() for t in self.triggers)

    def execute(self, user_input: str, context: dict, router: ModelRouter) -> SkillResult:
        # Delegate to notes tool
        from tools.notes import handle_note
        return handle_note(user_input, context, router)


class CalendarSkill(Skill):
    name = "calendar"
    description = "Manage calendar events"
    triggers = ["calendar", "schedule", "meeting", "appointment", "event"]

    def can_handle(self, user_input: str, context: dict) -> bool:
        return any(t in user_input.lower() for t in self.triggers)

    def execute(self, user_input: str, context: dict, router: ModelRouter) -> SkillResult:
        from tools.calendar import handle_calendar
        return handle_calendar(user_input, context, router)


class FileSkill(Skill):
    name = "files"
    description = "Read/write files in sandbox"
    triggers = ["file", "read", "write", "save to file"]

    def can_handle(self, user_input: str, context: dict) -> bool:
        return any(t in user_input.lower() for t in self.triggers)

    def execute(self, user_input: str, context: dict, router: ModelRouter) -> SkillResult:
        from tools.files import handle_files
        return handle_files(user_input, context, router)


# Default skill registry
def create_default_engine(router: ModelRouter) -> SkillEngine:
    engine = SkillEngine(router)
    engine.register(RecallSkill())
    engine.register(NoteSkill())
    engine.register(CalendarSkill())
    engine.register(FileSkill())
    return engine