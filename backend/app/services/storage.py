import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from ..utils.config import DATABASE_PATH

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    updated_at TEXT,
    is_project INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_tags (
    user_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, tag_id)
);

CREATE TABLE IF NOT EXISTS managers (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_date TEXT PRIMARY KEY,
    taken_at TEXT NOT NULL,
    project_users INTEGER NOT NULL,
    total_users INTEGER NOT NULL,
    volunteers INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'live'
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_tags_tag ON user_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_users_project ON users(is_project);
"""


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


@contextmanager
def _transaction():
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    global _initialized
    with _init_lock:
        if _initialized:
            return
        with _transaction() as connection:
            connection.executescript(SCHEMA)
        _initialized = True


def reset_connection_state():
    """For tests: allow init_db to run again against a new database file."""
    global _initialized
    _initialized = False


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def replace_users(users, project_user_ids):
    init_db()
    project_ids = set(project_user_ids)
    fetched_at = _now()

    tag_rows = {}
    user_rows = []
    pair_rows = set()
    for user in users:
        user_id = user.get("id")
        if user_id is None:
            continue
        tags = user.get("tags") or []
        for tag in tags:
            if isinstance(tag, dict) and tag.get("id") is not None:
                tag_rows[tag["id"]] = tag.get("name", "")
                pair_rows.add((user_id, tag["id"]))
        user_rows.append(
            (
                user_id,
                user.get("createdAt"),
                user.get("updatedAt"),
                1 if user_id in project_ids else 0,
                fetched_at,
            )
        )

    with _transaction() as connection:
        connection.execute("DELETE FROM user_tags")
        connection.execute("DELETE FROM users")
        connection.execute("DELETE FROM tags")
        connection.executemany(
            "INSERT OR REPLACE INTO tags(id, name) VALUES (?, ?)",
            list(tag_rows.items()),
        )
        connection.executemany(
            "INSERT OR REPLACE INTO users"
            "(id, created_at, updated_at, is_project, fetched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            user_rows,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO user_tags(user_id, tag_id) VALUES (?, ?)",
            list(pair_rows),
        )

    logger.info(f"Сохранено пользователей: {len(user_rows)}, из них участников проекта: {len(project_ids)}")


def replace_managers(managers):
    init_db()
    fetched_at = _now()
    rows = [
        (
            manager.get("id"),
            manager.get("createdAt"),
            fetched_at,
        )
        for manager in managers
        if manager.get("id") is not None
    ]

    with _transaction() as connection:
        connection.execute("DELETE FROM managers")
        connection.executemany(
            "INSERT OR REPLACE INTO managers(id, created_at, fetched_at) "
            "VALUES (?, ?, ?)",
            rows,
        )

    logger.info(f"Сохранено волонтёров: {len(rows)}")


def upsert_snapshot(snapshot_date, taken_at, project_users, total_users, volunteers, source="live"):
    init_db()
    with _transaction() as connection:
        connection.execute(
            "INSERT INTO snapshots"
            "(snapshot_date, taken_at, project_users, total_users, volunteers, source) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(snapshot_date) DO UPDATE SET "
            "taken_at = excluded.taken_at, "
            "project_users = excluded.project_users, "
            "total_users = excluded.total_users, "
            "volunteers = excluded.volunteers, "
            "source = excluded.source",
            (snapshot_date, taken_at, project_users, total_users, volunteers, source),
        )


def insert_snapshots(rows, source="backfill"):
    """rows: iterable of (snapshot_date, taken_at, project_users, total_users, volunteers)."""
    init_db()
    payload = [(row[0], row[1], row[2], row[3], row[4], source) for row in rows]
    if not payload:
        return
    with _transaction() as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO snapshots"
            "(snapshot_date, taken_at, project_users, total_users, volunteers, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            payload,
        )


def get_latest_snapshot():
    init_db()
    with _transaction() as connection:
        row = connection.execute(
            "SELECT * FROM snapshots ORDER BY snapshot_date DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_snapshot_before(day: str):
    init_db()
    with _transaction() as connection:
        row = connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_date < ? "
            "ORDER BY snapshot_date DESC LIMIT 1",
            (day,),
        ).fetchone()
    return dict(row) if row else None


def get_snapshots(start_date: str, end_date: str):
    init_db()
    with _transaction() as connection:
        rows = connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_date BETWEEN ? AND ? "
            "ORDER BY snapshot_date ASC",
            (start_date, end_date),
        ).fetchall()
    return [dict(row) for row in rows]


def min_snapshot_date():
    init_db()
    with _transaction() as connection:
        row = connection.execute("SELECT MIN(snapshot_date) AS day FROM snapshots").fetchone()
    return row["day"] if row and row["day"] else None


def get_all_user_created_dates():
    init_db()
    with _transaction() as connection:
        rows = connection.execute(
            "SELECT created_at FROM users WHERE created_at IS NOT NULL"
        ).fetchall()
    return [row["created_at"] for row in rows]


def get_project_created_dates():
    init_db()
    with _transaction() as connection:
        rows = connection.execute(
            "SELECT created_at FROM users "
            "WHERE is_project = 1 AND created_at IS NOT NULL"
        ).fetchall()
    return [row["created_at"] for row in rows]


def get_manager_created_dates():
    init_db()
    with _transaction() as connection:
        rows = connection.execute(
            "SELECT created_at FROM managers WHERE created_at IS NOT NULL"
        ).fetchall()
    return [row["created_at"] for row in rows]


def set_meta(key: str, value: str):
    init_db()
    with _transaction() as connection:
        connection.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_meta(key: str, default=None):
    init_db()
    with _transaction() as connection:
        row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default
