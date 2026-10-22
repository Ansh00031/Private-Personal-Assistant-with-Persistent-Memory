#!/usr/bin/env python3
# path: scripts/verify_nebius.py
"""Nebius Token Factory API verification script.

Checks configured model IDs, performs test calls, reports token usage and cost.
Never prints or logs the raw API key.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. Load environment from .env file
project_root = Path(__file__).resolve().parent.parent
env_file = project_root / ".env"
load_dotenv(env_file)

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from llm import ModelRouter


def main():
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        print("ERROR: NEBIUS_API_KEY environment variable is not set!")
        print("Please ensure your Nebius Token Factory API key is configured in .env")
        sys.exit(1)

    # Display masked key for safe verification (NEVER prints full key)
    masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
    print(f"Loaded NEBIUS_API_KEY: {masked} (length: {len(api_key)})")

    try:
        router = ModelRouter()
    except Exception as e:
        print(f"ERROR initializing ModelRouter: {e}")
        sys.exit(1)

    print(f"Base URL: {router.client.base_url}")
    print(f"Configured models:")
    print(f"  - nano:      '{router.nano_model}'")
    print(f"  - ultra:     '{router.ultra_model}'")
    print(f"  - embedding: '{router.embedding_model}' (dims={router.embedding_dims})")
    print(f"  - daily cap: ${router.daily_cost_cap:.2f}")

    # Step 1: Model validation against live API
    print("\n--- 1. Validating Model IDs against Nebius API ---")
    try:
        available = router.validate_models()
        print(f"✓ Found {len(available)} models on Nebius Token Factory.")
        print("✓ All 3 configured model IDs exist on the API.")
    except Exception as e:
        print(f"FAILED model validation: {e}")
        sys.exit(1)

    # Step 2: Test Nano Model
    print(f"\n--- 2. Testing Nano Model ({router.nano_model}) ---")
    try:
        content_nano, model_used_nano = router.chat(
            messages=[{"role": "user", "content": "Reply with 'Hello from Nano' and nothing else."}],
            model="nano",
            max_tokens=50,
        )
        print(f"Response: {content_nano.strip()}")
        print(f"Model used: {model_used_nano}")
        print(f"Cumulative session cost: ${router.daily_cost:.6f}")
    except Exception as e:
        print(f"FAILED nano chat call: {e}")
        sys.exit(1)

    # Step 3: Test Ultra Model
    print(f"\n--- 3. Testing Ultra Model ({router.ultra_model}) ---")
    try:
        content_ultra, model_used_ultra = router.chat(
            messages=[{"role": "user", "content": "Reply with 'Hello from Ultra' and nothing else."}],
            model="ultra",
            max_tokens=50,
        )
        print(f"Response: {content_ultra.strip()}")
        print(f"Model used: {model_used_ultra}")
        print(f"Cumulative session cost: ${router.daily_cost:.6f}")
    except Exception as e:
        print(f"FAILED ultra chat call: {e}")
        sys.exit(1)

    # Step 4: Test Embedding
    print(f"\n--- 4. Testing Embedding Model ({router.embedding_model}) ---")
    try:
        test_text = ["Nebius and NVIDIA Global AI Hackathon Private Personal Assistant"]
        embs = router.embed(test_text)
        dim = len(embs[0])
        print(f"Embedding count: {len(embs)}")
        print(f"Embedding dimensions: {dim} (expected: 1024)")
        if dim != 1024:
            print(f"ERROR: Expected 1024 dimensions, got {dim}")
            sys.exit(1)
        print("✓ Embedding dimension check passed (1024).")
    except Exception as e:
        print(f"FAILED embedding call: {e}")
        sys.exit(1)

    # Step 5: Summary
    print("\n=======================================================")
    print(f"Total verification cost: ${router.daily_cost:.6f}")
    print(f"Daily cost cap remaining: ${max(0.0, router.daily_cost_cap - router.daily_cost):.4f}")
    print("ALL NEBIUS RUNTIME CHECKS PASSED SUCCESSFULLY! ✓")
    print("=======================================================")


if __name__ == "__main__":
    main()
