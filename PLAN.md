# elo-f1: Driving-Quality Elo Rating System

## Context

Standard F1 standings (points, wins) conflate car quality, luck, and driving skill.
The goal is a rating system that isolates *driving quality*: a driver who outdrives
a mediocre car (Alonso 2023, Hamilton 2018) should rate well; a driver who crashes
repeatedly despite having a dominant car (e.g. Verstappen 2017) should rate poorly.
The core mechanism: teammates share identical machinery, so comparing teammates
head-to-head with classic Elo math naturally controls for car quality, and naturally
weights wins over stronger teammates (Hamilton's teammates: Button, Rosberg, Bottas,
Russell) more than wins over weaker ones (Perez alongside Verstappen). Crash-caused
DNFs apply an explicit rating penalty, scaled by how strong the car was that weekend
(throwing away a dominant car is a worse signal than binning a backmarker).

This is a **local-only, never-pushed** project — no `git remote` is ever configured.
It's built at `~/elo-f1` (does not exist yet).

Stack (user-selected): Python (ingestion + Elo engine) + FastAPI (backend) + React
(frontend), SQLite storage. Data source: Jolpica-F1 API (Ergast's community successor
— confirmed reachable via `curl -A "Mozilla/5.0" https://api.jolpi.ca/ergast/f1/...`,
returns classic Ergast-shaped JSON with driverId/constructorId/grid/position/points/
status). Season scope: 1980–present. FastF1 (already pip-installed, v3.6.1) supplies
lap-time telemetry for 2018+ only, used to refine the car-strength-relative-to-field
signal for the modern era; 1980–2017 uses a results/qualifying-derived proxy instead.

## Repository Layout

```
~/elo-f1/
├── README.md              # states explicitly: local-only, never push, no remote
├── .gitignore              # data/elo_f1.db, data/raw_cache/, data/fastf1_cache/, node_modules, __pycache__
├── pyproject.toml
├── data/
│   ├── elo_f1.db
│   ├── raw_cache/          # cached raw Jolpica JSON, read-through cache
│   └── fastf1_cache/       # fastf1.Cache target
├── src/elo_f1/
│   ├── ingestion/
│   │   ├── jolpica_client.py    # HTTP client: browser UA, pagination, backoff, delay
│   │   ├── cache.py              # read-through JSON cache
│   │   ├── ergast_ingest.py      # pulls races/results/qualifying/standings/drivers/constructors
│   │   ├── fastf1_ingest.py      # 2018+: pulls session lap data -> fastf1_lap_samples
│   │   ├── car_strength_ergast.py   # Tier A car-strength proxy (pre-2018, derived from results)
│   │   ├── car_strength_fastf1.py   # Tier B car-strength (2018+, from lap-time telemetry)
│   │   ├── status_classifier.py  # maps Ergast `status` -> driver_fault/mechanical/finished/other
│   │   └── run_ingest.py         # CLI, resumable via ingestion_progress table
│   ├── storage/
│   │   ├── schema.sql / db.py / models.py / repositories.py
│   ├── elo/
│   │   ├── config.py       # K_QUALI, K_RACE, PENALTY_BASE, REGRESSION_FACTOR (tunable constants)
│   │   ├── match.py        # builds quali+race "matches" per teammate pair per weekend
│   │   ├── expected_score.py
│   │   ├── penalty.py      # crash/driver-error penalty, severity + car-strength scaling
│   │   ├── car_strength.py # unifies Tier A/B signal for the engine
│   │   ├── engine.py       # chronological pass 1980->present, writes driver_elo_history
│   │   ├── season_boundary.py  # regression-to-mean between seasons
│   │   └── run_elo.py      # CLI, full recompute
│   └── api/
│       ├── main.py, deps.py, schemas.py
│       └── routers/standings.py, drivers.py, seasons.py
└── frontend/               # Vite + React
    └── src/components/StandingsTable.tsx  # sortable: Driver, Team, Points, Elo
```

## Database Schema (SQLite)

- `drivers`, `constructors`, `seasons`, `races` — dimension tables mirroring Ergast IDs.
- `qualifying_results(race_id, driver_id, constructor_id, position, q1/q2/q3_time_ms)`
- `race_results(race_id, driver_id, constructor_id, grid, position, position_text, points, status, status_category, laps_completed, total_race_laps, fastest_lap_rank, time_ms)`
- `driver_standings` / `constructor_standings` — for the Points column and sanity checks.
- `car_strength_weekend(race_id, constructor_id, tier['ergast_proxy'|'fastf1_telemetry'], strength_score, strength_components_json)`
- `fastf1_lap_samples(race_id, driver_id, constructor_id, lap_number, lap_time_ms, is_accurate, compound, track_status)` — Tier B staging only.
- `driver_elo_history(race_id, driver_id, constructor_id, elo_before, elo_after_quali, elo_after_race, elo_after_penalty, quali_expected/actual_score, race_expected/actual_score, car_strength_adjustment, penalty_applied, had_teammate)` — append-only rating ledger.
- `driver_elo_season_summary(year, driver_id, constructor_id, elo_season_end, elo_season_start, elo_season_average, races_started, points, final_points_position)` — materialized for the UI.
- `ingestion_progress(endpoint, year, round, status, fetched_at)` — makes ingestion resumable.

## Elo Algorithm

**Matches** — per race weekend, per teammate pair (same `constructor_id`, same `race_id`):
1. *Qualifying match*: better `qualifying_results.position` wins (1/0).
2. *Race match*: better `race_results.position` wins; if one DNFs and the other
   classifies, the classified driver wins outright; if both DNF, skip (no signal).
Single-car entries / mid-season team changes: teammate pairing is derived live per
weekend from the roster — no persistent assignment.

**Core update** — standard logistic Elo, 400-point scale, initial rating 1500:
```
expected_A = 1 / (1 + 10^((elo_B - elo_A)/400))
new_elo_A = elo_A + K * (actual_A - expected_A)
```
`K_QUALI = 8`, `K_RACE = 16` (race outcome carries more signal than quali).
These are starting values in `elo/config.py`, to be tuned during Stage 3 sanity checks.

**Crash/driver-error penalty** (independent of teammate matches, not zero-sum):
- `status_classifier.py` maps raw `status` to `driver_fault` ("Accident", "Collision",
  "Spun off") vs `mechanical` (engine/gearbox/electrical/etc., not penalized) vs
  `finished`/`other`. Documented limitation: Ergast can't distinguish self-caused vs
  contact-caused incidents — mitigated by discounting "Collision" penalty vs "Accident".
- `penalty = PENALTY_BASE * severity_multiplier * car_strength_multiplier`
  - `severity_multiplier = clamp(1.0 - 0.5*(laps_completed/total_race_laps), 0.5, 1.0)` — early DNF costs more.
  - `car_strength_multiplier`: 1.2x if that car was top-quartile strength that weekend (threw away a winning car), 0.85x if bottom-quartile (less to lose) — this is what makes a dominant-car crasher (Verstappen 2017-style pattern) rate poorly.
  - `PENALTY_BASE`: 15 (Accident/Spun off), 10 (Collision), 8 (Disqualified).

**Car strength signal**: NOT folded into the teammate expected-score (already car-neutral
by construction — same car, same weekend); used only for penalty scaling above and
exposed as an auditability field (`car_strength_adjustment`). Tier A (1980–2017): derived
from qualifying gap to pole, finish-vs-grid delta, rolling constructor points-pace — pure
derivation from already-ingested Ergast data, no extra network calls. Tier B (2018+):
FastF1 clean-air lap-time z-scores across the field per weekend.

**Season carryover**: ratings persist continuously across seasons; at each season
boundary, regress toward the mean: `elo_start = 1500 + 0.75*(elo_end_prior - 1500)`.
New drivers start at 1500. A driver skipping N seasons regresses N times.

**Season-level display**: expose both `elo_season_end` (default, matches Points'
"cumulative as of season end" convention) and `elo_season_average` (more robust
measure of that season's driving quality, closer to the actual ask) — both are cheap
to compute and stored, so show both rather than forcing one choice.

## Staged Build Plan

1. **Bootstrap**: `git init` (no remote, ever), `.gitignore`, README stating this is
   local-only, `pyproject.toml` with deps (`httpx`, `fastf1`, `fastapi`, `uvicorn`,
   `pydantic`, `sqlalchemy` or raw `sqlite3`, `pytest`).
2. **Ingestion** (get 1980–present into SQLite before any Elo code): full schema
   created; `jolpica_client.py` with browser User-Agent + pagination + read-through
   cache; `ergast_ingest.py` pulls all seasons; `status_classifier.py` populates
   `status_category`. Done when every season 1980–present has plausible row counts
   for races/results/qualifying/standings.
3. **Car strength**: Tier A proxy computed from already-ingested data (all seasons);
   Tier B FastF1 extraction for 2018+ (resumable per-session, since this is slow/heavy).
   Spot-check known dominant seasons (2014/2023 for expected strength ordering).
4. **Elo engine**: implement match/expected_score/penalty/car_strength/season_boundary
   modules; `engine.py` does one chronological pass writing `driver_elo_history`;
   `run_elo.py` is a full-recompute CLI (cheap enough to not need incremental patching).
   Sanity-check against known storylines (Alonso/Stroll, Hamilton/Rosberg,
   Verstappen/Ricciardo, Verstappen/Perez) and tune constants in `elo/config.py`.
5. **API**: FastAPI serving `GET /api/seasons`, `GET /api/seasons/{year}/standings`
   (driver, team, points, elo_season_end, elo_season_average), `GET /api/drivers/{id}/history`.
6. **Frontend**: Vite + React, `StandingsTable.tsx` — sortable table with Driver, Team,
   Points, Elo Rating columns (toggle season-end vs season-average), `SeasonPicker.tsx`.

## Verification

- After ingestion: `scripts/inspect_db.py` row-count sanity check per season.
- After car-strength: spot-check 2014 (Mercedes dominance) and 2023 (Red Bull
  dominance) show expected relative strength ordering.
- After Elo engine: eyeball known storylines listed above for plausibility before
  trusting the numbers; adjust K-factors/penalty/regression constants accordingly.
- After API: `curl localhost:8000/api/seasons/2023/standings` returns valid JSON.
- After frontend: `npm run dev` + `uvicorn` running together, manually verify the
  standings table renders, sorts correctly by each column (especially Elo), and
  switching seasons works, for at least a handful of seasons across the range.

## Addendum: post-launch corrections and cross-team calibration

Three structural bugs surfaced during sanity-checking against known
storylines, all now fixed in `elo/match.py` and `elo/car_strength_ergast.py`:

1. **Ergast's `position` field is a classification/retirement order, not a
   finish flag.** A DNF still gets a `position` (e.g. a lap-25 retirement can
   still show `position=17`), with `status`/`position_text` marking it as a
   retirement. The original match-building code used `position IS NOT NULL`
   to mean "classified," which is true almost always — so the "one driver
   DNF'd" branch of the race-match logic essentially never ran, and two
   drivers where one had crashed out on lap 2 were still scored as a normal
   finishing-order comparison. Fixed to key off `status_category` instead.
2. **A teammate's mechanical DNF was being scored as a full win for the other
   driver.** Once (1) was fixed, this became visible: if one driver finishes
   and the other retires with an engine/gearbox/electrical failure, that is
   reliability luck, not a driving-quality signal — crediting it as a win
   re-introduces exactly the car-and-luck contamination the teammate-Elo
   design exists to strip out. A race match is now only scored when a DNF was
   the driver's own fault (`driver_fault`/`disqualified`); a teammate's
   mechanical retirement produces no match at all.
3. **The Tier A car-strength proxy's finish-vs-grid delta** had the same
   classification bug — it was reading retirement-order numbers as if they
   were real finishing positions. Restricted to drivers who actually finished.

**Cross-team calibration (`elo/cross_match.py`).** Even with those fixed, the
teammate-only design has a deeper limitation: it's an isolated two-player Elo
graph. A driver's rating only ever moves relative to their own teammate, so
two elite teammates who split results evenly stay pinned near 1500 no matter
how good they actually are, while a driver paired with a weak teammate can
drift far from that one reference point with nothing ever checking it against
the rest of the grid. Added a second signal: every classified driver is also
compared against every other classified driver on a different team that
weekend, with the expected score computed from each driver's Elo *handicapped*
by their car's field-relative strength that weekend
(`CAR_TO_ELO_SCALE * strength_z`). A result the car alone already predicted
barely moves either rating; only genuine over- or under-performance relative
to the car does. This runs at a lower K (`K_CROSS`) than the true car-neutral
teammate matches (`K_RACE`), since it depends on the car-strength estimate
being roughly right rather than on identical machinery. `K_RACE`/`K_QUALI`
were also rebalanced down slightly (16→12, 8→6) so this second signal isn't
swamped by two-driver-pair dominance.

Known open tension: even after this, some backmarker-team drivers who clearly
outperform both their own teammate and their car's predicted finishing order
across a season (e.g. Albon at Williams) rate above points-comparable
front-runners. This may be partly correct under the model's own stated goal
(reward outdriving your machinery) rather than purely a bug — it wasn't
chased further to avoid hand-tuning constants to match specific drivers'
expected rankings rather than encoding a generalizable rule. Worth
revisiting with more historical validation if it keeps showing up.

## Addendum 2: pair-familiarity decay

A long-tenured, one-sided teammate pairing (same two drivers, same team, many
consecutive seasons, one side essentially never winning) was compounding the
stronger driver's rating upward every single season without bound, while the
weaker side spiraled down with no floor — a multi-season driver comparison
(Schumacher 2000-2004) showed the expected saturate-then-plateau pattern, but
a longer, more one-sided modern pairing did not.

Root cause: standard Elo's expected-score saturation (as a rating gap grows,
further wins from the favorite move the needle less) only bites hard at very
large gaps under this project's `K_RACE`/`ELO_SCALE`, and a 20-24 race season
provides enough repeated trials that even a "mostly saturated" per-race gain
still sums to tens of points a year, indefinitely, as long as the weaker side
never once wins. Two fixes were tried and rejected before landing on the
real one:

- *Weakening season-boundary regression* (retaining more of the prior
  rating) was tried first, on the theory that regression was "resetting the
  surprise" each winter and re-opening room for another season of large
  gains. Tested and made it **worse** — weaker regression let the losing
  side's rating carry over too, so the gap widened *faster*, not slower.
- *Confidence-scaled regression* (regress harder for sparse/rookie ratings,
  gentler for long track records) was considered to also help the "a bad
  rookie season permanently drags down a strong sophomore year" problem, but
  it pulls the long-tenured-rivalry problem in the opposite direction from
  what it needs, so the two issues can't share this lever.

The actual fix, in `elo/engine.py`'s new `PairFamiliarity` tracker: each
teammate matchup's effective K-factor decays hyperbolically with how many
races that *specific pair* has already raced together (`PAIR_FAMILIARITY_HALF_LIFE`
in `elo/config.py`), down to a floor (`PAIR_FAMILIARITY_FLOOR`) so a result
is never worth zero. This is standard statistical reasoning, not a
per-driver rule: the first race between two new teammates is strong evidence
about their relative gap; the 80th race confirming an already-well-established
gap is much weaker *new* evidence, since the variance on an estimated skill
gap shrinks as the sample size grows. A fresh pairing (new teammates,
mid-season swaps) is unaffected — the discount is keyed to the specific pair,
not either driver's career total. Re-verified after this change: 2017
Ricciardo/Verstappen ordering, and the 2012/1991/2004 season-leader checks,
all still hold; a long-dominant modern championship run's season-over-season
Elo growth is now flatter (yearly gains roughly halved in the case checked)
without erasing the fact that it was still a genuinely dominant, low-error
run.
