"""Database manager (SQLite) and rotating file logger setup."""
import logging
import os
import sqlite3
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "speed_logs.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "isplog.log")


def setup_logger(name: str = "isplog") -> logging.Logger:
    """Configure and return the application logger."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Rotating file handler — max 5 MB x 3 backups
    fh = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def init_database() -> None:
    """Initialize SQLite schema. Safe to call multiple times (IF NOT EXISTS)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Existing table — keep as-is
    cur.execute("""
        CREATE TABLE IF NOT EXISTS speed_tests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            download_mbps   REAL    NOT NULL,
            upload_mbps     REAL    NOT NULL,
            ping_ms         REAL    NOT NULL,
            below_threshold INTEGER DEFAULT 0
        )
    """)

    # New: downtime events table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS downtime_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT    NOT NULL,
            end_time   TEXT,
            duration_s REAL,
            reason     TEXT
        )
    """)

    conn.commit()
    conn.close()


def insert_speed_test(timestamp: str, download: float, upload: float,
                      ping: float, below: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO speed_tests (timestamp, download_mbps, upload_mbps, ping_ms, below_threshold)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, download, upload, ping, below))
    conn.commit()
    conn.close()


def insert_downtime(start_time: str, end_time: Optional[str] = None,
                    duration_s: Optional[float] = None, reason: str = "") -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO downtime_events (start_time, end_time, duration_s, reason)
        VALUES (?, ?, ?, ?)
    """, (start_time, end_time, duration_s, reason))
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_downtime(row_id: int, end_time: str, duration_s: float) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE downtime_events SET end_time=?, duration_s=? WHERE id=?
    """, (end_time, duration_s, row_id))
    conn.commit()
    conn.close()


def get_stats() -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM speed_tests")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM speed_tests WHERE below_threshold=1")
    below = cur.fetchone()[0]
    cur.execute("SELECT AVG(download_mbps), AVG(upload_mbps), AVG(ping_ms) FROM speed_tests")
    row = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM downtime_events")
    downtime_count = cur.fetchone()[0]
    conn.close()
    return {
        "total_tests": total,
        "below_threshold": below,
        "below_pct": round(below / total * 100 if total else 0, 1),
        "avg_download": round(row[0] or 0, 2),
        "avg_upload": round(row[1] or 0, 2),
        "avg_ping": round(row[2] or 0, 2),
        "downtime_events": downtime_count,
    }


def get_history(days: int = 7) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM speed_tests
        WHERE timestamp >= datetime('now', ?)
        ORDER BY timestamp DESC
    """, (f"-{days} days",))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_monthly_data(month: str) -> List[Dict[str, Any]]:
    """month format: YYYY-MM"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM speed_tests
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (month,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_downtime_events(days: int = 30) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM downtime_events
        WHERE start_time >= datetime('now', ?)
        ORDER BY start_time DESC
    """, (f"-{days} days",))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
