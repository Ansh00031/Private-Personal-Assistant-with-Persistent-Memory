# path: tools/actions.py
"""Pending actions registry with 2-step confirmation, expiration, and audit logging."""

import uuid
import time
import threading
from dataclasses import dataclass
from typing import Callable, Any, Optional
from memory.db import transaction, get_connection


@dataclass
class PendingAction:
    action_id: str
    tool_name: str
    action_type: str
    summary: str
    payload: dict
    created_at: float
    expires_at: float
    execute_fn: Callable[[dict], dict]
    status: str = "pending"  # "pending", "confirmed", "cancelled", "expired"
    target_id: Optional[str] = None


class ActionRegistry:
    """Thread-safe registry for proposed actions requiring user confirmation."""

    def __init__(self):
        self._actions: dict[str, PendingAction] = {}
        self._lock = threading.Lock()

    def propose(
        self,
        tool_name: str,
        action_type: str,
        summary: str,
        payload: dict,
        execute_fn: Callable[[dict], dict],
        target_id: Optional[str] = None,
        ttl_seconds: int = 300,  # 5 minutes default expiration
    ) -> PendingAction:
        """Register a proposed action. Does not execute until confirmed."""
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        now = time.time()
        action = PendingAction(
            action_id=action_id,
            tool_name=tool_name,
            action_type=action_type,
            summary=summary,
            payload=payload,
            created_at=now,
            expires_at=now + ttl_seconds,
            execute_fn=execute_fn,
            status="pending",
            target_id=str(target_id) if target_id is not None else None,
        )

        with self._lock:
            self._actions[action_id] = action

        # Audit log the proposal (non-sensitive metadata only)
        log_tool_audit(tool_name, f"propose_{action_type}", action.target_id, "proposed")
        return action

    def get(self, action_id: str) -> Optional[PendingAction]:
        """Fetch pending action by ID."""
        with self._lock:
            return self._actions.get(action_id)

    def confirm(self, action_id: str) -> dict:
        """Confirm and execute a proposed action. Cannot be confirmed twice or if expired."""
        with self._lock:
            action = self._actions.get(action_id)
            if not action:
                raise ValueError("Action not found or invalid action ID")

            if action.status == "confirmed":
                raise ValueError("Action has already been confirmed and executed")
            if action.status == "cancelled":
                raise ValueError("Action was cancelled and cannot be executed")
            if action.status == "expired":
                raise ValueError("Action has expired and cannot be executed")

            if time.time() > action.expires_at:
                action.status = "expired"
                log_tool_audit(action.tool_name, f"confirm_{action.action_type}", action.target_id, "expired")
                raise ValueError("Action confirmation expired (valid for 5 minutes)")

            # Execute the confirmed action
            try:
                result = action.execute_fn(action.payload)
                action.status = "confirmed"
                log_tool_audit(action.tool_name, f"confirm_{action.action_type}", action.target_id, "executed")
                return {
                    "success": True,
                    "action_id": action_id,
                    "summary": action.summary,
                    "result": result,
                }
            except Exception as e:
                action.status = "failed"
                log_tool_audit(action.tool_name, f"confirm_{action.action_type}", action.target_id, f"error: {type(e).__name__}")
                raise

    def cancel(self, action_id: str) -> dict:
        """Cancel a proposed action."""
        with self._lock:
            action = self._actions.get(action_id)
            if not action:
                raise ValueError("Action not found or invalid action ID")

            if action.status in ("confirmed", "cancelled"):
                raise ValueError(f"Action cannot be cancelled (status: {action.status})")

            action.status = "cancelled"
            log_tool_audit(action.tool_name, f"cancel_{action.action_type}", action.target_id, "cancelled")
            return {
                "success": True,
                "action_id": action_id,
                "summary": action.summary,
                "status": "cancelled",
            }

    def clear(self) -> None:
        """Clear all actions (used in testing)."""
        with self._lock:
            self._actions.clear()


# Global registry instance
registry = ActionRegistry()


def log_tool_audit(tool_name: str, action: str, target_id: Optional[str], status: str) -> None:
    """Log non-sensitive tool operation metadata to tool_audit_log table."""
    try:
        with transaction() as conn:
            conn.execute(
                "INSERT INTO tool_audit_log (tool_name, action, target_id, status) VALUES (?, ?, ?, ?)",
                (tool_name, action, str(target_id) if target_id is not None else None, status)
            )
    except Exception:
        # Never fail a tool operation due to audit logging
        pass
