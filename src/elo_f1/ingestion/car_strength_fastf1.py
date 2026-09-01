"""Tier B car-strength-relative-to-field signal, derived from FastF1 clean-air lap
times (2018+ only). Green-flag laps (IsAccurate, no pit in/out, no SC/VSC) are
aggregated per constructor and z-scored across the field for that race weekend,
same scale/shape as the Tier A ergast_proxy signal so the Elo engine can consume
either interchangeably (see car_strength_weekend.tier).
"""

import json
import sqlite3
import statistics

TIER = "fastf1_telemetry"

# FastF1 TrackStatus digit '1' means all-clear/green flag; anything else (SC, VSC,
# red flag, yellow) is excluded to avoid pace being skewed by non-racing conditions.
_GREEN_FLAG = "1"


def _zscore(value: float, values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return 0.0
    return (value - mean) / stdev


def compute_for_race(conn: sqlite3.Connection, race_id: str) -> None:
    # Map fastf1 3-letter driver code -> our constructor_id for this specific race,
    # using the already-ingested Ergast race_results as the canonical source (a
    # driver's FastF1 "Team" string doesn't always match our constructor_id spelling).
    code_to_constructor = dict(
        conn.execute(
            """
            SELECT d.code, rr.constructor_id
            FROM race_results rr
            JOIN drivers d ON d.driver_id = rr.driver_id
            WHERE rr.race_id = ?
            """,
            (race_id,),
        ).fetchall()
    )
    if not code_to_constructor:
        return

    laps = conn.execute(
        """
        SELECT driver_id AS code, lap_time_ms, is_accurate, track_status
        FROM fastf1_lap_samples
        WHERE race_id = ?
        """,
        (race_id,),
    ).fetchall()

    lap_times_by_constructor: dict[str, list[int]] = {}
    for lap in laps:
        if not lap["is_accurate"]:
            continue
        if lap["track_status"] not in (_GREEN_FLAG, str(_GREEN_FLAG)):
            continue
        constructor_id = code_to_constructor.get(lap["code"])
        if constructor_id is None or lap["lap_time_ms"] is None:
            continue
        lap_times_by_constructor.setdefault(constructor_id, []).append(lap["lap_time_ms"])

    medians = {
        cid: statistics.median(times) for cid, times in lap_times_by_constructor.items() if len(times) >= 3
    }
    if len(medians) < 2:
        return

    values = list(medians.values())
    for cid, median_ms in medians.items():
        # Faster (lower) median lap time -> higher strength, so invert the z-score.
        strength_score = -_zscore(median_ms, values)
        conn.execute(
            """
            INSERT INTO car_strength_weekend (race_id, constructor_id, tier, strength_score, strength_components_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(race_id, constructor_id, tier) DO UPDATE SET
                strength_score=excluded.strength_score,
                strength_components_json=excluded.strength_components_json
            """,
            (
                race_id,
                cid,
                TIER,
                strength_score,
                json.dumps({"median_green_flag_lap_ms": median_ms, "sample_size": len(lap_times_by_constructor[cid])}),
            ),
        )


def compute_all(conn: sqlite3.Connection, year_from: int = 2018, year_to: int | None = None) -> None:
    from elo_f1.storage import repositories as repo

    races = repo.get_races_in_order(conn, year_from, year_to)
    for race in races:
        compute_for_race(conn, race["race_id"])
    conn.commit()
