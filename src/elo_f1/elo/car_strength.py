"""Unifies Tier A (ergast_proxy) and Tier B (fastf1_telemetry) car-strength
signals into one lookup for the Elo engine, per PLAN.md 3.4: fastf1_telemetry
is preferred when available for a constructor/race, else ergast_proxy."""

import sqlite3

from elo_f1.storage import repositories as repo


def get_strength_by_constructor(conn: sqlite3.Connection, race_id: str) -> dict[str, float]:
    rows = repo.get_car_strength_for_weekend(conn, race_id)
    return {constructor_id: row["strength_score"] for constructor_id, row in rows.items()}
