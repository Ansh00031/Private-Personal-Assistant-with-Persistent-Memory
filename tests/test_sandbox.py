# path: tests/test_sandbox.py
"""Tests for tools/sandbox.py"""

import pytest
from tools.sandbox import run_tool, StubAdapter, set_adapter, ToolAdapter


def test_stub_adapter_known_tools():
    """Stub returns stubbed response for known tools."""
    adapter = StubAdapter()

    for tool in ["nemo_claw", "open_shell", "hermes_agent", "nebius_serverless"]:
        result = adapter.run_tool(tool, {"param": "value"})
        assert result["status"] == "stubbed"
        assert "not configured" in result["message"]


def test_stub_adapter_unknown_tool():
    """Stub returns error for unknown tools."""
    adapter = StubAdapter()
    result = adapter.run_tool("unknown_tool", {})
    assert result["status"] == "error"
    assert "Unknown tool" in result["message"]


def test_run_tool_uses_global_adapter():
    """run_tool uses global adapter."""
    # Replace with custom adapter
    class CustomAdapter(ToolAdapter):
        def run_tool(self, name, args):
            return {"custom": True, "name": name, "args": args}

    custom = CustomAdapter()
    set_adapter(custom)

    try:
        result = run_tool("test_tool", {"key": "value"})
        assert result["custom"] is True
        assert result["name"] == "test_tool"
        assert result["args"] == {"key": "value"}
    finally:
        # Restore stub
        set_adapter(StubAdapter())


def test_set_adapter_replaces_global():
    """set_adapter replaces the global adapter."""
    original = StubAdapter()
    set_adapter(original)

    class NewAdapter(ToolAdapter):
        def run_tool(self, name, args):
            return {"new": True}

    set_adapter(NewAdapter())
    result = run_tool("any", {})
    assert result["new"] is True

    set_adapter(original)