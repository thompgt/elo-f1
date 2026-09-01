"""Builds the teammate 'match' abstraction for a race weekend (PLAN.md 3.1)."""

from dataclasses import dataclass

from elo_f1.ingestion.status_classifier import DISQUALIFIED, DRIVER_FAULT, FINISHED

# A DNF only counts as "losing" a race match if it was the driver's own doing.
# A mechanical/other DNF carries no driving-quality signal about the other
# driver, so crediting them a win for merely outlasting a blown engine would
# reward car reliability, not driving — exactly the car-luck contamination
# this whole model exists to strip out.
_SELF_INFLICTED_DNF = {DRIVER_FAULT, DISQUALIFIED}


@dataclass
class TeammateMatch:
    driver_a: str
    driver_b: str
    constructor_id: str
    actual_a: float  # 1.0 win, 0.5 tie, 0.0 loss
    actual_b: float


def _group_by_constructor(rows: list, constructor_key: str = "constructor_id") -> dict[str, list]:
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row[constructor_key], []).append(row)
    return grouped


def build_qualifying_matches(qualifying_rows: list) -> list[TeammateMatch]:
    matches = []
    for constructor_id, rows in _group_by_constructor(qualifying_rows).items():
        ranked = [r for r in rows if r["position"] is not None]
        if len(ranked) != 2:
            continue  # only pairwise teammate comparisons; skip single-car or 3+ entries
        a, b = ranked
        if a["position"] == b["position"]:
            continue
        winner, loser = (a, b) if a["position"] < b["position"] else (b, a)
        matches.append(
            TeammateMatch(
                driver_a=winner["driver_id"],
                driver_b=loser["driver_id"],
                constructor_id=constructor_id,
                actual_a=1.0,
                actual_b=0.0,
            )
        )
    return matches


def build_race_matches(result_rows: list) -> list[TeammateMatch]:
    """Note: Ergast's `position` field is the classification/retirement order —
    it is populated even for DNFs (e.g. a lap-25 retirement still gets a
    position like 17), with `position_text`/`status` marking it as a
    retirement. So "did this driver actually finish" must be read from
    status_category, not from position being non-null."""
    matches = []
    for constructor_id, rows in _group_by_constructor(result_rows).items():
        if len(rows) != 2:
            continue
        a, b = rows
        a_finished = a["status_category"] == FINISHED
        b_finished = b["status_category"] == FINISHED

        if not a_finished and not b_finished:
            continue  # both DNF: no race-outcome signal, handled by penalty.py instead

        if a_finished and b_finished:
            if a["position"] is None or b["position"] is None or a["position"] == b["position"]:
                continue
            winner, loser = (a, b) if a["position"] < b["position"] else (b, a)
        else:
            dnf_driver = b if a_finished else a
            if dnf_driver["status_category"] not in _SELF_INFLICTED_DNF:
                continue  # teammate's mechanical/other DNF: no driving-quality signal
            winner, loser = (a, b) if a_finished else (b, a)

        matches.append(
            TeammateMatch(
                driver_a=winner["driver_id"],
                driver_b=loser["driver_id"],
                constructor_id=constructor_id,
                actual_a=1.0,
                actual_b=0.0,
            )
        )
    return matches
