from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Region:
    id: str
    name: str
    kind: str
    location_ids: list[str] = field(default_factory=list)
    center: Optional[tuple[float, float]] = None