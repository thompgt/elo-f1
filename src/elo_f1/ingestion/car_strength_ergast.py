"""Tier A car-strength-relative-to-field proxy, derived purely from already-ingested
Ergast/Jolpica data (grid/finish positions, qualifying gaps, constructor points pace).
Used for all seasons as a baseline, and as the only signal for 1980-2017 (before
FastF1 telemetry coverage begins).

Produces one strength_score per constructor per race weekend, on a scale where
0 is average and positive means stronger than the field that weekend (implemented
as a z-score across constructors within the race).
"""

import json
import sqlite3
import statistics

from elo_f1.ingestion.status_classifier import FINISHED
from elo_f1.storage import repositories as repo

TIER = "ergast_proxy"


def _zscore(value: float, values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return 0.0
    return (value - mean) / stdev


def _representative_time_ms(q) -> int | None:
    """A driver's best time from the session(s) they actually reached: Q3 if
    they made it that far, else Q2, else Q1. Falls back through whichever
    columns are populated for the era (many pre-2000s seasons only have a
    single qualifying time recorded, in q1_time_ms)."""
    return q["q3_time_ms"] or q["q2_time_ms"] or q["q1_time_ms"]


def _quali_strength_by_time_gap(quali_rows: list) -> dict[str, float] | None:
    """Uses the actual qualifying time gap to pole, not ordinal position, so a
    car that's genuinely far clear of the field (a big percentage gap) reads
    as far stronger than one that merely edged pole in a tightly-matched
    field — position alone can't distinguish a 0.05s pole from a 1.5s one,
    which understates how dominant a truly dominant car was and lets its
    driver bank spurious "beat expectation" credit in cross_match.py for
    outcomes the car alone already fully explains. Returns None if fewer than
    two constructors have usable time data (caller falls back to position)."""
    best_time_by_constructor: dict[str, int] = {}
    for q in quali_rows:
        t = _representative_time_ms(q)
        if t is None:
            continue
        cid = q["constructor_id"]
        if cid not in best_time_by_constructor or t < best_time_by_constructor[cid]:
            best_time_by_constructor[cid] = t

    if len(best_time_by_constructor) < 2:
        return None

    pole_time = min(best_time_by_constructor.values())
    gap_pct_by_constructor = {
        cid: (t - pole_time) / pole_time * 100.0 for cid, t in best_time_by_constructor.items()
    }
    gap_values = list(gap_pct_by_constructor.values())
    # Smaller (better) gap -> higher strength.
    return {cid: -_zscore(gap, gap_values) for cid, gap in gap_pct_by_constructor.items()}


def compute_for_race(conn: sqlite3.Connection, race_id: str) -> None:
    quali_rows = repo.get_qualifying_for_race(conn, race_id)
    result_rows = repo.get_results_for_race(conn, race_id)

    quali_z_by_constructor = _quali_strength_by_time_gap(quali_rows)

    if quali_z_by_constructor is None:
        # Fallback for races with insufficient recorded lap times: ordinal
        # qualifying position, inverted and z-scored (loses dominance
        # magnitude, but better than no signal at all for those weekends).
        best_quali_by_constructor: dict[str, int] = {}
        for q in quali_rows:
            if q["position"] is None:
                continue
            cid = q["constructor_id"]
            if cid not in best_quali_by_constructor or q["position"] < best_quali_by_constructor[cid]:
                best_quali_by_constructor[cid] = q["position"]
        quali_positions = list(best_quali_by_constructor.values())
        quali_z_by_constructor = {
            cid: -_zscore(pos, quali_positions) for cid, pos in best_quali_by_constructor.items()
        }

    # Finish-vs-grid delta proxy: average (grid - finish position) per constructor,
    # positive means the team gained places on average that weekend. Restricted
    # to drivers who actually finished — Ergast's `position` for a DNF is a
    # retirement-order rank, not a real finishing position, so including it here
    # would read car pace off of who happened to retire in what order.
    grid_finish_delta: dict[str, list[float]] = {}
    for r in result_rows:
        cid = r["constructor_id"]
        if r["status_category"] == FINISHED and r["grid"] is not None and r["position"] is not None:
            grid_finish_delta.setdefault(cid, []).append(r["grid"] - r["position"])

    constructors = set(quali_z_by_constructor) | set(grid_finish_delta)
    if len(constructors) < 2:
        return

    delta_avgs = {cid: statistics.mean(vals) for cid, vals in grid_finish_delta.items()}
    delta_values = list(delta_avgs.values())
    delta_z_by_constructor = {cid: _zscore(v, delta_values) for cid, v in delta_avgs.items()}

    for cid in constructors:
        quali_z = quali_z_by_constructor.get(cid, 0.0)
        delta_z = delta_z_by_constructor.get(cid, 0.0)
        # Weight qualifying pace higher than race-day position swings, which are
        # noisier (incidents, strategy, safety cars).
        strength_score = 0.7 * quali_z + 0.3 * delta_z
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
                json.dumps({"quali_zscore": quali_z, "grid_finish_delta_zscore": delta_z}),
            ),
        )


def compute_all(conn: sqlite3.Connection, year_from: int | None = None, year_to: int | None = None) -> None:
    races = repo.get_races_in_order(conn, year_from, year_to)
    for race in races:
        compute_for_race(conn, race["race_id"])
    conn.commit()
