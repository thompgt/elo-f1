"""Regression-to-mean applied at each season boundary a driver crosses (PLAN.md 3.5)."""

from elo_f1.elo.config import INITIAL_RATING, REGRESSION_FACTOR


def regress(rating: float, seasons_skipped: int = 0) -> float:
    """Applies regression toward INITIAL_RATING once per season boundary crossed
    (1 for a normal year-to-year transition, more if the driver skipped seasons)."""
    boundaries = max(1, seasons_skipped + 1)
    for _ in range(boundaries):
        rating = INITIAL_RATING + REGRESSION_FACTOR * (rating - INITIAL_RATING)
    return rating
