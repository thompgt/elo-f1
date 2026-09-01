import sqlite3
from collections.abc import Iterator

from elo_f1.storage.db import get_connection


def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
