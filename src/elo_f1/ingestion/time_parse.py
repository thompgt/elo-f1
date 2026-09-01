"""Parses Ergast/Jolpica time strings into integer milliseconds."""


def lap_time_to_ms(t: str | None) -> int | None:
    """Parses 'm:ss.SSS' (e.g. '1:36.236') lap/qualifying time strings."""
    if not t:
        return None
    try:
        minutes, rest = t.split(":")
        seconds = float(rest)
        return int((int(minutes) * 60 + seconds) * 1000)
    except (ValueError, AttributeError):
        return None


def race_time_to_ms(time_obj: dict | None) -> int | None:
    """Race result Time.millis is already in ms (only present for the winner and
    drivers on the lead lap in some seasons); returns None otherwise."""
    if not time_obj:
        return None
    millis = time_obj.get("millis")
    return int(millis) if millis is not None else None
