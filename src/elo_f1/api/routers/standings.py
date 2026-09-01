import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from elo_f1.api.deps import get_db
from elo_f1.api.schemas import StandingsRow

router = APIRouter()


@router.get("/api/seasons/{year}/standings", response_model=list[StandingsRow])
def get_standings(year: int, conn: sqlite3.Connection = Depends(get_db)) -> list[StandingsRow]:
    rows = conn.execute(
        """
        SELECT
            s.driver_id,
            d.given_name || ' ' || d.family_name AS driver_name,
            s.constructor_id,
            c.name AS constructor_name,
            s.points,
            s.elo_season_end,
            s.elo_season_average,
            s.final_points_position,
            s.races_started
        FROM driver_elo_season_summary s
        JOIN drivers d ON d.driver_id = s.driver_id
        JOIN constructors c ON c.constructor_id = s.constructor_id
        WHERE s.year = ?
        ORDER BY s.elo_season_end DESC
        """,
        (year,),
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No standings for season {year}")

    return [StandingsRow(**dict(r)) for r in rows]
