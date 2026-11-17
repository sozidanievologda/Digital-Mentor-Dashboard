import os
import tempfile
from pathlib import Path

import pytest

_TMP_DIR = Path(tempfile.mkdtemp(prefix="dm-tests-"))

# Must be set before the app modules import config.
os.environ.setdefault("MOYKLASS_API_KEY", "test-api-key")
os.environ.setdefault("DASHBOARD_USERNAME", "tester")
os.environ.setdefault("DASHBOARD_PASSWORD", "secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("PROJECT_TAG_PREFIX", "ФПГ_ЦН")
os.environ["DATABASE_PATH"] = str(_TMP_DIR / "dashboard.db")


@pytest.fixture(autouse=True)
def clean_database():
    from app.services import storage

    for suffix in ("", "-wal", "-shm"):
        path = Path(os.environ["DATABASE_PATH"] + suffix)
        if path.exists():
            path.unlink()
    storage.reset_connection_state()
    storage.init_db()
    yield
