# path: llm.py
"""Nebius client and model router with model ID validation and daily cost cap."""

import os
import logging
from datetime import datetime, timezone
import yaml
from openai import OpenAI
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# Estimated pricing per 1K tokens (USD)
PRICING = {
    "nano_prompt": 0.0003,
    "nano_completion": 0.0006,
    "ultra_prompt": 0.005,
    "ultra_completion": 0.015,
    "embedding": 0.0001,
}


class ModelRouter:
    """Routes requests to nano (fast/cheap) or ultra (smart) model with cost cap."""

    def __init__(self, config_path: str = "config/models.yaml", validate_on_init: bool = False):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        raw_key = os.getenv("NEBIUS_API_KEY")
        placeholder_keys = {
            "your-nebius-api-key",
            "your-nebius-api-key-here",
            "your_nebius_api_key",
            "<your-nebius-api-key>",
            "placeholder",
        }
        if not raw_key or raw_key.strip() in placeholder_keys:
            raise ValueError(
                "NEBIUS_API_KEY environment variable is not set to a valid API key (found empty or placeholder value). "
                "Please configure your actual Nebius Token Factory API key."
            )

        self.client = OpenAI(
            base_url=self.config["api"]["base_url"],
            api_key=raw_key.strip(),
        )

        self.nano_model = self.config["models"]["nano"]
        self.ultra_model = self.config["models"]["ultra"]
        self.embedding_model = self.config["embedding"]["model"]
        self.embedding_dims = self.config["embedding"]["dimensions"]

        # Configurable daily cost cap (USD)
        self.daily_cost_cap = float(os.getenv("DAILY_COST_CAP_USD", "5.0"))
        self._daily_cost: float = 0.0
        self._current_day: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if validate_on_init or os.getenv("VALIDATE_MODELS_ON_STARTUP", "false").lower() in ("true", "1", "yes"):
            self.validate_models()

    def _check_and_reset_day(self) -> None:
        """Reset cost tracker if UTC day has changed."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._current_day:
            self._current_day = today
            self._daily_cost = 0.0

    @property
    def daily_cost(self) -> float:
        self._check_and_reset_day()
        return round(self._daily_cost, 6)

    def record_cost(self, cost: float) -> None:
        self._check_and_reset_day()
        self._daily_cost += max(0.0, cost)

    def validate_models(self) -> list[str]:
        """Fetch available models from Nebius and verify configured models exist."""
        try:
            available_models = [m.id for m in self.client.models.list().data]
        except Exception as e:
            raise RuntimeError(f"Failed to query models from Nebius API: {e}") from e

        required = [
            ("nano", self.nano_model),
            ("ultra", self.ultra_model),
            ("embedding", self.embedding_model),
        ]
        mismatches = []
        for name, model_id in required:
            if model_id not in available_models:
                mismatches.append(f"{name} model '{model_id}'")

        if mismatches:
            msg = (
                f"Model ID mismatch on Nebius API! Configured in config/models.yaml but not found: "
                f"{', '.join(mismatches)}. Available IDs: {available_models[:10]}..."
            )
            logger.error(msg)
            raise ValueError(msg)

        logger.info(f"Model ID check passed: nano='{self.nano_model}', ultra='{self.ultra_model}', embed='{self.embedding_model}'")
        return available_models

    def chat(
        self,
        messages: list[dict],
        model: Literal["nano", "ultra"] = "nano",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> tuple[str, Literal["nano", "ultra"]]:
        """Call chat completion with automatic cost cap enforcement."""
        self._check_and_reset_day()

        effective_model = model
        # Enforce daily cost cap: downgrade ultra to nano if reached
        if model == "ultra" and self._daily_cost >= self.daily_cost_cap:
            logger.warning(
                f"Daily cost cap of ${self.daily_cost_cap:.2f} reached (${self._daily_cost:.4f} spent today). "
                f"Forcing nano model for cost protection."
            )
            effective_model = "nano"

        model_id = self.nano_model if effective_model == "nano" else self.ultra_model
        resp = self.client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Track token usage & estimate cost
        usage = getattr(resp, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0)
            if isinstance(prompt_tokens, (int, float)) and isinstance(completion_tokens, (int, float)):
                if effective_model == "nano":
                    cost = (prompt_tokens / 1000.0 * PRICING["nano_prompt"]) + (completion_tokens / 1000.0 * PRICING["nano_completion"])
                else:
                    cost = (prompt_tokens / 1000.0 * PRICING["ultra_prompt"]) + (completion_tokens / 1000.0 * PRICING["ultra_completion"])
                self.record_cost(cost)

        return resp.choices[0].message.content, effective_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings with configured dimensions."""
        resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
            dimensions=self.embedding_dims,
        )
        usage = getattr(resp, "usage", None)
        if usage:
            tokens = getattr(usage, "total_tokens", 0)
            if isinstance(tokens, (int, float)):
                cost = (tokens / 1000.0) * PRICING["embedding"]
                self.record_cost(cost)

        return [d.embedding for d in resp.data]

    def list_models(self) -> list[str]:
        """Fetch available model IDs from API."""
        return [m.id for m in self.client.models.list().data]
