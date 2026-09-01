"""Upsert and query helpers shared by ingestion, the Elo engine, and the API."""

import sqlite3


def upsert_driver(conn: sqlite3.Connection, d: dict) -> None:
    d = {**d, "code": d.get("code")}
    conn.execute(
        """
        INSERT INTO drivers (driver_id, code, given_name, family_name, date_of_birth, nationality)
        VALUES (:driver_id, :code, :given_name, :family_name, :date_of_birth, :nationality)
        ON CONFLICT(driver_id) DO UPDATE SET
            code=COALESCE(excluded.code, drivers.code),
            given_name=excluded.given_name,
            family_name=excluded.family_name,
            date_of_birth=excluded.date_of_birth,
            nationality=excluded.nationality
        """,
        d,
    )


def upsert_constructor(conn: sqlite3.Connection, c: dict) -> None:
    conn.execute(
        """
        INSERT INTO constructors (constructor_id, name, nationality)
        VALUES (:constructor_id, :name, :nationality)
        ON CONFLICT(constructor_id) DO UPDATE SET
            name=excluded.name,
            nationality=excluded.nationality
        """,
        c,
    )


def upsert_season(conn: sqlite3.Connection, year: int) -> None:
    conn.execute("INSERT OR IGNORE INTO seasons (year) VALUES (?)", (year,))


def upsert_race(conn: sqlite3.Connection, r: dict) -> None:
    conn.execute(
        """
        INSERT INTO races (race_id, year, round, race_name, circuit_id, date, has_fastf1_telemetry)
        VALUES (:race_id, :year, :round, :race_name, :circuit_id, :date, :has_fastf1_telemetry)
        ON CONFLICT(race_id) DO UPDATE SET
            race_name=excluded.race_name,
            circuit_id=excluded.circuit_id,
            date=excluded.date,
            has_fastf1_telemetry=excluded.has_fastf1_telemetry
        """,
        r,
    )


def upsert_qualifying_result(conn: sqlite3.Connection, q: dict) -> None:
    conn.execute(
        """
        INSERT INTO qualifying_results
            (race_id, driver_id, constructor_id, position, q1_time_ms, q2_time_ms, q3_time_ms)
        VALUES (:race_id, :driver_id, :constructor_id, :position, :q1_time_ms, :q2_time_ms, :q3_time_ms)
        ON CONFLICT(race_id, driver_id) DO UPDATE SET
            constructor_id=excluded.constructor_id,
            position=excluded.position,
            q1_time_ms=excluded.q1_time_ms,
            q2_time_ms=excluded.q2_time_ms,
            q3_time_ms=excluded.q3_time_ms
        """,
        q,
    )


def upsert_race_result(conn: sqlite3.Connection, r: dict) -> None:
    conn.execute(
        """
        INSERT INTO race_results
            (race_id, driver_id, constructor_id, grid, position, position_text, points,
             status, status_category, laps_completed, total_race_laps,
             fastest_lap_rank, fastest_lap_time_ms, time_ms)
        VALUES
            (:race_id, :driver_id, :constructor_id, :grid, :position, :position_text, :points,
             :status, :status_category, :laps_completed, :total_race_laps,
             :fastest_lap_rank, :fastest_lap_time_ms, :time_ms)
        ON CONFLICT(race_id, driver_id) DO UPDATE SET
            constructor_id=excluded.constructor_id,
            grid=excluded.grid,
            position=excluded.position,
            position_text=excluded.position_text,
            points=excluded.points,
            status=excluded.status,
            status_category=excluded.status_category,
            laps_completed=excluded.laps_completed,
            total_race_laps=excluded.total_race_laps,
            fastest_lap_rank=excluded.fastest_lap_rank,
            fastest_lap_time_ms=excluded.fastest_lap_time_ms,
            time_ms=excluded.time_ms
        """,
        r,
    )


def upsert_driver_standing(conn: sqlite3.Connection, s: dict) -> None:
    conn.execute(
        """
        INSERT INTO driver_standings (year, round, driver_id, points, position, wins)
        VALUES (:year, :round, :driver_id, :points, :position, :wins)
        ON CONFLICT(year, round, driver_id) DO UPDATE SET
            points=excluded.points,
            position=excluded.position,
            wins=excluded.wins
        """,
        s,
    )


def upsert_constructor_standing(conn: sqlite3.Connection, s: dict) -> None:
    conn.execute(
        """
        INSERT INTO constructor_standings (year, round, constructor_id, points, position, wins)
        VALUES (:year, :round, :constructor_id, :points, :position, :wins)
        ON CONFLICT(year, round, constructor_id) DO UPDATE SET
            points=excluded.points,
            position=excluded.position,
            wins=excluded.wins
        """,
        s,
    )


def mark_progress(conn: sqlite3.Connection, endpoint: str, year: int, round_: int | None, status: str, fetched_at: str) -> None:
    conn.execute(
        """
        INSERT INTO ingestion_progress (endpoint, year, round, status, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(endpoint, year, round) DO UPDATE SET
            status=excluded.status,
            fetched_at=excluded.fetched_at
        """,
        (endpoint, year, round_, status, fetched_at),
    )


def is_done(conn: sqlite3.Connection, endpoint: str, year: int, round_: int | None = None) -> bool:
    row = conn.execute(
        "SELECT status FROM ingestion_progress WHERE endpoint=? AND year=? AND round IS ?",
        (endpoint, year, round_),
    ).fetchone()
    return bool(row) and row["status"] == "done"


def get_races_in_order(conn: sqlite3.Connection, year_from: int | None = None, year_to: int | None = None) -> list[sqlite3.Row]:
    query = "SELECT * FROM races WHERE 1=1"
    params: list = []
    if year_from is not None:
        query += " AND year >= ?"
        params.append(year_from)
    if year_to is not None:
        query += " AND year <= ?"
        params.append(year_to)
    query += " ORDER BY date, round"
    return conn.execute(query, params).fetchall()


def get_qualifying_for_race(conn: sqlite3.Connection, race_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM qualifying_results WHERE race_id = ?", (race_id,)
    ).fetchall()


def get_results_for_race(conn: sqlite3.Connection, race_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM race_results WHERE race_id = ?", (race_id,)
    ).fetchall()


def get_car_strength_for_weekend(conn: sqlite3.Connection, race_id: str) -> dict[str, sqlite3.Row]:
    """One row per constructor for this race, preferring fastf1_telemetry over ergast_proxy."""
    rows = conn.execute(
        "SELECT * FROM car_strength_weekend WHERE race_id = ?", (race_id,)
    ).fetchall()
    by_constructor: dict[str, sqlite3.Row] = {}
    for row in rows:
        existing = by_constructor.get(row["constructor_id"])
        if existing is None or row["tier"] == "fastf1_telemetry":
            by_constructor[row["constructor_id"]] = row
    return by_constructor
