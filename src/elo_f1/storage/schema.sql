-- elo-f1 SQLite schema

CREATE TABLE IF NOT EXISTS drivers (
    driver_id TEXT PRIMARY KEY,
    code TEXT,
    given_name TEXT,
    family_name TEXT,
    date_of_birth TEXT,
    nationality TEXT
);

CREATE TABLE IF NOT EXISTS constructors (
    constructor_id TEXT PRIMARY KEY,
    name TEXT,
    nationality TEXT
);

CREATE TABLE IF NOT EXISTS seasons (
    year INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS races (
    race_id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    round INTEGER NOT NULL,
    race_name TEXT,
    circuit_id TEXT,
    date TEXT,
    has_fastf1_telemetry INTEGER NOT NULL DEFAULT 0,
    UNIQUE(year, round)
);

CREATE TABLE IF NOT EXISTS qualifying_results (
    race_id TEXT NOT NULL REFERENCES races(race_id),
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id TEXT NOT NULL REFERENCES constructors(constructor_id),
    position INTEGER,
    q1_time_ms INTEGER,
    q2_time_ms INTEGER,
    q3_time_ms INTEGER,
    PRIMARY KEY (race_id, driver_id)
);

CREATE TABLE IF NOT EXISTS race_results (
    race_id TEXT NOT NULL REFERENCES races(race_id),
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id TEXT NOT NULL REFERENCES constructors(constructor_id),
    grid INTEGER,
    position INTEGER,
    position_text TEXT,
    points REAL,
    status TEXT,
    status_category TEXT,
    laps_completed INTEGER,
    total_race_laps INTEGER,
    fastest_lap_rank INTEGER,
    fastest_lap_time_ms INTEGER,
    time_ms INTEGER,
    PRIMARY KEY (race_id, driver_id)
);

CREATE TABLE IF NOT EXISTS driver_standings (
    year INTEGER NOT NULL,
    round INTEGER NOT NULL,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    points REAL,
    position INTEGER,
    wins INTEGER,
    PRIMARY KEY (year, round, driver_id)
);

CREATE TABLE IF NOT EXISTS constructor_standings (
    year INTEGER NOT NULL,
    round INTEGER NOT NULL,
    constructor_id TEXT NOT NULL REFERENCES constructors(constructor_id),
    points REAL,
    position INTEGER,
    wins INTEGER,
    PRIMARY KEY (year, round, constructor_id)
);

CREATE TABLE IF NOT EXISTS car_strength_weekend (
    race_id TEXT NOT NULL REFERENCES races(race_id),
    constructor_id TEXT NOT NULL REFERENCES constructors(constructor_id),
    tier TEXT NOT NULL CHECK (tier IN ('ergast_proxy', 'fastf1_telemetry')),
    strength_score REAL,
    strength_components_json TEXT,
    PRIMARY KEY (race_id, constructor_id, tier)
);

CREATE TABLE IF NOT EXISTS fastf1_lap_samples (
    race_id TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    constructor_id TEXT NOT NULL,
    lap_number INTEGER,
    lap_time_ms INTEGER,
    is_accurate INTEGER,
    compound TEXT,
    track_status TEXT
);

CREATE INDEX IF NOT EXISTS idx_fastf1_lap_samples_race
    ON fastf1_lap_samples(race_id, constructor_id);

CREATE TABLE IF NOT EXISTS driver_elo_history (
    race_id TEXT NOT NULL REFERENCES races(race_id),
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id TEXT NOT NULL REFERENCES constructors(constructor_id),
    elo_before REAL NOT NULL,
    elo_after_quali REAL NOT NULL,
    elo_after_race REAL NOT NULL,
    elo_after_penalty REAL NOT NULL,
    quali_expected_score REAL,
    quali_actual_score REAL,
    race_expected_score REAL,
    race_actual_score REAL,
    car_strength_adjustment REAL,
    penalty_applied REAL NOT NULL DEFAULT 0,
    had_teammate INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (race_id, driver_id)
);

CREATE TABLE IF NOT EXISTS driver_elo_season_summary (
    year INTEGER NOT NULL,
    driver_id TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id TEXT,
    elo_season_start REAL,
    elo_season_end REAL,
    elo_season_average REAL,
    races_started INTEGER,
    points REAL,
    final_points_position INTEGER,
    PRIMARY KEY (year, driver_id)
);

CREATE TABLE IF NOT EXISTS ingestion_progress (
    endpoint TEXT NOT NULL,
    year INTEGER NOT NULL,
    round INTEGER,
    status TEXT NOT NULL CHECK (status IN ('pending', 'done', 'failed')),
    fetched_at TEXT,
    PRIMARY KEY (endpoint, year, round)
);
