"""Read-through cache for raw Jolpica JSON responses, keyed by request URL."""

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / "data" / "raw_cache"


def _key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def get(url: str) -> dict | None:
    path = CACHE_DIR / f"{_key(url)}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def put(url: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(url)}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
