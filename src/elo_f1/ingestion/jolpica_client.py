"""HTTP client for the Jolpica-F1 API (Ergast-compatible successor).

Jolpica returns HTTP 403 to non-browser-looking clients, so a browser User-Agent
is required. Responses are paginated (limit/offset with a `total` count) and are
cached to disk so repeated ingestion runs don't re-hit the network.
"""

import time

import httpx

from elo_f1.ingestion import cache

BASE_URL = "https://api.jolpi.ca/ergast/f1"
USER_AGENT = "Mozilla/5.0 (compatible; elo-f1-ingest/0.1; local research project)"
PAGE_LIMIT = 100
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 6


def _get(url: str) -> dict:
    cached = cache.get(url)
    if cached is not None:
        return cached

    backoff = 5.0
    for attempt in range(MAX_RETRIES):
        resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30.0)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", backoff))
            time.sleep(max(retry_after, backoff))
            backoff *= 2
            continue
        resp.raise_for_status()
        data = resp.json()
        cache.put(url, data)
        time.sleep(REQUEST_DELAY_SECONDS)
        return data

    raise RuntimeError(f"Exceeded retries (429 Too Many Requests) for {url}")


def _table_key(mr: dict) -> str:
    """The Ergast/Jolpica response envelope (MRData) names the payload table by
    content, e.g. RaceTable, QualifyingTable, DriverTable, StandingsTable."""
    for key in mr:
        if key.endswith("Table"):
            return key
    raise ValueError(f"No *Table key found in response: {list(mr.keys())}")


def fetch_all(path: str) -> list[dict]:
    """Fetch every page for an Ergast-shaped endpoint path (e.g. '2023/results')
    and return the concatenated list of race entries (or driver/constructor entries
    for non-race-scoped endpoints)."""
    offset = 0
    all_races: list[dict] = []
    all_items: list[dict] = []
    is_race_scoped = None
    while True:
        url = f"{BASE_URL}/{path}.json?limit={PAGE_LIMIT}&offset={offset}"
        data = _get(url)
        mr = data["MRData"]
        total = int(mr["total"])
        table_key = _table_key(mr)
        table = mr[table_key]

        if "Races" in table:
            is_race_scoped = True
            all_races.extend(table["Races"])
        else:
            is_race_scoped = False
            # DriverTable -> Drivers, ConstructorTable -> Constructors,
            # StandingsTable -> StandingsLists (special-cased by caller)
            list_key = next(k for k in table if isinstance(table[k], list))
            all_items.extend(table[list_key])

        offset += PAGE_LIMIT
        if offset >= total:
            break

    return all_races if is_race_scoped else all_items


def fetch_standings_lists(path: str) -> list[dict]:
    """Standings endpoints nest one StandingsList per round under RaceTable... but
    Jolpica/Ergast actually nests StandingsLists under StandingsTable.Races.
    Returns the raw list of {season, round, DriverStandings|ConstructorStandings} dicts.
    """
    offset = 0
    all_lists: list[dict] = []
    while True:
        url = f"{BASE_URL}/{path}.json?limit={PAGE_LIMIT}&offset={offset}"
        data = _get(url)
        mr = data["MRData"]
        total = int(mr["total"])
        standings_table = mr["StandingsTable"]
        all_lists.extend(standings_table.get("StandingsLists", []))
        offset += PAGE_LIMIT
        if offset >= total:
            break
    return all_lists
