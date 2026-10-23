# path: scripts/test_demo_flow.py
"""Verify the exact sequence of steps for the hackathon demo video script."""

import sys
import os
from dotenv import load_dotenv

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

# Use dedicated demo test DB to avoid touching user database
os.environ["MEMORY_DB_PATH"] = "data/demo_test.db"
os.environ["MEMORY_PASSPHRASE"] = "demo-judge-passphrase-2026"

from fastapi.testclient import TestClient
import app
from memory.db import init_db

def safe_str(s: str) -> str:
    if not s:
        return ""
    return s.encode("ascii", "replace").decode("ascii")

def run_demo_verification():
    print("=== Step 0: Initialize and Verify Health ===")
    init_db()
    client = TestClient(app.app)
    
    health_resp = client.get("/health")
    print(f"Health Response: {health_resp.status_code} -> {health_resp.json()}")
    assert health_resp.status_code == 200
    
    print("\n=== Step 1: Nano Query & Badge ===")
    r1 = client.post("/chat", json={"message": "Hi assistant, who are you?", "model": "nano"})
    print(f"Chat Nano Status: {r1.status_code}")
    d1 = r1.json()
    print(f"Model used: {d1.get('model_used')}")
    print(f"Response: {safe_str(d1.get('response', ''))[:80]}...")
    assert d1.get("model_used") == "nano"
    
    print("\n=== Step 2: Store Fact in Memory ===")
    r2 = client.post("/chat", json={
        "message": "Please remember that my favorite beverage before morning work is matcha green tea.",
        "model": "nano"
    })
    print(f"Store Fact Status: {r2.status_code}")
    d2 = r2.json()
    print(f"Response: {safe_str(d2.get('response', ''))[:80]}...")
    
    print("\n=== Step 3: Recall Memory Across Turns ('memories used') ===")
    r3 = client.post("/chat", json={
        "message": "What is my favorite beverage before morning work?",
        "model": "nano"
    })
    print(f"Recall Status: {r3.status_code}")
    d3 = r3.json()
    print(f"Response: {safe_str(d3.get('response', ''))[:100]}...")
    print(f"Memories retrieved count: {len(d3.get('memories_retrieved', []))}")
    for m in d3.get("memories_retrieved", []):
        print(f"  - Retrieved memory [{m.get('provenance')}]: {safe_str(m.get('content', ''))[:60]}...")
    
    print("\n=== Step 4: Complex Reasoning Query (Ultra) ===")
    r4 = client.post("/chat", json={
        "message": "Briefly contrast SQLCipher page encryption with plain SQLite in 2 sentences.",
        "model": "ultra"
    })
    print(f"Ultra Status: {r4.status_code}")
    d4 = r4.json()
    print(f"Model used: {d4.get('model_used')}")
    print(f"Response: {safe_str(d4.get('response', ''))[:120]}...")
    assert d4.get("model_used") == "ultra"
    
    print("\n=== Step 5: Tool Action with Confirmation (Note Skill) ===")
    r5 = client.post("/chat", json={
        "message": "Add a note: Submit Devpost project before October 30 deadline.",
        "model": "nano"
    })
    print(f"Tool Proposal Status: {r5.status_code}")
    d5 = r5.json()
    print(f"Requires confirmation: {d5.get('requires_confirmation')}")
    print(f"Confirmation prompt: {safe_str(d5.get('confirmation_prompt', ''))}")
    action_id = d5.get("action_id")
    print(f"Action ID: {action_id}")
    assert d5.get("requires_confirmation") is True
    assert action_id is not None
    
    # Confirm the action
    r5_confirm = client.post(f"/actions/{action_id}/confirm")
    print(f"Confirmation execution status: {r5_confirm.status_code}")
    d5_c = r5_confirm.json()
    print(f"Confirmed action result: {d5_c}")
    assert r5_confirm.status_code == 200
    
    print("\n=== Step 6: Privacy Panel & Hard-Delete Proof ===")
    # List memories
    r_list = client.get("/memories?limit=5")
    memories = r_list.json()
    print(f"Current memories listed: {len(memories)}")
    target_id = memories[0]["id"]
    print(f"Targeting memory ID {target_id} for hard delete: '{safe_str(memories[0]['content'])[:40]}...'")
    
    # Execute hard delete
    r_del = client.delete(f"/memory/{target_id}")
    print(f"Delete status: {r_del.status_code}")
    d_del = r_del.json()
    print(f"Delete response: {d_del}")
    assert d_del.get("deleted") is True
    assert d_del.get("verified") is True
    
    # Cleanup demo test files
    for f in ["data/demo_test.db", "data/demo_test.salt", "data/demo_test.db-wal", "data/demo_test.db-shm"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    print("\n=== ALL DEMO FLOW STEPS VERIFIED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_demo_verification()
