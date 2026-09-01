import sqlite3

from fastapi import APIRouter, Depends

from elo_f1.api.deps import get_db
from elo_f1.api.schemas import DriverRaceHistoryRow

router = APIRouter()


@router.get("/api/drivers/{driver_id}/history", response_model=list[DriverRaceHistoryRow])
def get_driver_history(driver_id: str, conn: sqlite3.Connection = Depends(get_db)) -> list[DriverRaceHistoryRow]:
    rows = conn.execute(
        """
        SELECT h.race_id, r.race_name, r.date, h.elo_before, h.elo_after_penalty, h.penalty_applied
        FROM driver_elo_history h
        JOIN races r ON r.race_id = h.race_id
        WHERE h.driver_id = ?
        ORDER BY r.date
        """,
        (driver_id,),
    ).fetchall()
    return [DriverRaceHistoryRow(**dict(r)) for r in rows]
