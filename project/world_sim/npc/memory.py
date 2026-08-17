from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryEntry:
    timestamp: str
    event_type: str
    description: str
    importance: float
    related_entity: Optional[str] = None


class Memory:
    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.entries: list[MemoryEntry] = []

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)
        self.prune()

    def prune(self) -> None:
        excess = len(self.entries) - self.max_size
        if excess <= 0:
            return
        indexed = sorted(range(len(self.entries)), key=lambda i: (self.entries[i].importance, i))
        drop = set(indexed[:excess])
        self.entries = [entry for i, entry in enumerate(self.entries) if i not in drop]

    def recent(self, event_type: str, limit: int = 5) -> list[MemoryEntry]:
        return [entry for entry in self.entries if entry.event_type == event_type][-limit:]

    def __iter__(self):
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)


class MemorySystem:
    def update(self, npc) -> None:
        npc.memory.prune()