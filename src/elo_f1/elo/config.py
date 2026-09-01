"""Tunable Elo constants (see PLAN.md section 3). Starting values to be tuned
against known storylines during Stage 3 sanity checks."""

INITIAL_RATING = 1500.0
ELO_SCALE = 400.0

K_QUALI = 8.0
K_RACE = 16.0

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
