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



def test_validate_models_success(router, mock_openai):
    """validate_models passes when all configured model IDs exist on the API."""
    mock_openai.models.list.return_value.data = [
        Mock(id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
        Mock(id="nvidia/Nemotron-3-Ultra-550b-a55b"),
        Mock(id="Qwen/Qwen3-Embedding-8B"),
    ]
    models = router.validate_models()
    assert len(models) == 3


def test_validate_models_mismatch_raises(router, mock_openai):
    """validate_models raises ValueError on model ID mismatch."""
    mock_openai.models.list.return_value.data = [
        Mock(id="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
        # ultra and embedding models missing
    ]
    with pytest.raises(ValueError, match="Model ID mismatch"):
        router.validate_models()


def test_daily_cost_cap_downgrades_ultra_to_nano(router, mock_openai):
    """When daily cost cap is reached, requests for ultra are downgraded to nano."""
    router.daily_cost_cap = 0.05
    # Force cost to exceed cap
    router.record_cost(0.06)

    messages = [{"role": "user", "content": "Complex reasoning"}]
    _, model_used = router.chat(messages, model="ultra")

    # Must be forced to nano due to cost cap
    assert model_used == "nano"
    mock_openai.chat.completions.create.assert_called_with(
        model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
    )


def test_token_usage_increments_cost(router, mock_openai):
    """Token usage in API response properly increments router's daily_cost."""
    initial_cost = router.daily_cost
    mock_resp = Mock()
    mock_resp.choices = [Mock(message=Mock(content="Test"))]
    mock_resp.usage = Mock(prompt_tokens=500, completion_tokens=500)
    mock_openai.chat.completions.create.return_value = mock_resp

    router.chat([{"role": "user", "content": "hi"}], model="nano")
    assert router.daily_cost > initial_cost
