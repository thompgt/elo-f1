# elo-f1

**This is a private, local-only project. Do not add a git remote or push this
repository anywhere (GitHub, GitLab, or otherwise).**

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
python -m elo_f1.elo.run_elo
uvicorn elo_f1.api.main:app --reload
```

Then, in `frontend/`:

```
npm install
npm run dev
```
