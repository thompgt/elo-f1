"""Pulls races, results, qualifying, and season-end standings from Jolpica-F1
for a range of seasons and upserts them into SQLite. Resumable via
ingestion_progress: re-running skips (season, endpoint) pairs already done.
"""

import datetime as dt
import sqlite3

from elo_f1.ingestion import jolpica_client as client
from elo_f1.ingestion.status_classifier import classify
from elo_f1.ingestion.time_parse import lap_time_to_ms, race_time_to_ms
from elo_f1.storage import repositories as repo

FASTF1_START_YEAR = 2018


def _race_id(year: int, round_: int) -> str:
    return f"{year}_{round_}"


def _upsert_driver_and_constructor(conn: sqlite3.Connection, driver: dict, constructor: dict) -> None:
    repo.upsert_driver(
        conn,
        {
            "driver_id": driver["driverId"],
            "given_name": driver.get("givenName"),
            "family_name": driver.get("familyName"),
            "date_of_birth": driver.get("dateOfBirth"),
            "nationality": driver.get("nationality"),
        },
    )
    repo.upsert_constructor(
        conn,
        {
            "constructor_id": constructor["constructorId"],
            "name": constructor.get("name"),
            "nationality": constructor.get("nationality"),
        },
    )


def ingest_season_races(conn: sqlite3.Connection, year: int) -> list[dict]:
    """Ingests the race schedule for a season; returns the raw race dicts."""
    if repo.is_done(conn, "races", year):
        return client.fetch_all(f"{year}/races")

    races = client.fetch_all(f"{year}/races")
    repo.upsert_season(conn, year)
    for race in races:
        round_ = int(race["round"])
        repo.upsert_race(
            conn,
            {
                "race_id": _race_id(year, round_),
                "year": year,
                "round": round_,
                "race_name": race.get("raceName"),
                "circuit_id": race.get("Circuit", {}).get("circuitId"),
                "date": race.get("date"),
                "has_fastf1_telemetry": int(year >= FASTF1_START_YEAR),
            },
        )
    conn.commit()
    repo.mark_progress(conn, "races", year, None, "done", dt.datetime.utcnow().isoformat())
    conn.commit()
    return races


def ingest_season_results(conn: sqlite3.Connection, year: int) -> None:
    if repo.is_done(conn, "results", year):
        return

    races = client.fetch_all(f"{year}/results")
    for race in races:
        round_ = int(race["round"])
        race_id = _race_id(year, round_)
        results = race.get("Results", [])
        total_laps = max((int(r.get("laps", 0) or 0) for r in results), default=None)
        for r in results:
            _upsert_driver_and_constructor(conn, r["Driver"], r["Constructor"])
            status = r.get("status", "")
            repo.upsert_race_result(
                conn,
                {
                    "race_id": race_id,
                    "driver_id": r["Driver"]["driverId"],
                    "constructor_id": r["Constructor"]["constructorId"],
                    "grid": int(r["grid"]) if r.get("grid") not in (None, "") else None,
                    "position": int(r["position"]) if r.get("position") not in (None, "") else None,
                    "position_text": r.get("positionText"),
                    "points": float(r["points"]) if r.get("points") not in (None, "") else None,
                    "status": status,
                    "status_category": classify(status),
                    "laps_completed": int(r["laps"]) if r.get("laps") not in (None, "") else None,
                    "total_race_laps": total_laps,
                    "fastest_lap_rank": int(r["FastestLap"]["rank"]) if r.get("FastestLap", {}).get("rank") else None,
                    "fastest_lap_time_ms": lap_time_to_ms(r.get("FastestLap", {}).get("Time", {}).get("time")),
                    "time_ms": race_time_to_ms(r.get("Time")),
                },
            )
    conn.commit()
    repo.mark_progress(conn, "results", year, None, "done", dt.datetime.utcnow().isoformat())
    conn.commit()


def ingest_season_qualifying(conn: sqlite3.Connection, year: int) -> None:
    if repo.is_done(conn, "qualifying", year):
        return

    races = client.fetch_all(f"{year}/qualifying")
    for race in races:
        round_ = int(race["round"])
        race_id = _race_id(year, round_)
        for q in race.get("QualifyingResults", []):
            _upsert_driver_and_constructor(conn, q["Driver"], q["Constructor"])
            repo.upsert_qualifying_result(
                conn,
                {
                    "race_id": race_id,
                    "driver_id": q["Driver"]["driverId"],
                    "constructor_id": q["Constructor"]["constructorId"],
                    "position": int(q["position"]) if q.get("position") not in (None, "") else None,
                    "q1_time_ms": lap_time_to_ms(q.get("Q1")),
                    "q2_time_ms": lap_time_to_ms(q.get("Q2")),
                    "q3_time_ms": lap_time_to_ms(q.get("Q3")),
                },
            )
    conn.commit()
    repo.mark_progress(conn, "qualifying", year, None, "done", dt.datetime.utcnow().isoformat())
    conn.commit()


def ingest_season_standings(conn: sqlite3.Connection, year: int) -> None:
    """Season-end standings only (one snapshot per season, not per round) —
    sufficient for the Points column and season summary; avoids one request
    per round per season."""
    if repo.is_done(conn, "standings", year):
        return

    races = repo.get_races_in_order(conn, year_from=year, year_to=year)
    final_round = max((r["round"] for r in races), default=0)

    driver_lists = client.fetch_standings_lists(f"{year}/driverStandings")
    for standings_list in driver_lists:
        for s in standings_list.get("DriverStandings", []):
            _upsert_driver_and_constructor(
                conn, s["Driver"], s["Constructors"][-1] if s.get("Constructors") else {"constructorId": "unknown"}
            )
            repo.upsert_driver_standing(
                conn,
                {
                    "year": year,
                    "round": final_round,
                    "driver_id": s["Driver"]["driverId"],
                    "points": float(s["points"]) if s.get("points") not in (None, "") else None,
                    "position": int(s["position"]) if s.get("position") not in (None, "") else None,
                    "wins": int(s["wins"]) if s.get("wins") not in (None, "") else None,
                },
            )

    constructor_lists = client.fetch_standings_lists(f"{year}/constructorStandings")
    for standings_list in constructor_lists:
        for s in standings_list.get("ConstructorStandings", []):
            repo.upsert_constructor(
                conn,
                {
                    "constructor_id": s["Constructor"]["constructorId"],
                    "name": s["Constructor"].get("name"),
                    "nationality": s["Constructor"].get("nationality"),
                },
            )
            repo.upsert_constructor_standing(
                conn,
                {
                    "year": year,
                    "round": final_round,
                    "constructor_id": s["Constructor"]["constructorId"],
                    "points": float(s["points"]) if s.get("points") not in (None, "") else None,
                    "position": int(s["position"]) if s.get("position") not in (None, "") else None,
                    "wins": int(s["wins"]) if s.get("wins") not in (None, "") else None,
                },
            )

    conn.commit()
    repo.mark_progress(conn, "standings", year, None, "done", dt.datetime.utcnow().isoformat())
    conn.commit()


def ingest_season(conn: sqlite3.Connection, year: int) -> None:
    ingest_season_races(conn, year)
    ingest_season_results(conn, year)
    ingest_season_qualifying(conn, year)
    ingest_season_standings(conn, year)
