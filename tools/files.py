# path: tools/files.py
"""Files tool: read/write files in sandbox directory with 2-step confirmation."""

import os
import re
from pathlib import Path
from typing import Optional
from skills import SkillResult
from tools.actions import registry


SANDBOX_ROOT = Path(os.getenv("SANDBOX_ROOT", "data/sandbox"))
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)


def handle_files(user_input: str, context: dict, router) -> SkillResult:
    """Route file operations."""
    lower = user_input.lower()

    if any(w in lower for w in ["delete", "remove", "rm"]):
        return delete_file(user_input)
    elif any(w in lower for w in ["write", "create", "save", "put"]):
        return write_file(user_input, context)
    elif any(w in lower for w in ["read", "open", "view", "cat"]):
        return read_file(user_input)
    elif any(w in lower for w in ["list", "ls", "dir"]):
        return list_files()

    return SkillResult(True, "File command not recognized. Try: read/write/list/delete file.")


def _safe_path(path: str) -> Path:
    """Resolve path within sandbox, strictly preventing traversal."""
    root = SANDBOX_ROOT.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Path traversal blocked: target path '{path}' resolves outside sandbox '{root}'")
    return target


def read_file(user_input: str) -> SkillResult:
    """Read a file from sandbox. File contents are treated strictly as data."""
    words = user_input.split()
    filename = None
    for i, w in enumerate(words):
        if w.lower() in ("read", "open", "view", "cat", "file") and i + 1 < len(words):
            candidate = words[i + 1].strip("'\"")
            if "." in candidate or candidate.isalnum():
                filename = candidate
                break

    if not filename:
        return SkillResult(False, "Specify a filename to read (e.g. 'read file notes.txt').")

    try:
        path = _safe_path(filename)
        if not path.exists():
            return SkillResult(False, f"File not found in sandbox: {filename}")
        content = path.read_text(encoding="utf-8")
        # Tool output and file contents are wrapped as data, never executed as instructions
        return SkillResult(True, f"File '{filename}' content (data):\n```\n{content}\n```")
    except Exception as e:
        return SkillResult(False, f"Error reading file: {e}")


def write_file(user_input: str, context: dict) -> SkillResult:
    """Propose writing a file to sandbox (step 1 of 2). Changes nothing until confirmed."""
    # Simple extraction of filename and content
    m = re.search(r'(?:write|save|create)\s+(?:file\s+)?([^\s:]+)(?:\s*:\s*|\s+with\s+(?:content\s+)?|\s+)(.*)', user_input, re.I | re.DOTALL)
    if m:
        filename = m.group(1).strip("'\"")
        content = m.group(2).strip()
    else:
        filename = "note.txt"
        content = user_input

    try:
        target = _safe_path(filename)
    except Exception as e:
        return SkillResult(False, str(e))

    def _execute(payload: dict) -> dict:
        p = _safe_path(payload["filename"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(payload["content"], encoding="utf-8")
        return {"filename": payload["filename"], "bytes_written": len(payload["content"])}

    summary = f"Write {len(content)} characters to sandbox file '{filename}'"
    action = registry.propose(
        tool_name="files",
        action_type="write",
        summary=summary,
        payload={"filename": filename, "content": content},
        execute_fn=_execute,
        target_id=filename,
    )

    return SkillResult(
        success=True,
        output=f"Proposed writing to sandbox file '{filename}'. Please confirm to execute.",
        requires_confirmation=True,
        confirmation_prompt=f"Write {len(content)} chars to sandbox file '{filename}'?",
        action_id=action.action_id,
    )


def list_files() -> SkillResult:
    """List files in sandbox allowlisted folder."""
    files = list(SANDBOX_ROOT.rglob("*"))
    files = [f for f in files if f.is_file()]

    if not files:
        return SkillResult(True, "Sandbox folder is empty.")

    lines = ["Sandbox files (allowlisted):"]
    for f in files:
        rel = f.relative_to(SANDBOX_ROOT)
        size = f.stat().st_size
        lines.append(f"  {rel} ({size} bytes)")
    return SkillResult(True, "\n".join(lines))


def delete_file(user_input: str) -> SkillResult:
    """Propose deleting a file from sandbox (step 1 of 2). Changes nothing until confirmed."""
    words = user_input.split()
    filename = None
    for i, w in enumerate(words):
        if w.lower() in ("delete", "remove", "rm", "file") and i + 1 < len(words):
            candidate = words[i + 1].strip("'\"")
            if "." in candidate or candidate.isalnum():
                filename = candidate
                break

    if not filename:
        return SkillResult(False, "Specify a filename to delete (e.g. 'delete file test.txt').")

    try:
        path = _safe_path(filename)
        if not path.exists():
            return SkillResult(False, f"File not found in sandbox: {filename}")
    except Exception as e:
        return SkillResult(False, str(e))

    def _execute(payload: dict) -> dict:
        p = _safe_path(payload["filename"])
        if p.exists():
            p.unlink()
        return {"filename": payload["filename"], "deleted": True}

    summary = f"Delete sandbox file '{filename}'"
    action = registry.propose(
        tool_name="files",
        action_type="delete",
        summary=summary,
        payload={"filename": filename},
        execute_fn=_execute,
        target_id=filename,
    )

    return SkillResult(
        success=True,
        output=f"Proposed deleting sandbox file '{filename}'. Please confirm.",
        requires_confirmation=True,
        confirmation_prompt=f"Delete sandbox file '{filename}' permanently?",
        action_id=action.action_id,
    )
