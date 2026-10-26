# path: tools/web_search.py
"""Tavily web search tool: provides runtime real-time internet search capabilities."""

import os
import logging
import httpx
from typing import Optional
from dotenv import load_dotenv
from memory.db import get_connection

load_dotenv()
logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


def _audit_log(tool_name: str, action: str, target: str, status: str):
    """Record non-sensitive audit metadata."""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO tool_audit_log (tool_name, action, target_id, status) VALUES (?, ?, ?, ?)",
                (tool_name, action, target[:100], status)
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Could not record search audit log: {e}")


def search_web_tavily(query: str, max_results: int = 3) -> dict:
    """
    Execute a real-time web search query via Tavily Search API.
    Returns dictionary with search results, URLs, and status.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        _audit_log("tavily", "search", query, "skipped_missing_key")
        return {
            "success": False,
            "error": "TAVILY_API_KEY is not configured in .env",
            "results": []
        }

    try:
        payload = {
            "api_key": api_key.strip(),
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": True,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(TAVILY_API_URL, json=payload)

        if resp.status_code != 200:
            _audit_log("tavily", "search", query, f"http_error_{resp.status_code}")
            return {
                "success": False,
                "error": f"Tavily API returned HTTP {resp.status_code}: {resp.text[:100]}",
                "results": []
            }

        data = resp.json()
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in data.get("results", [])
        ]

        _audit_log("tavily", "search", query, "success")
        return {
            "success": True,
            "answer": data.get("answer", ""),
            "results": results,
            "query": query,
        }
    except Exception as e:
        logger.exception(f"Tavily search execution failed: {e}")
        _audit_log("tavily", "search", query, f"error_{type(e).__name__}")
        return {
            "success": False,
            "error": str(e),
            "results": []
        }
