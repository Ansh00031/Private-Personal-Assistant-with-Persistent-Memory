# path: tools/sandbox.py
"""Tool adapter: run_tool(name, args) -> dict.

NemoClaw, OpenShell, Hermes Agent and Nebius Serverless APIs are NOT known.
Put them behind this adapter interface and stub it.
"""

from abc import ABC, abstractmethod
from typing import Any
import json


class ToolAdapter(ABC):
    """Abstract adapter for external tool APIs."""

    @abstractmethod
    def run_tool(self, name: str, args: dict) -> dict:
        """Execute a tool by name with arguments. Return result dict."""
        pass


class StubAdapter(ToolAdapter):
    """Stub implementation for development/testing."""

    def run_tool(self, name: str, args: dict) -> dict:
        # Log the call for debugging
        print(f"[STUB] run_tool({name}, {json.dumps(args)})")

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


# Global adapter instance (replace with real implementation when APIs are known)
adapter: ToolAdapter = StubAdapter()


def run_tool(name: str, args: dict) -> dict:
    """Main entry point for tool execution."""
    return adapter.run_tool(name, args)


def set_adapter(new_adapter: ToolAdapter) -> None:
    """Replace the global adapter (for testing or when real APIs are available)."""
    global adapter
    adapter = new_adapter