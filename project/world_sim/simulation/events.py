from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventState(Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass
class WorldEvent:
    id: str
    type: str
    description: str
    start_tick: int
    duration_ticks: int
    location_id: Optional[str] = None
    state: EventState = EventState.SCHEDULED
    started_tick: Optional[int] = None
    social_type: Optional[str] = None
