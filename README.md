# elo-f1

**This is a private project (`github.com/thompgt/elo-f1`). Keep the repo
private — don't make it public or share the data outside the existing
remote.**

## What this is

An Elo-style rating system for Formula 1 drivers that tries to isolate *driving
quality* from car quality and luck. Standard points/wins standings conflate all
three. This project instead compares teammates head-to-head (since teammates
share identical machinery within a season) using classic Elo math, so that:

- Beating a stronger teammate (e.g. Hamilton against Rosberg/Bottas/Russell)
  earns more rating than beating a weaker one (e.g. a driver alongside a
  clearly weaker teammate).
- A driver who outdrives a mediocre car (Alonso 2023, Hamilton 2018) is
  rewarded relative to raw finishing position.
- Crash-caused DNFs apply an explicit rating penalty, scaled up when the car
  that weekend was strong (throwing away a winning car is a worse signal than
  binning a backmarker) and scaled down when the car was weak.

See `PLAN.md` for the full architecture, database schema, and Elo algorithm
specification.

## Data sources

- [Jolpica-F1](https://api.jolpi.ca/) — community successor to the defunct
  Ergast API, same JSON shape. Requires a browser-like `User-Agent` header.
- [FastF1](https://github.com/theOehrly/Fast-F1) — Python library wrapping
  official F1 timing data, used for lap-time telemetry from 2018 onward only.

## Season scope

1980–present. Ratings before 2018 use a results/qualifying-derived proxy for
car strength; 2018+ additionally uses FastF1 lap-time telemetry.

## Setup

```
pip install -e .
python -m elo_f1.ingestion.run_ingest --from 1980 --to 2026
python -m elo_f1.ingestion.run_car_strength                      # Tier A, all seasons (fast, local)
python -m elo_f1.ingestion.run_car_strength --fastf1-from 2018 --fastf1-to 2025   # Tier B, optional (slow)
python -m elo_f1.elo.run_elo
uvicorn elo_f1.api.main:app --reload
```

`run_ingest` is resumable — re-running it skips seasons already marked done in
`ingestion_progress` and retries anything that previously failed (e.g. Jolpica
rate limits). The FastF1 telemetry pass is opt-in and heavy (one full session
download+parse per race weekend); skip it and the Elo engine falls back to the
Tier A proxy for those seasons.

Run `python scripts/inspect_db.py` for row-count sanity checks per season and a
spot-check of known storylines (Verstappen/Perez, Hamilton/Rosberg, Alonso/Stroll).

## Notebooks

`notebooks/elo_standings_by_season.ipynb` lists every season's driver
standings ordered by end-of-season Elo, one season per cell (1980–present).
Requires the notebook extras: `pip install -e ".[notebooks]"`.

Then, in `frontend/`:

```
npm install
npm run dev
```
