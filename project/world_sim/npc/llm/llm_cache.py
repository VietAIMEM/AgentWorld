"""Optional in-memory deterministic cache for LLM responses.

The cache key is the request fingerprint (npc id, partner, conversation id,
context digest, model, prompt version). Identical requests return the cached
response. The cache never mutates simulation state and never consumes
simulation RNG. No database is involved.
"""

from __future__ import annotations

import threading


class LLMCache:
    def __init__(self, enabled: bool = True, max_entries: int = 512):
        self.enabled = enabled
        self.max_entries = max(1, int(max_entries))
        self._lock = threading.Lock()
        self._data = {}
        self._order = []

    def get(self, fingerprint: str):
        if not self.enabled:
            return None
        with self._lock:
            return self._data.get(fingerprint)

    def put(self, fingerprint: str, response) -> None:
        if not self.enabled or response is None:
            return
        if not getattr(response, "llm", False):
            return
        with self._lock:
            if fingerprint not in self._data:
                self._order.append(fingerprint)
            self._data[fingerprint] = response
            while len(self._order) > self.max_entries:
                oldest = self._order.pop(0)
                self._data.pop(oldest, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._order.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)