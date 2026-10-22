# path: tests/test_llm.py
"""Tests for llm.py"""

import os
import pytest
from unittest.mock import Mock, patch
from llm import ModelRouter


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    with patch("llm.OpenAI") as mock:
        client = Mock()
        mock.return_value = client
        yield client


@pytest.fixture
def router(mock_openai):
    """Create ModelRouter with mocked client."""
    # Mock models.list() with actual Nebius model IDs
    mock_openai.models.list.return_value.data = [
        Mock(id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
        Mock(id="nvidia/Nemotron-3-Ultra-550b-a55b"),
    ]

    # Mock chat.completions.create
    mock_resp = Mock()
    mock_resp.choices = [Mock(message=Mock(content="Test response"))]
    mock_openai.chat.completions.create.return_value = mock_resp

    # Mock embeddings.create
    mock_emb = Mock()
    mock_emb.data = [
        Mock(embedding=[0.1] * 1024),
        Mock(embedding=[0.2] * 1024),
    ]
    mock_openai.embeddings.create.return_value = mock_emb

    os.environ["NEBIUS_API_KEY"] = "test-key"
    return ModelRouter()


def test_router_initialization(router):
    """Router initializes with correct models from config."""
    assert router.nano_model == "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    assert router.ultra_model == "nvidia/Nemotron-3-Ultra-550b-a55b"
    assert router.embedding_model == "Qwen/Qwen3-Embedding-8B"
    assert router.embedding_dims == 1024


def test_chat_nano(router, mock_openai):
    """Chat with nano model."""
    messages = [{"role": "user", "content": "Hello"}]
    content, model = router.chat(messages, model="nano")

    assert content == "Test response"
    assert model == "nano"
    mock_openai.chat.completions.create.assert_called_with(
        model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
    )


def test_chat_ultra(router, mock_openai):
    """Chat with ultra model."""
    messages = [{"role": "user", "content": "Hello"}]
    content, model = router.chat(messages, model="ultra")

    assert content == "Test response"
    assert model == "ultra"
    mock_openai.chat.completions.create.assert_called_with(
        model="nvidia/Nemotron-3-Ultra-550b-a55b",
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
    )


def test_embed(router, mock_openai):
    """Embeddings with correct dimensions."""
    texts = ["text1", "text2"]
    embeddings = router.embed(texts)

    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1024
    mock_openai.embeddings.create.assert_called_with(
        model="Qwen/Qwen3-Embedding-8B",
        input=texts,
        dimensions=1024,
    )


def test_list_models(router, mock_openai):
    """List models returns IDs from API."""
    models = router.list_models()
    assert "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B" in models
    assert "nvidia/Nemotron-3-Ultra-550b-a55b" in models


def test_missing_api_key_raises():
    """Router raises if NEBIUS_API_KEY not set."""
    os.environ.pop("NEBIUS_API_KEY", None)
    with patch("llm.OpenAI") as mock_openai:
        mock_openai.side_effect = ValueError("NEBIUS_API_KEY environment variable not set")
        with pytest.raises(ValueError, match="NEBIUS_API_KEY"):
            ModelRouter()