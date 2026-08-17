from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Location:
    id: str
    name: str
    type: str
    connected: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
