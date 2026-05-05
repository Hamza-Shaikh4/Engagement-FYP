"""This file opens the database and sets up the tables."""

import sqlite3
from datetime import datetime, timezone

from config import DB_PATH, SCHEMA_PATH


def get_db() -> sqlite3.Connection:
    """Open a connection to the SQLite database."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO string."""
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """Create database tables from schema.sql."""
    connection = get_db()

    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        connection.executescript(schema_file.read())

    connection.commit()
    connection.close()