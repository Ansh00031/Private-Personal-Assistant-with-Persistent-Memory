# path: jobs.py
"""Scheduled jobs: morning_brief and other periodic tasks."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from llm import ModelRouter
from memory.recall import hybrid_recall
from memory.extract import get_recent_episodes
from typing import Optional
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def morning_brief(router: ModelRouter, user_id: str = "default") -> str:
    """Generate morning briefing from recent memories and episodes."""
    # Get recent episodes (facts)
    episodes = get_recent_episodes(limit=20)

    # Get recent memories from last 24h
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(hours=24)).isoformat()
    recent_memories = hybrid_recall(router, "recent activity", limit=10, since=since)

    # Build context
    context_parts = []
    if episodes:
        context_parts.append("Key facts:")
        for ep in episodes[:10]:
            context_parts.append(f"  - {ep['fact']} (confidence: {ep['confidence']:.0%})")

    if recent_memories:
        context_parts.append("\nRecent conversations:")
        for mem in recent_memories[:5]:
            context_parts.append(f"  - [{mem['provenance']}] {mem['content'][:100]}")

    if not context_parts:
        return "Good morning! No recent activity to summarize."

    context = "\n".join(context_parts)

    # Generate brief with nano
    prompt = f"""Generate a concise morning briefing from this context.
Keep it under 200 words. Friendly, personal tone.

Context:
{context}

Briefing:"""

    brief, _ = router.chat(
        messages=[{"role": "user", "content": prompt}],
        model="nano",
        temperature=0.5,
        max_tokens=300,
    )

    return brief.strip()


def schedule_morning_brief(router: ModelRouter, hour: int = 8, minute: int = 0) -> None:
    """Schedule daily morning brief."""
    scheduler.add_job(
        lambda: logger.info(f"Morning brief: {morning_brief(router)}"),
        CronTrigger(hour=hour, minute=minute),
        id="morning_brief",
        replace_existing=True,
    )
    logger.info(f"Scheduled morning brief for {hour:02d}:{minute:02d}")


def start_scheduler(router: ModelRouter) -> None:
    """Start all scheduled jobs."""
    if not scheduler.running:
        schedule_morning_brief(router)
        scheduler.start()
        logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    """Stop scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")