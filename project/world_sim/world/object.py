from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorldObject:
    id: str
    name: str
    location_id: str
    object_type: str
    interactions: list = field(default_factory=list)
    state: str = "available"
    in_use_by: Optional[str] = None

    def is_available(self) -> bool:
        return self.state == "available"

    def is_in_use(self) -> bool:
        return self.state == "in_use"