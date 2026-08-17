from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..npc.goals import Goal


@dataclass
class Decision:
    goal: Goal
    action_type: str
    priority: float = 0.0
    target_location_id: Optional[str] = None
    target_npc_id: Optional[str] = None
    reason: str = ""
    candidates: dict = field(default_factory=dict)
    urgent: bool = False


class DecisionSystem(ABC):
    @abstractmethod
    def decide(self, npc, perception, world) -> Decision:
        ...