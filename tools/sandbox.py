# path: tools/sandbox.py
"""Tool adapter: run_tool(name, args) -> dict with allowlisted folders, timeouts, and audit logging.

NemoClaw, OpenShell, Hermes Agent and Nebius Serverless APIs are stubbed behind this interface.
Tool output and file contents are treated strictly as data, never as executable instructions.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
import concurrent.futures
from tools.actions import log_tool_audit

logger = logging.getLogger(__name__)

DEFAULT_TOOL_TIMEOUT = 10.0  # 10 seconds default timeout
SANDBOX_ROOT = Path(os.getenv("SANDBOX_ROOT", "data/sandbox")).resolve()


class ToolAdapter(ABC):
    """Abstract adapter for external tool APIs."""

    @abstractmethod
    def run_tool(self, name: str, args: dict) -> dict:
        """Execute a tool by name with arguments. Return result dict."""
        pass


class StubAdapter(ToolAdapter):
    """Stub implementation for development/testing."""

    def run_tool(self, name: str, args: dict) -> dict:
        # Known tool stubs
        stubs = {
            "nemo_claw": {"status": "stubbed", "message": "NemoClaw not configured"},
            "open_shell": {"status": "stubbed", "message": "OpenShell not configured"},
            "hermes_agent": {"status": "stubbed", "message": "Hermes Agent not configured"},
            "nebius_serverless": {"status": "stubbed", "message": "Nebius Serverless not configured"},
        }

        if name in stubs:
            return stubs[name]

        return {"status": "error", "message": f"Unknown tool: {name}"}


# Global adapter instance
adapter: ToolAdapter = StubAdapter()


def set_adapter(new_adapter: ToolAdapter) -> None:
    """Replace the global adapter (for testing or when real APIs are available)."""
    global adapter
    adapter = new_adapter


def _validate_allowlisted_path(args: dict) -> None:
    """Verify that any file or path in arguments stays strictly within allowlisted folders."""
    for key in ("path", "folder", "filename", "filepath"):
        if key in args and isinstance(args[key], str):
            p = (SANDBOX_ROOT / args[key]).resolve()
            if not p.is_relative_to(SANDBOX_ROOT):
                raise ValueError(f"Path traversal blocked: '{args[key]}' is outside allowlisted folder '{SANDBOX_ROOT}'")


def run_tool(name: str, args: dict, timeout: float = DEFAULT_TOOL_TIMEOUT) -> dict:
    """
    Main entry point for tool execution with:
    1. Allowlisted folder validation
    2. Execution timeout
    3. Non-sensitive audit logging
    4. Safe data encapsulation (outputs are pure data, not instructions)
    """
    # 1. Allowlisted folder validation
    try:
        _validate_allowlisted_path(args)
    except ValueError as e:
        log_tool_audit(name, "path_validation_failed", None, "blocked")
        return {"status": "error", "message": str(e), "data": None}

    # 2. Non-sensitive audit log of invocation
    log_tool_audit(name, "invoke", None, "started")

    # 3. Timeout enforcement via ThreadPoolExecutor
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(adapter.run_tool, name, args)

    try:
        raw_result = future.result(timeout=timeout)
        log_tool_audit(name, "invoke", None, "completed")
        # Ensure returned structure treats output purely as data
        if isinstance(raw_result, dict):
            return raw_result
        return {"status": "ok", "data": str(raw_result)}
    except concurrent.futures.TimeoutError:
        log_tool_audit(name, "invoke", None, "timeout")
        return {
            "status": "error",
            "message": f"Tool '{name}' timed out after {timeout} seconds",
            "data": None
        }
    except Exception as e:
        log_tool_audit(name, "invoke", None, f"error: {type(e).__name__}")
        return {
            "status": "error",
            "message": f"Tool execution failed: {str(e)}",
            "data": None
        }
    finally:
        executor.shutdown(wait=False)
