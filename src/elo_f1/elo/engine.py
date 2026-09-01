"""Single chronological pass over all races (1980-present), maintaining and
recording driver Elo ratings. See PLAN.md section 3 for the full spec.

Each season is computed entirely independently: every driver starts each
season at INITIAL_RATING, and no rating or pair-familiarity state carries
across a season boundary. This is a deliberate design choice (see PLAN.md
addendum 3) — the project measures how strong a given SEASON was, not a
career trajectory, so a season's rating should reflect only what happened
that season, not a prior year's form (good or bad).

Full recompute on every run (cheap enough not to need incremental patching):
clears driver_elo_history / driver_elo_season_summary and rebuilds from
race_results / qualifying_results / car_strength_weekend.
"""

import sqlite3

from elo_f1.elo import penalty
from elo_f1.elo.car_strength import get_strength_by_constructor
from elo_f1.elo.config import (
    INITIAL_RATING,
    K_CROSS,
    K_QUALI,
    K_RACE,
    PAIR_FAMILIARITY_FLOOR,
    PAIR_FAMILIARITY_HALF_LIFE,
)
from elo_f1.elo.cross_match import compute_cross_deltas
from elo_f1.elo.expected_score import expected_score, update
from elo_f1.elo.match import build_qualifying_matches, build_race_matches
from elo_f1.ingestion.status_classifier import DISQUALIFIED, DRIVER_FAULT
from elo_f1.storage import repositories as repo


class RatingBook:
    """Tracks each driver's current rating within a single season. A fresh
    RatingBook is created for every season (see `run`), so every driver
    starts here at INITIAL_RATING regardless of how any prior season went."""

    def __init__(self) -> None:
        self.ratings: dict[str, float] = {}

    def get(self, driver_id: str) -> float:
        return self.ratings.setdefault(driver_id, INITIAL_RATING)

    def set(self, driver_id: str, rating: float) -> None:
        self.ratings[driver_id] = rating


class PairFamiliarity:
    """Tracks how many matches two drivers have had as teammates so far THIS
    SEASON (a fresh instance is created every season, same as RatingBook), so
    the matches elo/match.py produces can be discounted for repeated
    head-to-heads between the same two people within the season — see
    PAIR_FAMILIARITY_HALF_LIFE in elo/config.py."""

    def __init__(self) -> None:
        self.counts: dict[frozenset, int] = {}

    def k_multiplier(self, driver_a: str, driver_b: str) -> float:
        n = self.counts.get(frozenset((driver_a, driver_b)), 0)
        decay = PAIR_FAMILIARITY_HALF_LIFE / (PAIR_FAMILIARITY_HALF_LIFE + n)
        return PAIR_FAMILIARITY_FLOOR + (1 - PAIR_FAMILIARITY_FLOOR) * decay

    def record(self, driver_a: str, driver_b: str) -> None:
        key = frozenset((driver_a, driver_b))
        self.counts[key] = self.counts.get(key, 0) + 1


def _clear_derived_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM driver_elo_history")
    conn.execute("DELETE FROM driver_elo_season_summary")
    conn.commit()


def run(conn: sqlite3.Connection) -> None:
    _clear_derived_tables(conn)
    season_records: dict[tuple[int, str], dict] = {}

    races = repo.get_races_in_order(conn)
    book = None
    familiarity = None
    current_year = None
    for race in races:
        race_id = race["race_id"]
        year = race["year"]

        if year != current_year:
            # New season: reset ratings AND pair-familiarity to a clean slate.
            # Nothing about a prior season's results or a rivalry's history
            # carries forward — each season is judged entirely on its own.
            book = RatingBook()
            familiarity = PairFamiliarity()
            current_year = year

        result_rows = repo.get_results_for_race(conn, race_id)
        if not result_rows:
            continue

        # Only consider qualifying entries for drivers who also appear in this
        # weekend's race results — a driver who qualified but never raced (DNS,
        # or a data gap) has no race-side signal to pair with theirs.
        result_driver_ids = {r["driver_id"] for r in result_rows}
        quali_rows = [
            q for q in repo.get_qualifying_for_race(conn, race_id) if q["driver_id"] in result_driver_ids
        ]

        strength_by_constructor = get_strength_by_constructor(conn, race_id)

        elo_before = {r["driver_id"]: book.get(r["driver_id"]) for r in result_rows}
        elo_after_quali = dict(elo_before)
        quali_score = {r["driver_id"]: (None, None) for r in result_rows}

        for m in build_qualifying_matches(quali_rows):
            k = K_QUALI * familiarity.k_multiplier(m.driver_a, m.driver_b)
            ea = expected_score(elo_after_quali[m.driver_a], elo_after_quali[m.driver_b])
            eb = 1.0 - ea
            elo_after_quali[m.driver_a] = update(elo_after_quali[m.driver_a], ea, m.actual_a, k)
            elo_after_quali[m.driver_b] = update(elo_after_quali[m.driver_b], eb, m.actual_b, k)
            quali_score[m.driver_a] = (ea, m.actual_a)
            quali_score[m.driver_b] = (eb, m.actual_b)

        elo_after_race = dict(elo_after_quali)
        race_score = {r["driver_id"]: (None, None) for r in result_rows}

        for m in build_race_matches(result_rows):
            k = K_RACE * familiarity.k_multiplier(m.driver_a, m.driver_b)
            ea = expected_score(elo_after_race[m.driver_a], elo_after_race[m.driver_b])
            eb = 1.0 - ea
            elo_after_race[m.driver_a] = update(elo_after_race[m.driver_a], ea, m.actual_a, k)
            elo_after_race[m.driver_b] = update(elo_after_race[m.driver_b], eb, m.actual_b, k)
            race_score[m.driver_a] = (ea, m.actual_a)
            race_score[m.driver_b] = (eb, m.actual_b)

        # Cross-team calibration (elo/cross_match.py): every classified driver
        # against every other, expected score handicapped by car strength, so
        # only over/under-performance relative to the car moves the needle.
        cross_deltas = compute_cross_deltas(result_rows, elo_after_race, strength_by_constructor)
        for driver_id, delta in cross_deltas.items():
            elo_after_race[driver_id] += K_CROSS * delta

        had_teammate = {r["driver_id"]: False for r in result_rows}
        by_constructor: dict[str, list] = {}
        for r in result_rows:
            by_constructor.setdefault(r["constructor_id"], []).append(r)
        for rows in by_constructor.values():
            if len(rows) == 2:
                for r in rows:
                    had_teammate[r["driver_id"]] = True
                familiarity.record(rows[0]["driver_id"], rows[1]["driver_id"])

        elo_after_penalty = dict(elo_after_race)
        penalty_applied = {r["driver_id"]: 0.0 for r in result_rows}

        for r in result_rows:
            driver_id = r["driver_id"]
            if r["status_category"] in (DRIVER_FAULT, DISQUALIFIED):
                p = penalty.compute_penalty(
                    status=r["status"],
                    status_category=r["status_category"],
                    laps_completed=r["laps_completed"],
                    total_race_laps=r["total_race_laps"],
                    car_strength_score=strength_by_constructor.get(r["constructor_id"]),
                )
                penalty_applied[driver_id] = p
                elo_after_penalty[driver_id] -= p

        for r in result_rows:
            driver_id = r["driver_id"]
            book.set(driver_id, elo_after_penalty[driver_id])

            qe, qa = quali_score[driver_id]
            re_, ra = race_score[driver_id]
            conn.execute(
                """
                INSERT INTO driver_elo_history
                    (race_id, driver_id, constructor_id, elo_before, elo_after_quali,
                     elo_after_race, elo_after_penalty, quali_expected_score, quali_actual_score,
                     race_expected_score, race_actual_score, car_strength_adjustment,
                     penalty_applied, had_teammate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    race_id,
                    driver_id,
                    r["constructor_id"],
                    elo_before[driver_id],
                    elo_after_quali[driver_id],
                    elo_after_race[driver_id],
                    elo_after_penalty[driver_id],
                    qe,
                    qa,
                    re_,
                    ra,
                    strength_by_constructor.get(r["constructor_id"]),
                    penalty_applied[driver_id],
                    had_teammate[driver_id],
                ),
            )

            key = (year, driver_id)
            rec = season_records.setdefault(
                key,
                {"constructor_counts": {}, "elo_values": [], "elo_start": elo_before[driver_id], "races": 0},
            )
            rec["constructor_counts"][r["constructor_id"]] = rec["constructor_counts"].get(r["constructor_id"], 0) + 1
            rec["elo_values"].append(elo_after_penalty[driver_id])
            rec["races"] += 1
            rec["elo_end"] = elo_after_penalty[driver_id]

    conn.commit()
    _write_season_summary(conn, season_records)


def _write_season_summary(conn: sqlite3.Connection, season_records: dict[tuple[int, str], dict]) -> None:
    for (year, driver_id), rec in season_records.items():
        primary_constructor = max(rec["constructor_counts"], key=rec["constructor_counts"].get)
        elo_average = sum(rec["elo_values"]) / len(rec["elo_values"])

        standing = conn.execute(
            "SELECT points, position FROM driver_standings WHERE year=? AND driver_id=?",
            (year, driver_id),
        ).fetchone()

        conn.execute(
            """
            INSERT INTO driver_elo_season_summary
                (year, driver_id, constructor_id, elo_season_start, elo_season_end,
                 elo_season_average, races_started, points, final_points_position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(year, driver_id) DO UPDATE SET
                constructor_id=excluded.constructor_id,
                elo_season_start=excluded.elo_season_start,
                elo_season_end=excluded.elo_season_end,
                elo_season_average=excluded.elo_season_average,
                races_started=excluded.races_started,
                points=excluded.points,
                final_points_position=excluded.final_points_position
            """,
            (
                year,
                driver_id,
                primary_constructor,
                rec["elo_start"],
                rec["elo_end"],
                elo_average,
                rec["races"],
                standing["points"] if standing else None,
                standing["position"] if standing else None,
            ),
        )
    conn.commit()
