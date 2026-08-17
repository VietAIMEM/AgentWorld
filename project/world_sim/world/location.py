from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Location:
    id: str
    name: str
    type: str
    connected: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    region_id: Optional[str] = None
    position: Optional[tuple[float, float]] = None
