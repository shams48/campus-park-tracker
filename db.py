import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "campus_park.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS lots (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    capacity INTEGER NOT NULL CHECK (capacity > 0)
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id     INTEGER NOT NULL REFERENCES lots(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('in', 'out')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_lot ON events(lot_id);
"""

SEED_LOTS = [
    ("Lot A", 20),
    ("Lot B", 15),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute("SELECT COUNT(*) FROM lots").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO lots (name, capacity) VALUES (?, ?)",
                SEED_LOTS,
            )


def get_lot(lot_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, capacity FROM lots WHERE id = ?", (lot_id,)
        ).fetchone()
        return dict(row) if row else None


def get_occupancy(lot_id: int) -> int:
    # Derived from event log: each 'in' adds 1, each 'out' subtracts 1.
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
              SUM(CASE WHEN event_type = 'in'  THEN 1 ELSE 0 END) -
              SUM(CASE WHEN event_type = 'out' THEN 1 ELSE 0 END) AS occupancy
            FROM events
            WHERE lot_id = ?
            """,
            (lot_id,),
        ).fetchone()
        return int(row["occupancy"] or 0)


def get_lots_with_occupancy() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
              l.id,
              l.name,
              l.capacity,
              COALESCE(SUM(CASE WHEN e.event_type = 'in'  THEN 1 ELSE 0 END), 0) -
              COALESCE(SUM(CASE WHEN e.event_type = 'out' THEN 1 ELSE 0 END), 0) AS occupancy
            FROM lots l
            LEFT JOIN events e ON e.lot_id = l.id
            GROUP BY l.id, l.name, l.capacity
            ORDER BY l.id
            """
        ).fetchall()
        return [dict(r) for r in rows]


def record_event(lot_id: int, event_type: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (lot_id, event_type) VALUES (?, ?)",
            (lot_id, event_type),
        )


def list_events(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.event_type, e.created_at,
                   l.id AS lot_id, l.name AS lot_name
            FROM events e
            JOIN lots l ON l.id = e.lot_id
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_event(event_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        return cur.rowcount > 0


def get_history(lot_id: int, since_iso: str) -> tuple[int, list[dict]]:
    """Return (baseline_at_window_start, events_inside_window)."""
    with get_conn() as conn:
        baseline_row = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN event_type = 'in'  THEN 1 ELSE 0 END), 0) -
              COALESCE(SUM(CASE WHEN event_type = 'out' THEN 1 ELSE 0 END), 0) AS baseline
            FROM events
            WHERE lot_id = ? AND created_at < ?
            """,
            (lot_id, since_iso),
        ).fetchone()
        events = conn.execute(
            """
            SELECT event_type, created_at
            FROM events
            WHERE lot_id = ? AND created_at >= ?
            ORDER BY created_at ASC, id ASC
            """,
            (lot_id, since_iso),
        ).fetchall()
        return int(baseline_row["baseline"] or 0), [dict(e) for e in events]
