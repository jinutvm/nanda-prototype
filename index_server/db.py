import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

DB_PATH = Path(__file__).parent / "nanda_index.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id                    TEXT PRIMARY KEY,
                agent_name            TEXT UNIQUE NOT NULL,
                primary_facts_url     TEXT NOT NULL,
                private_facts_url     TEXT,
                adaptive_resolver_url TEXT,
                ttl                   INTEGER NOT NULL DEFAULT 3600,
                registered_at         TEXT NOT NULL,
                updated_at            TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resolution_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name   TEXT NOT NULL,
                resolved_at  TEXT NOT NULL,
                client_hint  TEXT
            );
        """)


def register_agent(agent_data: dict) -> dict:
    """Insert a new agent row. Returns the full record as a dict."""
    now = _now()
    agent_id = f"nanda:{uuid4()}"
    row = {
        "id":                    agent_id,
        "agent_name":            agent_data["agent_name"],
        "primary_facts_url":     agent_data["primary_facts_url"],
        "private_facts_url":     agent_data.get("private_facts_url"),
        "adaptive_resolver_url": agent_data.get("adaptive_resolver_url"),
        "ttl":                   agent_data.get("ttl", 3600),
        "registered_at":         now,
        "updated_at":            now,
    }
    with _conn() as con:
        con.execute(
            """
            INSERT INTO agents
                (id, agent_name, primary_facts_url, private_facts_url,
                 adaptive_resolver_url, ttl, registered_at, updated_at)
            VALUES
                (:id, :agent_name, :primary_facts_url, :private_facts_url,
                 :adaptive_resolver_url, :ttl, :registered_at, :updated_at)
            """,
            row,
        )
    return row


def get_agent(agent_name: str) -> Optional[dict]:
    """Return the agent row for agent_name, or None if not found."""
    with _conn() as con:
        cur = con.execute(
            "SELECT * FROM agents WHERE agent_name = ?", (agent_name,)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def log_resolution(agent_name: str, client_hint: Optional[str] = None) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO resolution_log (agent_name, resolved_at, client_hint) VALUES (?, ?, ?)",
            (agent_name, _now(), client_hint),
        )


def get_all_agents() -> list[str]:
    """Return a list of all registered agent_names."""
    with _conn() as con:
        cur = con.execute("SELECT agent_name FROM agents ORDER BY registered_at")
        return [row["agent_name"] for row in cur.fetchall()]


def delete_agent(agent_name: str) -> bool:
    """Delete agent by agent_name. Returns True if a row was removed."""
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM agents WHERE agent_name = ?", (agent_name,)
        )
    return cur.rowcount > 0
