from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from tracesurface.config import DEFAULT_SETTINGS

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_home() -> Path:
    base = os.environ.get("TRACESURFACE_HOME")
    home = Path(base).expanduser() if base else Path.home() / ".tracesurface"

    (home / "responses").mkdir(parents=True, exist_ok=True)
    (home / "logs").mkdir(parents=True, exist_ok=True)
    return home


def db_path() -> Path:
    return get_home() / "tracesurface.db"


def response_file(replay_id: int) -> Path:
    return get_home() / "responses" / f"{replay_id}.bin"


def cdp_response_file(req_id: int) -> Path:
    return get_home() / "responses" / f"cdp_{req_id}.bin"


def auth_path() -> Path:
    return get_home() / "auth.json"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path(),
        isolation_level=None,
        timeout=DEFAULT_SETTINGS.storage.sqlite_busy_timeout_s,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    get_home()
    conn = connect()
    try:
        apply_migrations(conn)
    finally:
        conn.close()


def apply_migrations(conn: sqlite3.Connection) -> None:
    had_migration_table = _table_exists(conn, "schema_migrations")
    has_existing_schema = _table_exists(conn, "scans")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, "
        "applied_at INTEGER NOT NULL)"
    )

    if has_existing_schema and not had_migration_table:
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
            (1, int(time.time())),
        )

    applied = {
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for migration in _migration_files():
        version = _migration_version(migration)
        if version in applied:
            continue
        _apply_migration(conn, version, migration)
        applied.add(version)


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _migration_version(path: Path) -> int:
    return int(path.name.split("_", 1)[0])


def _apply_migration(conn: sqlite3.Connection, version: int, migration: Path) -> None:
    applied_at = int(time.time())
    script = migration.read_text(encoding="utf-8")
    try:
        conn.executescript(
            "BEGIN IMMEDIATE;\n"
            f"{script}\n"
            "INSERT INTO schema_migrations(version, applied_at) "
            f"VALUES({version}, {applied_at});\n"
            "COMMIT;"
        )
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None
