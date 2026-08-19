from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .goals import Goal
from .intent import Intent
from .memory import Memory, MemoryEntry
from .needs import Needs
from .personality import Personality

if TYPE_CHECKING:
    from ..actions.action import Action


@dataclass
class Job:
    id: str
    name: str
    work_location: str
    income_per_tick: float
    energy_cost: float
    shift_ticks: int
    produces_food: bool = False


RELATIONSHIP_MIN = -100
RELATIONSHIP_MAX = 100


@dataclass
class NPC:
    id: str
    name: str
    age: int
    money: float
    job: Job
    location_id: str
    home_id: str
    needs: Needs
    personality: Personality
    memory: Memory
    settlement_id: Optional[str] = None
    facing: Optional[str] = None
    intent: Optional[Intent] = None
    routine_id: Optional[str] = None
    conversation_id: Optional[str] = None
    idle_state: Optional[str] = None
    last_interact_tick: Optional[int] = None
    relationships: dict = field(default_factory=dict)
    inventory: dict = field(default_factory=dict)
    current_goal: Optional[Goal] = None
    current_action: Optional["Action"] = None
    alive: bool = True
    last_wake_day: int = 0
    last_socialize_day: int = 0
    hungry_logged: bool = False
    thought: Optional[str] = None

    def add_resource(self, resource_id: str, amount: int = 1) -> None:
        self.inventory[resource_id] = self.inventory.get(resource_id, 0) + amount

    def has_resource(self, resource_id: str) -> bool:
        return self.inventory.get(resource_id, 0) > 0

    def consume_resource(self, resource_id: str, amount: int = 1) -> bool:
        current = self.inventory.get(resource_id, 0)
        if current < amount:
            return False
        self.inventory[resource_id] = current - amount
        return True

    def move_to(self, location_id: str) -> None:
        self.location_id = location_id

    def add_memory(
        self,
        timestamp: str,
        event_type: str,
        description: str,
        importance: float,
        related_entity: Optional[str] = None,
    ) -> None:
        self.memory.add(MemoryEntry(timestamp, event_type, description, importance, related_entity))

    def adjust_relationship(self, other_id: str, delta: int) -> None:
        self.relationships[other_id] = max(
            RELATIONSHIP_MIN, min(RELATIONSHIP_MAX, self.relationships.get(other_id, 0) + delta)
        )

    def location_name(self, world) -> str:
        location = world.get_location(self.location_id)
        return location.name if location else self.location_id