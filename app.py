# path: app.py
"""FastAPI routes for Private Personal Assistant."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Literal
from llm import ModelRouter
from memory.db import init_db, get_connection, hard_delete_memory, verify_hard_delete, HAS_SQLCIPHER
from memory.extract import extract_facts_and_episodes
from memory.recall import hybrid_recall
from skills import create_default_engine, SkillResult
from jobs import start_scheduler, shutdown_scheduler, morning_brief
from tools.actions import registry
import os
import time
import logging
from memory.db import HAS_SQLCIPHER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Private Personal Assistant", version="0.1.0")

# Initialize
router = ModelRouter()
skill_engine = create_default_engine(router)
init_db()

# Rate limiting for demo protection (configurable requests per minute per client)
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "30"))
_request_counts = {}

def check_rate_limit(client_ip: str):
    now = time.time()
    minute_window = int(now // 60)
    key = f"{client_ip}:{minute_window}"
    count = _request_counts.get(key, 0)
    if count >= RATE_LIMIT_RPM:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded ({RATE_LIMIT_RPM} requests/min). Please wait a moment.")
    _request_counts[key] = count + 1
    if len(_request_counts) > 500:
        for k in list(_request_counts.keys()):
            if not k.endswith(f":{minute_window}"):
                _request_counts.pop(k, None)

# Mount static files for UI
app.mount("/ui", StaticFiles(directory="ui"), name="ui")


class ChatRequest(BaseModel):
    message: str
    model: Literal["nano", "ultra"] = "nano"
    context: Optional[dict] = None
    history: Optional[list[dict]] = None


class ChatResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    
    response: str
    model_used: Literal["nano", "ultra"]
    memories_retrieved: list[dict] = []
    skill_used: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    action_id: Optional[str] = None


class MemoryDeleteRequest(BaseModel):
    memory_id: int


@app.on_event("startup")
async def startup():
    if HAS_SQLCIPHER:
        logger.info("encryption: on")
    else:
        logger.warning("encryption: off")
    start_scheduler(router)


@app.on_event("shutdown")
async def shutdown():
    shutdown_scheduler()


@app.get("/")
async def root():
    return FileResponse("ui/index.html")


@app.get("/health")
async def health():
    """Production health check verifying DB connectivity, encryption status, and models."""
    db_ok = False
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
            db_ok = True
    except Exception as e:
        logger.error(f"Health check DB probe failed: {e}")

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "encryption": "on" if HAS_SQLCIPHER else "off",
        "models": {
            "nano": router.nano_model,
            "ultra": router.ultra_model,
            "embedding": router.embedding_model,
        },
        "daily_cost_usd": router.daily_cost,
        "daily_cost_cap_usd": router.daily_cost_cap,
    }


@app.post("/morning-brief")
async def trigger_morning_brief():
    """Generate executive morning briefing on-demand."""
    try:
        brief = morning_brief(router)
        return {"brief": brief, "model_used": "nano"}
    except Exception as e:
        logger.exception(f"Morning brief generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Morning brief error: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_req: Request):
    client_ip = http_req.client.host if http_req.client else "local"
    check_rate_limit(client_ip)
    """Main chat endpoint with memory retrieval, conversation history, and skill routing."""
    try:
        user_msg = request.message
        context = request.context or {}
        history = request.history or []

        # 1. Retrieve relevant memories
        memories = hybrid_recall(router, user_msg, limit=5)
        memory_context = "\n".join([f"[{m['provenance']}] {m['content']}" for m in memories])

        # 2. Build system prompt with memory context, language support, and markdown tables instruction
        system_prompt = f"""You are a private personal assistant with persistent memory.
Relevant memories:
{memory_context if memory_context else 'None'}

Respond naturally in the language or dialect used by the user (including English, Hindi, and Hinglish). If the user writes or speaks in Hindi or Hinglish, reply in Hindi or Hinglish accordingly.
When requested to create or format a timetable, schedule, plan, comparison, or tabular data, ALWAYS format it cleanly as a standard markdown table (using pipe | syntax with clear header rows) so it renders as a visual table.
If user asks to perform an action (write, delete, schedule), indicate what tool would be needed."""

        messages = [{"role": "system", "content": system_prompt}]

        # 3. Include previous conversation history so user can add on without repeating
        if history:
            for turn in history[-10:]:
                r = turn.get("role")
                c = turn.get("content")
                if r in ("user", "assistant") and c:
                    messages.append({"role": r, "content": c})
        else:
            # Fallback to recent stored turns if client didn't supply history
            try:
                with get_connection() as conn:
                    recent = conn.execute("""
                        SELECT id, content, provenance
                        FROM memories
                        WHERE deleted_at IS NULL
                        ORDER BY id DESC
                        LIMIT 6
                    """).fetchall()
                    for row in reversed(recent):
                        r = "user" if row["provenance"] == "user_said" else "assistant"
                        messages.append({"role": r, "content": row["content"]})
            except Exception as e:
                logger.warning(f"Could not load recent memory history fallback: {e}")

        # Ensure current user message is appended if not already the last entry
        if not (messages and messages[-1]["role"] == "user" and messages[-1]["content"] == user_msg):
            messages.append({"role": "user", "content": user_msg})

        # 4. Check for skill match
        skill = skill_engine.route(user_msg, context)
        skill_result: Optional[SkillResult] = None

        if skill:
            logger.info(f"Skill matched: {skill.name}")
            skill_result = skill.execute(user_msg, context, router)
            if skill_result.requires_confirmation:
                return ChatResponse(
                    response=skill_result.output,
                    model_used=request.model,
                    memories_retrieved=memories,
                    skill_used=skill.name,
                    requires_confirmation=True,
                    confirmation_prompt=skill_result.confirmation_prompt,
                    action_id=skill_result.action_id,
                )
            # If skill handled it completely, return its output
            if skill_result.success:
                # Store the exchange as memory
                await _store_exchange(user_msg, skill_result.output, "tool_output")
                return ChatResponse(
                    response=skill_result.output,
                    model_used=request.model,
                    memories_retrieved=memories,
                    skill_used=skill.name,
                )

        # 5. Fall back to LLM with full context
        response, model_used = router.chat(messages, model=request.model)

        # 6. Store exchange
        memory_ids = await _store_exchange(user_msg, response, "user_said")

        # 7. Extract facts/episodes (async in background)
        try:
            if memory_ids:
                extract_facts_and_episodes(router, f"User: {user_msg}\nAssistant: {response}", memory_ids)
        except Exception as e:
            logger.warning(f"Fact extraction failed: {e}")

        return ChatResponse(
            response=response,
            model_used=model_used,
            memories_retrieved=memories,
        )
    except Exception as e:
        logger.exception(f"Chat execution failed: {e}")
        err_type = type(e).__name__
        err_msg = str(e)
        if "AuthenticationError" in err_type or "401" in err_msg or "authenticate" in err_msg.lower():
            detail = "Nebius API authentication failed (401). Your NEBIUS_API_KEY environment variable is invalid or was set to a placeholder. Please ensure your valid Nebius Token Factory API key is loaded."
        else:
            detail = f"{err_type}: {err_msg}"
        raise HTTPException(status_code=500, detail=detail)


async def _store_exchange(user_msg: str, assistant_msg: str, provenance: str) -> list[int]:
    """Store both messages as memories, return IDs."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO memories (content, provenance) VALUES (?, ?)",
            (user_msg, provenance)
        )
        user_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO memories (content, provenance) VALUES (?, ?)",
            (assistant_msg, "tool_output" if provenance == "user_said" else "user_said")
        )
        assistant_id = cur.lastrowid
        conn.commit()
    return [user_id, assistant_id]


@app.post("/actions/{action_id}/confirm")
async def confirm_action_endpoint(action_id: str):
    """Confirm and execute a proposed 2-step tool action."""
    try:
        result = registry.confirm(action_id)
        # Store confirmed action in memories for assistant context
        summary = result.get("summary", "action")
        await _store_exchange(f"Confirmed action: {summary}", f"Action executed successfully: {summary}", "tool_output")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Action confirmation execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Action execution failed: {str(e)}")


@app.post("/actions/{action_id}/cancel")
async def cancel_action_endpoint(action_id: str):
    """Cancel a proposed tool action."""
    try:
        result = registry.cancel(action_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tool-audit-log")
async def get_tool_audit_log(limit: int = 50):
    """Retrieve non-sensitive tool audit log entries."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, tool_name, action, target_id, status, timestamp
            FROM tool_audit_log
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.delete("/memory/{memory_id}")
async def delete_memory(memory_id: int):
    """Hard delete a memory (removes row, vector, FTS)."""
    success = hard_delete_memory(memory_id)
    if not success:
        raise HTTPException(404, "Memory not found or already deleted")

    verified = verify_hard_delete(memory_id)
    return {"deleted": success, "verified": verified}


@app.get("/memories")
async def list_memories(limit: int = 50, offset: int = 0):
    """List memories with pagination."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, content, provenance, created_at
            FROM memories
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
    return [dict(r) for r in rows]


@app.get("/stats")
async def stats():
    """System stats for UI badge/cost counter."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL").fetchone()[0]
        episodes = conn.execute("SELECT COUNT(*) FROM episodes WHERE deleted_at IS NULL").fetchone()[0]
    # Rough cost estimate: ~$0.001 per 1k tokens, avg 500 tokens per memory
    estimated_cost = round(total * 0.0005, 4)
    return {
        "total_memories": total,
        "total_episodes": episodes,
        "estimated_cost_usd": estimated_cost,
        "models": {"nano": router.nano_model, "ultra": router.ultra_model},
    }