from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """Cache mémoire simple avec expiration. Pas de dépendance externe."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self.ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()