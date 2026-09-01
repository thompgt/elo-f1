"""Pulls race-session lap data from FastF1 for seasons >= 2018 and stores clean-air
lap samples in `fastf1_lap_samples`, feeding car_strength_fastf1.py.

This is the slow/heavy ingestion tier: each session load downloads and parses a
full timing dataset. FastF1's own on-disk cache (data/fastf1_cache/) avoids
re-downloading across runs, and ingestion_progress checkpoints per (year, round)
so an interrupted run can resume without re-processing completed sessions.
"""

import datetime as dt
import sqlite3
from pathlib import Path

import fastf1

from elo_f1.storage import repositories as repo

REPO_ROOT = Path(__file__).resolve().parents[3]
FASTF1_CACHE_DIR = REPO_ROOT / "data" / "fastf1_cache"

_cache_enabled = False


def _ensure_cache() -> None:
    global _cache_enabled
    if not _cache_enabled:
        FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))
        _cache_enabled = True


def ingest_race_session(conn: sqlite3.Connection, year: int, round_: int) -> None:
    if repo.is_done(conn, "fastf1_session", year, round_):
        return

    _ensure_cache()
    race_id = f"{year}_{round_}"

    try:
        session = fastf1.get_session(year, round_, "R")
        session.load(telemetry=False, weather=False, messages=False)
    except Exception as exc:  # noqa: BLE001 - some sessions have no FastF1 data
        print(f"  skip FastF1 {year} round {round_}: {exc}")
        repo.mark_progress(conn, "fastf1_session", year, round_, "failed", dt.datetime.utcnow().isoformat())
        conn.commit()
        return

    laps = session.laps
    for _, lap in laps.iterrows():
        driver_id = lap.get("Driver")
        team = lap.get("Team")
        if driver_id is None or lap.get("LapTime") is None:
            continue
        conn.execute(
            """
            INSERT INTO fastf1_lap_samples
                (race_id, driver_id, constructor_id, lap_number, lap_time_ms, is_accurate, compound, track_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                race_id,
                driver_id,
                team,
                int(lap.get("LapNumber")) if lap.get("LapNumber") == lap.get("LapNumber") else None,
                int(lap["LapTime"].total_seconds() * 1000),
                bool(lap.get("IsAccurate", False)),
                lap.get("Compound"),
                str(lap.get("TrackStatus")),
            ),
        )
    conn.commit()
    repo.mark_progress(conn, "fastf1_session", year, round_, "done", dt.datetime.utcnow().isoformat())
    conn.commit()


def ingest_seasons(conn: sqlite3.Connection, year_from: int, year_to: int) -> None:
    races = repo.get_races_in_order(conn, year_from, year_to)
    for race in races:
        if race["year"] < 2018:
            continue
        print(f"FastF1: {race['year']} round {race['round']} ({race['race_name']})")
        ingest_race_session(conn, race["year"], race["round"])
