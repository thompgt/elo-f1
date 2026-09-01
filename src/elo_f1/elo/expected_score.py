from elo_f1.elo.config import ELO_SCALE


def expected_score(rating_a: float, rating_b: float) -> float:
    """Classic Elo expected-score formula: probability A beats B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / ELO_SCALE))


def update(rating: float, expected: float, actual: float, k: float) -> float:
    return rating + k * (actual - expected)
