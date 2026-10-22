# path: tools/files.py
"""Files tool: read/write files in sandbox directory."""

import os
from pathlib import Path
from typing import Optional
from skills import SkillResult


SANDBOX_ROOT = Path(os.getenv("SANDBOX_ROOT", "data/sandbox"))
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)


def handle_files(user_input: str, context: dict, router) -> SkillResult:
    """Route file operations."""
    lower = user_input.lower()

    if any(w in lower for w in ["read", "open", "view", "cat"]):
        return read_file(user_input)
    elif any(w in lower for w in ["write", "create", "save", "put"]):
        return write_file(user_input, context)
    elif any(w in lower for w in ["list", "ls", "dir"]):
        return list_files()
    elif any(w in lower for w in ["delete", "remove", "rm"]):
        return delete_file(user_input)

    return SkillResult(True, "File command not recognized. Try: read/write/list/delete file.")


def _safe_path(path: str) -> Path:
    """Resolve path within sandbox, prevent traversal."""
    target = (SANDBOX_ROOT / path).resolve()
    if not target.is_relative_to(SANDBOX_ROOT.resolve()):
        raise ValueError("Path traversal attempt blocked")
    return target


def read_file(user_input: str) -> SkillResult:
    """Read a file from sandbox."""
    # Extract filename (simple heuristic)
    words = user_input.split()
    filename = None
    for i, w in enumerate(words):
        if w in ("read", "open", "view", "cat") and i + 1 < len(words):
            filename = words[i + 1]
            break

    if not filename:
        return SkillResult(False, "Specify a filename to read.")

    try:
        path = _safe_path(filename)
        if not path.exists():
            return SkillResult(False, f"File not found: {filename}")
        content = path.read_text(encoding="utf-8")
        return SkillResult(True, f"Content of {filename}:\n```\n{content}\n```")
    except Exception as e:
        return SkillResult(False, f"Error reading file: {e}")


def write_file(user_input: str, context: dict) -> SkillResult:
    """Write a file to sandbox (requires confirmation)."""
    # Extract filename and content
    return SkillResult(
        True,
        "Write file: provide filename and content. This requires confirmation.",
        requires_confirmation=True,
        confirmation_prompt="Write this file to sandbox?"
    )


def list_files() -> SkillResult:
    """List files in sandbox."""
    files = list(SANDBOX_ROOT.rglob("*"))
    files = [f for f in files if f.is_file()]

    if not files:
        return SkillResult(True, "Sandbox is empty.")

    lines = ["Sandbox files:"]
    for f in files:
        rel = f.relative_to(SANDBOX_ROOT)
        size = f.stat().st_size
        lines.append(f"  {rel} ({size} bytes)")
    return SkillResult(True, "\n".join(lines))


def delete_file(user_input: str) -> SkillResult:
    """Delete a file (requires confirmation)."""
    return SkillResult(
        True,
        "Delete file: provide filename. This requires confirmation.",
        requires_confirmation=True,
        confirmation_prompt="Delete this file permanently?"
    )