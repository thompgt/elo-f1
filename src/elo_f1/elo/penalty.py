"""Crash/driver-error penalty computation (PLAN.md 3.3), applied independently
of the teammate matches, not zero-sum."""

from elo_f1.elo import config
from elo_f1.ingestion.status_classifier import DISQUALIFIED, DRIVER_FAULT, SINGLE_CAR_FAULT_STATUSES


def severity_multiplier(laps_completed: int | None, total_race_laps: int | None) -> float:
    if not laps_completed or not total_race_laps:
        return config.SEVERITY_MAX_MULTIPLIER
    fraction = laps_completed / total_race_laps
    raw = 1.0 - 0.5 * fraction
    return max(config.SEVERITY_MIN_MULTIPLIER, min(config.SEVERITY_MAX_MULTIPLIER, raw))


def car_strength_multiplier(strength_score: float | None) -> float:
    if strength_score is None:
        return 1.0
    if strength_score >= config.CAR_STRENGTH_QUARTILE_Z_THRESHOLD:
        return config.CAR_STRENGTH_TOP_QUARTILE_MULTIPLIER
    if strength_score <= -config.CAR_STRENGTH_QUARTILE_Z_THRESHOLD:
        return config.CAR_STRENGTH_BOTTOM_QUARTILE_MULTIPLIER
    return 1.0


def compute_penalty(status: str, status_category: str, laps_completed: int | None,
                     total_race_laps: int | None, car_strength_score: float | None) -> float:
    """Returns a non-negative Elo point penalty to subtract from the driver's rating."""
    if status_category == DRIVER_FAULT:
        base = (
            config.PENALTY_SINGLE_CAR_FAULT
            if (status or "").strip().lower() in SINGLE_CAR_FAULT_STATUSES
            else config.PENALTY_CONTACT_FAULT
        )
    elif status_category == DISQUALIFIED:
        base = config.PENALTY_DISQUALIFIED
    else:
        return 0.0

    return base * severity_multiplier(laps_completed, total_race_laps) * car_strength_multiplier(car_strength_score)
