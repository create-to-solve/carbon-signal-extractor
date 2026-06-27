import os
import sqlite3
from pathlib import Path
from typing import Optional

DB_DIR = Path("data")
DB_PATH = DB_DIR / "app.db"

_SCHEMA_SOURCE_RUNS = """
CREATE TABLE IF NOT EXISTS source_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name    TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    fetched_at     TEXT NOT NULL,
    content_hash   TEXT,
    content_length INTEGER,
    status         TEXT NOT NULL
);
"""

_SCHEMA_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    detected_at     TEXT NOT NULL,
    headline        TEXT NOT NULL,
    why_it_matters  TEXT NOT NULL,
    who_is_affected TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    content_hash    TEXT
);
"""


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    with _connect() as conn:
        conn.execute(_SCHEMA_SOURCE_RUNS)
        conn.execute(_SCHEMA_SIGNALS)
        try:
            conn.execute("ALTER TABLE signals ADD COLUMN source_url TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists — safe to ignore
        conn.commit()


def get_last_hash(source_name: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT content_hash FROM source_runs
            WHERE source_name = ?
              AND status IN ('new', 'changed', 'unchanged')
              AND content_hash IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (source_name,),
        ).fetchone()
    return row[0] if row else None


def save_run(
    source_name: str,
    run_id: str,
    content_hash: Optional[str],
    content_length: int,
    status: str,
) -> None:
    from datetime import datetime

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO source_runs
                (source_name, run_id, fetched_at, content_hash, content_length, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_name,
                run_id,
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                content_hash,
                content_length,
                status,
            ),
        )
        conn.commit()


def save_signals(
    source_name: str,
    run_id: str,
    signals: list,
    content_hash: Optional[str],
    source_url: Optional[str] = None,
) -> None:
    if not signals:
        return
    from datetime import datetime

    detected_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    rows = [
        (
            source_name,
            run_id,
            detected_at,
            s["headline"],
            s["why_it_matters"],
            s["who_is_affected"],
            s["signal_type"],
            content_hash,
            source_url,
        )
        for s in signals
    ]
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO signals
                (source_name, run_id, detected_at, headline,
                 why_it_matters, who_is_affected, signal_type,
                 content_hash, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
