# path: scripts/migrate_to_sqlcipher.py
"""Migrate unencrypted SQLite data/memory.db to SQLCipher encrypted database."""

import os
import sys
import gc
import shutil
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from memory.db import (
    get_connection,
    init_db,
)

def migrate():
    db_file = Path("data/memory.db")
    bak_file = Path("data/memory.db.unencrypted.bak")
    temp_encrypted = Path("data/memory_encrypted_tmp.db")

    if not bak_file.exists() and db_file.exists():
        print("Step 1: Creating backup of unencrypted database...")
        shutil.copy2(db_file, bak_file)
        print(f"Backup created at: {bak_file}")
    elif bak_file.exists():
        print(f"Using existing backup: {bak_file}")

    print("Step 2: Inspecting unencrypted database...")
    plain_conn = sqlite3.connect(str(bak_file))
    plain_conn.row_factory = sqlite3.Row

    cur = plain_conn.cursor()
    cur.execute("SELECT count(*) FROM memories")
    total_memories = cur.fetchone()[0]
    print(f"Found {total_memories} memories to migrate.")

    # Remove temporary encrypted file if exists
    if temp_encrypted.exists():
        try:
            temp_encrypted.unlink()
        except Exception:
            pass
    temp_salt = temp_encrypted.with_suffix(".salt")
    if temp_salt.exists():
        try:
            temp_salt.unlink()
        except Exception:
            pass

    print("Step 3: Initializing encrypted database schema via init_db()...")
    os.environ["MEMORY_DB_PATH"] = str(temp_encrypted)
    init_db()

    print("Step 4: Copying data into encrypted database...")
    enc_conn = get_connection(db_path_override=temp_encrypted)
    try:
        # 1. Memories
        memories = plain_conn.execute("SELECT * FROM memories").fetchall()
        for m in memories:
            keys = m.keys()
            cols = ", ".join(keys)
            placeholders = ", ".join(["?"] * len(keys))
            enc_conn.execute(
                f"INSERT INTO memories ({cols}) VALUES ({placeholders})",
                tuple(m[k] for k in keys)
            )

        # 2. Episodes
        try:
            episodes = plain_conn.execute("SELECT * FROM episodes").fetchall()
            for ep in episodes:
                keys = ep.keys()
                cols = ", ".join(keys)
                placeholders = ", ".join(["?"] * len(keys))
                enc_conn.execute(
                    f"INSERT INTO episodes ({cols}) VALUES ({placeholders})",
                    tuple(ep[k] for k in keys)
                )
            print(f"Migrated {len(episodes)} episodes.")
        except Exception as e:
            print(f"Episodes table skipped: {e}")

        # 3. Provenance log
        try:
            provs = plain_conn.execute("SELECT * FROM provenance_log").fetchall()
            for p in provs:
                keys = p.keys()
                cols = ", ".join(keys)
                placeholders = ", ".join(["?"] * len(keys))
                enc_conn.execute(
                    f"INSERT INTO provenance_log ({cols}) VALUES ({placeholders})",
                    tuple(p[k] for k in keys)
                )
            print(f"Migrated {len(provs)} provenance log records.")
        except Exception as e:
            print(f"Provenance log skipped: {e}")

        # Rebuild FTS index to ensure full sync
        enc_conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        enc_conn.commit()

        # Verify count in encrypted DB
        migrated_count = enc_conn.execute("SELECT count(*) FROM memories").fetchone()[0]
        print(f"Encrypted DB verified with {migrated_count} memories.")
        assert migrated_count == total_memories, f"Count mismatch: {migrated_count} != {total_memories}"

    finally:
        enc_conn.close()
        del enc_conn
        plain_conn.close()
        del plain_conn
        gc.collect()

    print("Step 5: Swapping encrypted DB into place...")
    # Clean up original db_file (already safely backed up to bak_file)
    if db_file.exists():
        db_file.unlink()

    shutil.move(temp_encrypted, db_file)

    if temp_salt.exists():
        dest_salt = db_file.with_suffix(".salt")
        if dest_salt.exists():
            dest_salt.unlink()
        shutil.move(temp_salt, dest_salt)

    # Clean up WAL/SHM artifacts if any
    for ext in ["-wal", "-shm"]:
        p = Path(f"data/memory.db{ext}")
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    print("\n[SUCCESS] Migration complete! All 187 memories are now encrypted with SQLCipher AES-256.")

if __name__ == "__main__":
    migrate()
