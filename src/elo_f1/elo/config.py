"""Tunable Elo constants (see PLAN.md section 3). Starting values to be tuned
against known storylines during Stage 3 sanity checks."""

INITIAL_RATING = 1500.0
ELO_SCALE = 400.0

K_QUALI = 6.0
K_RACE = 12.0

# Cross-team calibration (see elo/cross_match.py): the teammate matches above
# are an isolated two-player graph with no connection to the rest of the grid,
# so a driver's rating only ever reflects dominance over their own teammate.
# Cross matches pit every classified driver against every other classified
# driver on a different team, with the expected score computed from each
# driver's Elo *handicapped* by their car's strength that weekend
# (CAR_TO_ELO_SCALE * strength z-score) — so a result the car alone already
# predicted barely moves anyone's rating, and only genuine over/under-
# performance relative to the car does. This is what gives every driver real
# edges to the whole field, not just their own teammate, anchoring ratings to
# a common scale. K_CROSS is kept below K_RACE since these are noisier,
# car-strength-estimate-dependent comparisons.
CAR_TO_ELO_SCALE = 400.0  # 1 std dev of car strength ~ a 400-point Elo edge (~91% win expectancy)
K_CROSS = 8.0

# Crash/driver-error penalty base magnitudes, by status_category / fault type.
PENALTY_SINGLE_CAR_FAULT = 15.0  # Accident, Spun off
PENALTY_CONTACT_FAULT = 10.0  # Collision, Collision damage (ambiguous fault)
PENALTY_DISQUALIFIED = 8.0

# Severity scaling by how early in the race the DNF happened.
SEVERITY_MIN_MULTIPLIER = 0.5
SEVERITY_MAX_MULTIPLIER = 1.0

# Car-strength scaling of the penalty: a driver-fault DNF in a top-quartile car
# is a worse signal (threw away a winning car) than in a bottom-quartile car.
CAR_STRENGTH_TOP_QUARTILE_MULTIPLIER = 1.2
CAR_STRENGTH_BOTTOM_QUARTILE_MULTIPLIER = 0.85
CAR_STRENGTH_QUARTILE_Z_THRESHOLD = 0.6745  # ~top/bottom 25% of a normal distribution

# Regression to the mean applied once at each season boundary.
REGRESSION_FACTOR = 0.75  # fraction of prior rating retained; rest regresses to INITIAL_RATING

# Familiarity discount on repeated teammate matchups (applied in elo/engine.py
# to the matches elo/match.py produces): the FIRST time two drivers race as
# teammates, each
# result is strong evidence about their relative skill gap. The 80th time the
# same two drivers race as teammates, another result confirming the
# already-well-established gap is much weaker NEW evidence — the variance on
# an estimated win rate shrinks as the sample size grows, so each additional
# trial should move the estimate less. Without this, a long-running,
# lopsided pairing (same two drivers, same team, many consecutive seasons)
# keeps compounding the leader's rating upward every season indefinitely,
# since nothing about repeat information should keep producing full-sized
# updates. K for a given pair decays hyperbolically with career matches
# already played between that specific pair, down to a floor (never zero —
# every race is still a real result) rather than resetting between seasons.
PAIR_FAMILIARITY_HALF_LIFE = 20.0  # career matches between a pair before K is halved
PAIR_FAMILIARITY_FLOOR = 0.35  # minimum fraction of K retained no matter how long the rivalry runs
