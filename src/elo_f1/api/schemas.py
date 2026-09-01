from pydantic import BaseModel


class StandingsRow(BaseModel):
    driver_id: str
    driver_name: str
    constructor_id: str
    constructor_name: str
    points: float | None
    elo_season_end: float
    elo_season_average: float
    final_points_position: int | None
    races_started: int


class SeasonSummary(BaseModel):
    year: int


class DriverRaceHistoryRow(BaseModel):
    race_id: str
    race_name: str
    date: str
    elo_before: float
    elo_after_penalty: float
    penalty_applied: float
