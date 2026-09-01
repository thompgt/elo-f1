"""Cross-team calibration matches — the signal that anchors ratings to the
whole grid, not just a driver's own teammate.

The teammate matches in match.py are an isolated two-player Elo graph: a
driver's rating only ever moves relative to their own teammate. Two elite
teammates who split results evenly stay pinned near INITIAL_RATING no matter
how good they actually are, while a driver paired with a weak teammate can
drift arbitrarily far from that one reference point, because nothing ever
checks it against the rest of the field.

This gives every classified driver a match against every other classified
driver on a different team, same weekend — but the expected score is computed
from a *handicapped* rating: each driver's Elo plus a car-strength term
(CAR_TO_ELO_SCALE * that car's strength z-score for this weekend). A driver in
a car one standard deviation faster is expected to beat a driver in an
average car the great majority of the time purely from the car; scoring the
match against that car-adjusted expectation means a result the car alone
already predicted barely moves anyone's rating, while an upset (a weaker car
beating a stronger one) is attributed entirely to the driver, since the car
term already accounted for the handicap. This is what lets a backmarker who
merely matches their car's expected finishing order stay near baseline, while
one who repeatedly beats faster cars — or a front-runner who beats a much
faster car, or loses to a much slower one — actually moves the needle,
regardless of team.
"""

from elo_f1.elo.config import CAR_TO_ELO_SCALE, ELO_SCALE
from elo_f1.ingestion.status_classifier import FINISHED


def _handicapped_rating(elo: float, strength_z: float) -> float:
    return elo + CAR_TO_ELO_SCALE * strength_z


def compute_cross_deltas(
    result_rows: list, elo_current: dict[str, float], strength_by_constructor: dict[str, float]
) -> dict[str, float]:
    """Returns {driver_id: signed elo delta} from all cross-team matches this
    race, to be scaled by K_CROSS and applied by the caller."""
    classified = [
        r for r in result_rows
        if r["status_category"] == FINISHED
        and r["position"] is not None
        and strength_by_constructor.get(r["constructor_id"]) is not None
    ]
    raw_sums: dict[str, float] = {r["driver_id"]: 0.0 for r in classified}
    opponent_counts: dict[str, int] = {r["driver_id"]: 0 for r in classified}

    for i in range(len(classified)):
        for j in range(i + 1, len(classified)):
            a, b = classified[i], classified[j]
            if a["constructor_id"] == b["constructor_id"]:
                continue  # actual teammates are handled by match.py, not here
            if a["position"] == b["position"]:
                continue

            handicapped_a = _handicapped_rating(elo_current[a["driver_id"]], strength_by_constructor[a["constructor_id"]])
            handicapped_b = _handicapped_rating(elo_current[b["driver_id"]], strength_by_constructor[b["constructor_id"]])
            expected_a = 1.0 / (1.0 + 10 ** ((handicapped_b - handicapped_a) / ELO_SCALE))
            actual_a = 1.0 if a["position"] < b["position"] else 0.0

            raw_sums[a["driver_id"]] += actual_a - expected_a
            raw_sums[b["driver_id"]] += (1.0 - actual_a) - (1.0 - expected_a)
            opponent_counts[a["driver_id"]] += 1
            opponent_counts[b["driver_id"]] += 1

    # Average rather than sum across opponents, so this stays comparable in
    # magnitude to a single match regardless of grid size.
    return {
        driver_id: (raw_sums[driver_id] / opponent_counts[driver_id]) if opponent_counts[driver_id] else 0.0
        for driver_id in raw_sums
    }
