"""Semantic cache (arch O.4) — validity-aware, tenant-isolated by construction.

Key: sha256(tenant | contract_version | investigation_version | conclusion_hash |
           persona | prompt_version | model_route)
Same conclusion + persona + versions + route → HIT; any change → MISS (new key).
Redis absent ⇒ in-process store with a DEGRADED label (documented deviation:
identical keys/semantics so the offline demo shows the hit; Redis swaps in
without code change). Never caches unauthorized data or mutable decision state
without version validation — the version fields ARE the validation.
"""
from __future__ import annotations

import hashlib
import json
import time

from ...config import settings


def cache_key(tenant_id: str, contract_version: int | str, investigation_version: int | str,
              conclusion_hash: str, persona: str, prompt_version: str, model_route: str) -> str:
    raw = "|".join(str(x) for x in [tenant_id, contract_version, investigation_version,
                                    conclusion_hash, persona, prompt_version, model_route])
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


class SemanticCache:
    """Redis-backed when REDIS_URL is set; in-process fallback otherwise (DEGRADED)."""

    def __init__(self) -> None:
        self._redis = None
        self._store: dict[str, tuple[str, float]] = {}
        self.backend = "in_process"
        url = getattr(settings, "redis_url", None)
        if url:
            try:
                import redis  # type: ignore

                self._redis = redis.Redis.from_url(url, socket_timeout=1)
                self._redis.ping()
                self.backend = "redis"
            except Exception:
                self._redis = None

    @property
    def degraded(self) -> bool:
        return self._redis is None

    def get(self, key: str) -> dict | None:
        hit = self._hit_ts(key)
        if hit is None:
            return None
        payload, _ = hit
        return json.loads(payload)

    def put(self, key: str, payload: dict, ttl_s: int = 3600) -> None:
        blob = json.dumps(payload, default=str)
        if self._redis is not None:
            self._redis.setex(f"rf:sc:{key}", ttl_s, blob)
        else:
            self._store[key] = (blob, time.time() + ttl_s)

    def _hit_ts(self, key: str) -> tuple[str, float] | None:
        if self._redis is not None:
            blob = self._redis.get(f"rf:sc:{key}")
            return (blob.decode(), time.time()) if blob else None
        row = self._store.get(key)
        if row is None:
            return None
        blob, exp = row
        if time.time() > exp:
            self._store.pop(key, None)
            return None
        return row


_cache = SemanticCache()


def semantic_cache() -> SemanticCache:
    return _cache
