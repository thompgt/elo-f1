import sqlite3

from fastapi import APIRouter, Depends

from elo_f1.api.deps import get_db

router = APIRouter()


@router.get("/api/seasons")
def list_seasons(conn: sqlite3.Connection = Depends(get_db)) -> list[int]:
    rows = conn.execute(
        "SELECT DISTINCT year FROM driver_elo_season_summary ORDER BY year"
    ).fetchall()
    return [r["year"] for r in rows]
