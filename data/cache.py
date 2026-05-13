from diskcache import Cache
from pathlib import Path

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)
_cache = Cache(str(CACHE_DIR))

TTL = {
    "prices": 15 * 60,
    "filings": 24 * 60 * 60,
    "news": 60 * 60,
    "options": 15 * 60,
    "industry": 4 * 60 * 60,
    "finviz": 60 * 60,
}


def get(key: str) -> any:
    return _cache.get(key)


def set(key: str, value: any, ttl_type: str = "prices") -> None:
    _cache.set(key, value, expire=TTL.get(ttl_type, 3600))


def delete(key: str) -> None:
    _cache.delete(key)


def make_key(*parts) -> str:
    return ":".join(str(p) for p in parts)
