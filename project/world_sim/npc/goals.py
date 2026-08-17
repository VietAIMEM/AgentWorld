from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GoalType(Enum):
    EAT = "eat"
    BUY_FOOD = "buy_food"
    SLEEP = "sleep"
    WORK = "work"
    EARN_MONEY = "earn_money"
    SOCIALIZE = "socialize"
    EXPLORE = "explore"
    REST = "rest"
    MOVE = "move"
    SEEK_HEALTH = "seek_health"


class GoalStatus(Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


@dataclass
class Goal:
    type: GoalType
    priority: float = 0.0
    target: Optional[str] = None
    status: GoalStatus = GoalStatus.PROPOSED
    started_tick: Optional[int] = None


class GoalGenerator:
    def __init__(self, config: dict):
        thresholds = config.get("needs", {}).get("thresholds", {})
        self.th_health = float(thresholds.get("health", 25))
        self.th_hunger = float(thresholds.get("hunger", 80))
        self.th_energy = float(thresholds.get("energy", 20))
        self.th_money = float(thresholds.get("money", 20))
        self.th_social = float(thresholds.get("social", 20))

    def generate(self, npc, perception, world) -> list[Goal]:
        goals: list[Goal] = []
        health = npc.needs.health
        if health < self.th_health:
            goals.append(Goal(GoalType.SEEK_HEALTH, self._scale(health, self.th_health, 0.0, 100.0, 100.0), None))
        hunger = npc.needs.hunger
        if hunger > self.th_hunger:
            goals.append(Goal(GoalType.EAT, self._scale(hunger, self.th_hunger, 100.0, 80.0, 100.0), None))
        energy = npc.needs.energy
        if energy < self.th_energy:
            goals.append(Goal(GoalType.SLEEP, self._scale(energy, self.th_energy, 0.0, 60.0, 100.0), None))
        money = npc.money
        if money < self.th_money:
            goals.append(Goal(GoalType.EARN_MONEY, self._scale(money, self.th_money, 0.0, 50.0, 100.0), None))
        social = npc.needs.social
        if social < self.th_social:
            goals.append(Goal(GoalType.SOCIALIZE, self._scale(social, self.th_social, 0.0, 40.0, 100.0), None))
        goals.sort(key=lambda goal: goal.priority, reverse=True)
        return goals

    @staticmethod
    def _scale(value: float, lo: float, hi: float, prio_lo: float, prio_hi: float) -> float:
        if hi == lo:
            return float(prio_hi)
        t = (value - lo) / (hi - lo)
        t = max(0.0, min(1.0, t))
        return prio_lo + t * (prio_hi - prio_lo)