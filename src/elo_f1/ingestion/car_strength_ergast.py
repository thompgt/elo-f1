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


def compute_for_race(conn: sqlite3.Connection, race_id: str) -> None:
    quali_rows = repo.get_qualifying_for_race(conn, race_id)
    result_rows = repo.get_results_for_race(conn, race_id)

    # Qualifying gap proxy: constructor's best qualifying position that weekend,
    # inverted and z-scored so a lower (better) position -> higher strength.
    best_quali_by_constructor: dict[str, int] = {}
    for q in quali_rows:
        if q["position"] is None:
            continue
        cid = q["constructor_id"]
        if cid not in best_quali_by_constructor or q["position"] < best_quali_by_constructor[cid]:
            best_quali_by_constructor[cid] = q["position"]

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

    constructors = set(best_quali_by_constructor) | set(grid_finish_delta)
    if len(constructors) < 2:
        return

    quali_positions = list(best_quali_by_constructor.values())
    quali_z_by_constructor = {
        cid: -_zscore(pos, quali_positions) for cid, pos in best_quali_by_constructor.items()
    }

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
