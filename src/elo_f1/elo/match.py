"""Builds the teammate 'match' abstraction for a race weekend (PLAN.md 3.1)."""

from dataclasses import dataclass


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
    matches = []
    for constructor_id, rows in _group_by_constructor(result_rows).items():
        if len(rows) != 2:
            continue
        a, b = rows
        a_classified = a["position"] is not None
        b_classified = b["position"] is not None

        if not a_classified and not b_classified:
            continue  # both DNF: no race-outcome signal, handled by penalty.py instead

        if a_classified and b_classified:
            if a["position"] == b["position"]:
                continue
            winner, loser = (a, b) if a["position"] < b["position"] else (b, a)
        else:
            winner, loser = (a, b) if a_classified else (b, a)

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
