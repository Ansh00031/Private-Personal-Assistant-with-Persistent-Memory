# path: tests/conftest.py
"""Pytest configuration - sets up test environment."""

import os
import tempfile
import atexit

# Create a temporary database file for tests
_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)

# Set test environment variables before any imports
os.environ["MEMORY_ENCRYPTION_KEY"] = "0" * 64
os.environ["NEBIUS_API_KEY"] = "test-key"
os.environ["MEMORY_DB_PATH"] = _test_db_path
os.environ["SANDBOX_ROOT"] = "data/sandbox"


def _cleanup():
    try:
        if os.path.exists(_test_db_path):
            os.unlink(_test_db_path)
    except PermissionError:
        pass
    for s in ["-wal", "-shm"]:
        try:
            if os.path.exists(_test_db_path + s):
                os.unlink(_test_db_path + s)
        except PermissionError:
            pass


atexit.register(_cleanup)