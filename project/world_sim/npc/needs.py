from dataclasses import dataclass


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def money_need(money: float) -> float:
    return clamp(100.0 - money, 0.0, 100.0)


class NeedLevel:
    """Canonical need thresholds on the 0..100 scale (0 = full, 100 = starving)."""

    HUNGER_SATISFIED = 30.0
    HUNGER_LOW = 50.0
    HUNGER_CRITICAL = 95.0
    HEALTH_CRITICAL = 25.0
    ENERGY_CRITICAL = 20.0
    SOCIAL_LOW = 20.0


@dataclass
class Needs:
    hunger: float = 20.0
    energy: float = 95.0
    health: float = 100.0
    social: float = 60.0


class NeedsSystem:
    def __init__(self, config: dict):
        cfg = config.get("needs", {})
        self.hunger_rate = float(cfg.get("hunger_rate", 0.6))
        self.energy_decay = float(cfg.get("energy_decay", 0.3))
        self.social_decay = float(cfg.get("social_decay", 0.15))
        self.health_damage = float(cfg.get("health_damage", 0.3))
        self.health_recover = float(cfg.get("health_recover", 0.1))
        self.hunger_critical = float(cfg.get("hunger_critical", 90.0))
        self.energy_critical = float(cfg.get("energy_critical", 5.0))
        self.hunger_safe = float(cfg.get("hunger_safe", 60.0))
        self.energy_safe = float(cfg.get("energy_safe", 25.0))

    def update(self, npc, world) -> None:
        dt = float(world.clock.tick_minutes) / 10.0
        needs = npc.needs
        needs.hunger = clamp(needs.hunger + self.hunger_rate * dt, 0.0, 100.0)
        needs.energy = clamp(needs.energy - self.energy_decay * dt, 0.0, 100.0)
        needs.social = clamp(needs.social - self.social_decay * dt, 0.0, 100.0)
        if needs.hunger > self.hunger_critical or needs.energy < self.energy_critical:
            needs.health = clamp(needs.health - self.health_damage * dt, 0.0, 100.0)
        elif needs.hunger < self.hunger_safe and needs.energy > self.energy_safe:
            needs.health = clamp(needs.health + self.health_recover * dt, 0.0, 100.0)