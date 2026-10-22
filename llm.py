# path: llm.py
"""Nebius client and model router."""

import os
import yaml
from openai import OpenAI
from typing import Literal


class ModelRouter:
    """Routes requests to nano (fast/cheap) or ultra (smart) model."""

    def __init__(self, config_path: str = "config/models.yaml"):
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

    def chat(
        self,
        messages: list[dict],
        model: Literal["nano", "ultra"] = "nano",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> tuple[str, Literal["nano", "ultra"]]:
        """Call chat completion, return (content, model_used)."""
        model_id = self.nano_model if model == "nano" else self.ultra_model
        resp = self.client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content, model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings with configured dimensions."""
        resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
            dimensions=self.embedding_dims,
        )
        return [d.embedding for d in resp.data]

    def list_models(self) -> list[str]:
        """Fetch available model IDs from API."""
        return [m.id for m in self.client.models.list().data]