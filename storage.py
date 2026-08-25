"""
SQLite storage for:
  - content_history: every generated + published post (with its full chain)
  - pending_approvals: one-time tokens for the email "POST THIS" / "REGENERATE" links
  - leads: schema stub for Phase 5 (Typeform -> Google Sheet). Not populated yet,
    but present so future phases don't require a migration.
"""
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS content_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    title TEXT NOT NULL,
    audience TEXT,
    pillar TEXT,
    hook TEXT,
    full_thread_json TEXT NOT NULL,   -- JSON list of post strings, in order
    status TEXT NOT NULL DEFAULT 'proposed',  -- proposed | approved | rejected | published
    threads_post_id TEXT,             -- id of the first post in the published chain
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_approvals (
    token TEXT PRIMARY KEY,
    batch_date TEXT NOT NULL,
    content_id INTEGER,               -- NULL for a batch-level "regenerate" token
    kind TEXT NOT NULL,                -- 'approve' | 'regenerate'
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (content_id) REFERENCES content_history (id)
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    whatsapp TEXT,
    budget TEXT,
    preferred_location TEXT,
    alternative_location TEXT,
    property_type TEXT,
    buy_or_rent TEXT,
    bedrooms TEXT,
    bathrooms TEXT,
    land_size TEXT,
    building_size TEXT,
    purpose TEXT,
    timeline TEXT,
    requirements TEXT,
    source_post_id INTEGER,           -- FK -> content_history.id
    date TEXT,
    lead_status TEXT DEFAULT 'new',
    FOREIGN KEY (source_post_id) REFERENCES content_history (id)
);
"""


@contextmanager
def get_conn():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------- content_history ----------

def save_proposed_content(date: str, title: str, audience: str, pillar: str,
                           hook: str, thread_posts: list) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO content_history
               (date, title, audience, pillar, hook, full_thread_json, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'proposed', ?)""",
            (date, title, audience, pillar, hook, json.dumps(thread_posts, ensure_ascii=False),
             datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_content(content_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM content_history WHERE id = ?", (content_id,)).fetchone()
        return dict(row) if row else None


def update_status(content_id: int, status: str, threads_post_id: str = None):
    with get_conn() as conn:
        if threads_post_id is not None:
            conn.execute(
                "UPDATE content_history SET status = ?, threads_post_id = ? WHERE id = ?",
                (status, threads_post_id, content_id),
            )
        else:
            conn.execute("UPDATE content_history SET status = ? WHERE id = ?", (status, content_id))


def recent_history(limit: int = 30):
    """Used to avoid repeating topics/hooks — pulled into the content-generation prompt."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date, title, audience, pillar, hook, status FROM content_history "
            "ORDER BY date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def batch_for_date(date: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM content_history WHERE date = ? ORDER BY id", (date,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- pending_approvals ----------

def create_token(batch_date: str, kind: str, content_id: int = None) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires = now + timedelta(hours=config.APPROVAL_TOKEN_TTL_HOURS)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO pending_approvals
               (token, batch_date, content_id, kind, created_at, expires_at, used)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (token, batch_date, content_id, kind, now.isoformat(), expires.isoformat()),
        )
    return token


def consume_token(token: str):
    """Returns the row dict if valid+unused+unexpired, else None. Marks it used."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM pending_approvals WHERE token = ?", (token,)).fetchone()
        if not row:
            return None
        row = dict(row)
        if row["used"]:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
            return None
        conn.execute("UPDATE pending_approvals SET used = 1 WHERE token = ?", (token,))
        return row
