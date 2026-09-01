"""Single chronological pass over all races (1980-present), maintaining and
recording driver Elo ratings. See PLAN.md section 3 for the full spec.

Full recompute on every run (cheap enough not to need incremental patching):
clears driver_elo_history / driver_elo_season_summary and rebuilds from
race_results / qualifying_results / car_strength_weekend.
"""

import sqlite3

from elo_f1.elo import penalty
from elo_f1.elo.car_strength import get_strength_by_constructor
from elo_f1.elo.config import INITIAL_RATING, K_CROSS, K_QUALI, K_RACE
from elo_f1.elo.cross_match import compute_cross_deltas
from elo_f1.elo.expected_score import expected_score, update
from elo_f1.elo.match import build_qualifying_matches, build_race_matches
from elo_f1.elo.season_boundary import regress
from elo_f1.ingestion.status_classifier import DISQUALIFIED, DRIVER_FAULT
from elo_f1.storage import repositories as repo


class RatingBook:
    """Tracks each driver's current rating and the last season they raced in,
    so season-boundary regression can be applied lazily as gaps are crossed."""

    def __init__(self) -> None:
        self.ratings: dict[str, float] = {}
        self.last_season: dict[str, int] = {}

    def get(self, driver_id: str, year: int) -> float:
        if driver_id not in self.ratings:
            self.ratings[driver_id] = INITIAL_RATING
            self.last_season[driver_id] = year
            return self.ratings[driver_id]

        last = self.last_season[driver_id]
        if year > last:
            skipped = max(0, (year - last) - 1)
            self.ratings[driver_id] = regress(self.ratings[driver_id], seasons_skipped=skipped)
            self.last_season[driver_id] = year
        return self.ratings[driver_id]

    def set(self, driver_id: str, rating: float, year: int) -> None:
        self.ratings[driver_id] = rating
        self.last_season[driver_id] = year


def _clear_derived_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM driver_elo_history")
    conn.execute("DELETE FROM driver_elo_season_summary")
    conn.commit()


def run(conn: sqlite3.Connection) -> None:
    _clear_derived_tables(conn)
    book = RatingBook()
    season_records: dict[tuple[int, str], dict] = {}

    races = repo.get_races_in_order(conn)
    for race in races:
        race_id = race["race_id"]
        year = race["year"]

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

        elo_before = {r["driver_id"]: book.get(r["driver_id"], year) for r in result_rows}
        elo_after_quali = dict(elo_before)
        quali_score = {r["driver_id"]: (None, None) for r in result_rows}

        for m in build_qualifying_matches(quali_rows):
            ea = expected_score(elo_after_quali[m.driver_a], elo_after_quali[m.driver_b])
            eb = 1.0 - ea
            elo_after_quali[m.driver_a] = update(elo_after_quali[m.driver_a], ea, m.actual_a, K_QUALI)
            elo_after_quali[m.driver_b] = update(elo_after_quali[m.driver_b], eb, m.actual_b, K_QUALI)
            quali_score[m.driver_a] = (ea, m.actual_a)
            quali_score[m.driver_b] = (eb, m.actual_b)

        elo_after_race = dict(elo_after_quali)
        race_score = {r["driver_id"]: (None, None) for r in result_rows}

        for m in build_race_matches(result_rows):
            ea = expected_score(elo_after_race[m.driver_a], elo_after_race[m.driver_b])
            eb = 1.0 - ea
            elo_after_race[m.driver_a] = update(elo_after_race[m.driver_a], ea, m.actual_a, K_RACE)
            elo_after_race[m.driver_b] = update(elo_after_race[m.driver_b], eb, m.actual_b, K_RACE)
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
            book.set(driver_id, elo_after_penalty[driver_id], year)

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
