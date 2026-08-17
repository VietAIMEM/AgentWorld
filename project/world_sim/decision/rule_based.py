from __future__ import annotations

import logging
import random
from typing import Optional

from ..logging import get_logger
from ..npc.goals import Goal, GoalGenerator, GoalType
from ..npc.needs import NeedLevel
from .decision_system import Decision, DecisionSystem

log = get_logger()


def _d(
    goal: Goal,
    action_type: str,
    priority: float,
    target_location: Optional[str] = None,
    target_npc: Optional[str] = None,
) -> Decision:
    return Decision(
        goal=goal,
        action_type=action_type,
        priority=priority,
        target_location_id=target_location,
        target_npc_id=target_npc,
    )


def _wrap(decision: Decision, reason: str, candidates: dict, urgent: bool = False) -> Decision:
    decision.reason = reason
    decision.candidates = dict(candidates)
    decision.urgent = urgent
    return decision


def _rest(npc, prio: float) -> Decision:
    return _d(Goal(GoalType.REST, prio, npc.location_id), "rest", prio)


def _work(npc, world, prio: float) -> Decision:
    work_location = npc.job.work_location
    goal = Goal(GoalType.WORK, prio, work_location)
    if npc.location_id == work_location:
        return _d(goal, "work", prio)
    return _d(goal, "move", prio, work_location)


def _sleep(npc, world, prio: float) -> Decision:
    goal = Goal(GoalType.SLEEP, prio, npc.home_id)
    if npc.location_id == npc.home_id:
        return _d(goal, "sleep", prio)
    return _d(goal, "move", prio, npc.home_id)


def _health(npc, world, prio: float) -> Decision:
    goal = Goal(GoalType.SEEK_HEALTH, prio, npc.home_id)
    if npc.location_id == npc.home_id:
        return _d(goal, "rest", prio)
    return _d(goal, "move", prio, npc.home_id)


def _nearest_natural(world, start_id: str) -> Optional[str]:
    from collections import deque

    start = world.locations.get(start_id)
    if start is None:
        return None
    if start.type == "natural":
        return None
    seen = {start_id}
    queue = deque(start.connected)
    while queue:
        loc_id = queue.popleft()
        if loc_id in seen:
            continue
        seen.add(loc_id)
        location = world.locations.get(loc_id)
        if location is None:
            continue
        if location.type == "natural":
            return loc_id
        queue.extend(location.connected)
    return None


def _explore(npc, perception, world, prio: float) -> Decision:
    goal = Goal(GoalType.EXPLORE, prio)
    location = perception.location
    if location is not None and location.type != "natural":
        natural = _nearest_natural(world, npc.location_id)
        if natural is not None:
            return _d(goal, "move", prio, natural)
    return _d(goal, "explore", prio)


def _social(npc, perception, world, prio: float, rng, social_location: str) -> Decision:
    goal = Goal(GoalType.SOCIALIZE, prio)
    schedule = world.config.get("schedule", {})
    work_end = int(schedule.get("work_end", 17))
    sleep_start = int(schedule.get("sleep_start", 22))
    hour = world.clock.hour
    evening = work_end <= hour < sleep_start
    at_social = npc.location_id == social_location
    if perception.nearby_npcs:
        partner = rng.choice(perception.nearby_npcs)
        return _d(goal, "socialize", prio, target_npc=partner.id)
    if evening and not at_social:
        if any(loc.id == social_location for loc in perception.connected_locations):
            return _d(goal, "move", prio, social_location)
        if any(loc.id == world.market_id for loc in perception.connected_locations):
            return _d(goal, "move", prio, world.market_id)
    location = perception.location
    if location is not None and location.type == "social":
        return _d(goal, "rest", prio)
    if any(loc.id == social_location for loc in perception.connected_locations):
        return _d(goal, "move", prio, social_location)
    if any(loc.id == world.market_id for loc in perception.connected_locations):
        return _d(goal, "move", prio, world.market_id)
    return _d(goal, "rest", prio)


def _food(npc, perception, world, prio: float, reserve: int, hunger_threshold: float) -> Optional[Decision]:
    goal = Goal(GoalType.EAT, prio)
    if npc.needs.hunger <= hunger_threshold:
        return None
    at_market = npc.location_id == world.market_id
    can_buy = world.is_shop_open() and world.economy.can_buy_food(npc, world)
    stock = npc.inventory.get("food", 0)
    if at_market:
        if stock < reserve and can_buy:
            return _d(goal, "buy_food", prio)
        if stock > 0:
            return _d(goal, "eat", prio)
        return None
    if npc.has_resource("food"):
        return _d(goal, "eat", prio)
    if can_buy and any(location.id == world.market_id for location in perception.connected_locations):
        return _d(goal, "move", prio, world.market_id)
    return None


class LowHealthRule:
    def __init__(self, config: dict, generator: GoalGenerator):
        self.generator = generator
        self.threshold = float(config.get("needs", {}).get("thresholds", {}).get("health", NeedLevel.HEALTH_CRITICAL))

    def evaluate(self, npc, perception, world) -> Optional[Decision]:
        if npc.needs.health >= self.threshold:
            return None
        decision = _health(npc, world, 100.0)
        return _wrap(decision, "low_health", {}, urgent=True)


class HighHungerRule:
    def __init__(self, config: dict, generator: GoalGenerator):
        self.generator = generator
        self.threshold = float(config.get("needs", {}).get("hunger_critical", NeedLevel.HUNGER_CRITICAL))
        self.hunger_threshold = float(config.get("needs", {}).get("thresholds", {}).get("hunger", 80))
        self.reserve = int(config.get("actions", {}).get("food_reserve", 3))

    def evaluate(self, npc, perception, world) -> Optional[Decision]:
        if npc.needs.hunger < self.threshold:
            return None
        eat = next((g for g in self.generator.generate(npc, perception, world) if g.type is GoalType.EAT), None)
        if eat is None:
            return None
        decision = _food(npc, perception, world, eat.priority, self.reserve, self.hunger_threshold)
        if decision is None:
            return None
        return _wrap(decision, "hunger_critical", {}, urgent=True)


class LowEnergyRule:
    def __init__(self, config: dict, generator: GoalGenerator):
        self.generator = generator
        self.threshold = float(config.get("needs", {}).get("thresholds", {}).get("energy", NeedLevel.ENERGY_CRITICAL))

    def evaluate(self, npc, perception, world) -> Optional[Decision]:
        if npc.needs.energy >= self.threshold:
            return None
        sleep = next((g for g in self.generator.generate(npc, perception, world) if g.type is GoalType.SLEEP), None)
        if sleep is None:
            return None
        decision = _sleep(npc, world, sleep.priority)
        return _wrap(decision, "low_energy", {}, urgent=True)


class LowMoneyRule:
    def __init__(self, config: dict, generator: GoalGenerator):
        self.generator = generator
        self.threshold = float(config.get("needs", {}).get("thresholds", {}).get("money", 20))

    def evaluate(self, npc, perception, world) -> Optional[Decision]:
        if npc.money >= self.threshold:
            return None
        earn = next(
            (g for g in self.generator.generate(npc, perception, world) if g.type is GoalType.EARN_MONEY), None
        )
        if earn is None:
            return None
        decision = _work(npc, world, earn.priority + 5.0 * npc.personality.ambition)
        return _wrap(decision, "low_money", {})


class LowSocialRule:
    def __init__(self, config: dict, generator: GoalGenerator, rng):
        self.generator = generator
        self.rng = rng
        self.threshold = float(config.get("needs", {}).get("thresholds", {}).get("social", NeedLevel.SOCIAL_LOW))
        self.social_location = config.get("schedule", {}).get("social_location", "tavern")

    def evaluate(self, npc, perception, world) -> Optional[Decision]:
        if npc.needs.social >= self.threshold:
            return None
        social = next(
            (g for g in self.generator.generate(npc, perception, world) if g.type is GoalType.SOCIALIZE), None
        )
        if social is None:
            return None
        decision = _social(
            npc,
            perception,
            world,
            social.priority + 5.0 * npc.personality.sociability,
            self.rng,
            self.social_location,
        )
        return _wrap(decision, "low_social", {})


class LowFoodStockRule:
    def __init__(self, config: dict, generator: GoalGenerator):
        self.generator = generator
        self.buy_threshold = float(config.get("needs", {}).get("hunger_safe", 60))
        self.reserve = int(config.get("actions", {}).get("food_reserve", 3))

    def evaluate(self, npc, perception, world) -> Optional[Decision]:
        stock = npc.inventory.get("food", 0)
        if npc.needs.hunger <= self.buy_threshold or stock >= self.reserve:
            return None
        if not world.is_shop_open():
            return None
        if not world.economy.can_buy_food(npc, world):
            return None
        priority = 5.0 + 5.0 * (npc.needs.hunger / 100.0)
        goal = Goal(GoalType.BUY_FOOD, priority)
        if npc.location_id == world.market_id:
            return _wrap(_d(goal, "buy_food", priority), "low_food_stock", {})
        if any(loc.id == world.market_id for loc in perception.connected_locations):
            return _wrap(_d(goal, "move", priority, world.market_id), "low_food_stock", {})
        return None


class DefaultActivityRule:
    def __init__(self, config: dict, rng, generator: GoalGenerator):
        self.rng = rng
        self.generator = generator
        schedule = config.get("schedule", {})
        self.wake = int(schedule.get("wake", 6))
        self.work_start = int(schedule.get("work_start", 8))
        self.work_end = int(schedule.get("work_end", 17))
        self.sleep_start = int(schedule.get("sleep_start", 22))
        self.social_location = schedule.get("social_location", "tavern")
        self.hunger_threshold = float(config.get("needs", {}).get("thresholds", {}).get("hunger", 80))
        self.food_reserve = int(config.get("actions", {}).get("food_reserve", 3))

    def _score(self, npc, perception, world) -> dict:
        hour = world.clock.hour
        personality = npc.personality
        energy = npc.needs.energy
        money_pressure = min(1.0, max(0.0, 1.0 - npc.money / 40.0))
        morning = self.wake <= hour < self.work_start
        work_window = self.work_start <= hour < self.work_end
        evening = self.work_end <= hour < self.sleep_start
        night = hour >= self.sleep_start or hour < self.wake

        work = 0.35 * personality.ambition + 0.35 * personality.work_ethic + 0.30 * money_pressure
        if work_window:
            work += 0.50
            if hour >= self.work_end - 2:
                work -= 1.20
        else:
            work -= 1.20
        if energy < 30:
            work -= 0.35
        if night:
            work -= 0.50

        eat = 0.5 * (npc.needs.hunger / 100.0) + 0.5 * (
            1.0 if npc.needs.hunger > self.hunger_threshold else 0.0
        )
        if night:
            eat -= 0.30

        social = 0.5 * personality.sociability + 0.5 * (1.0 - npc.needs.social / 100.0)
        if perception.nearby_npcs:
            social += 0.10
        if evening:
            social += 0.10
        if work_window:
            social -= 0.30
        if night:
            social -= 0.45
        if npc.last_socialize_day == world.clock.day:
            social -= 0.60

        rest = 0.10 + 0.35 * (1.0 - energy / 100.0)
        if not work_window and not night:
            rest += 0.20
        if night and energy >= 90.0:
            rest += 0.10
        if evening and perception.nearby_npcs and personality.sociability >= 0.6:
            rest -= 0.10

        explore = 0.15 + 0.40 * personality.risk_tolerance
        if perception.location is not None and perception.location.type == "natural":
            explore += 0.15
        if morning:
            explore += 0.10
        if work_window:
            explore -= 0.35
        if night:
            explore -= 0.50
        if npc.inventory.get("food", 0) >= self.food_reserve:
            explore -= 0.30

        sleep = 0.10 + 0.35 * (1.0 - energy / 100.0)
        if night and energy < 90.0:
            sleep += 0.55
        elif night:
            sleep += 0.35
        if work_window:
            sleep -= 0.60

        return {
            "work": work,
            "eat": eat,
            "socialize": social,
            "rest": rest,
            "explore": explore,
            "sleep": sleep,
        }

    def evaluate(self, npc, perception, world) -> Optional[Decision]:
        hour = world.clock.hour
        home = npc.home_id

        if world.clock.day != npc.last_wake_day and self.wake <= hour < self.work_start and npc.location_id == home:
            npc.last_wake_day = world.clock.day
            log.info(f"[{world.clock.stamp()}] {npc.name} woke up at {world.get_location(home).name}.")

        if self.work_start <= hour < self.work_end and npc.needs.energy < 35.0:
            return _wrap(_rest(npc, 10.0), "low_energy", {})

        scores = self._score(npc, perception, world)
        best = max(scores, key=lambda key: scores[key])
        prio = 10.0 + scores[best] * 10.0
        reason = f"default:{best}"

        if best == "work":
            return _wrap(_work(npc, world, prio), reason, scores)
        if best == "socialize":
            return _wrap(_social(npc, perception, world, prio, self.rng, self.social_location), reason, scores)
        if best == "eat":
            decision = _food(npc, perception, world, prio, self.food_reserve, self.hunger_threshold)
            if decision is None:
                return _wrap(_rest(npc, prio), reason, scores)
            return _wrap(decision, reason, scores)
        if best == "explore":
            return _wrap(_explore(npc, perception, world, prio), reason, scores)
        if best == "sleep":
            return _wrap(_sleep(npc, world, prio), reason, scores)
        return _wrap(_rest(npc, prio), reason, scores)


class RuleBasedDecisionSystem(DecisionSystem):
    def __init__(self, config: dict, rng=None):
        self.rng = rng if rng is not None else random.Random(0)
        self.generator = GoalGenerator(config)
        self.social_location = config.get("schedule", {}).get("social_location", "tavern")
        self.commitment_cfg = config.get("commitment", {})
        self.food_reserve = int(config.get("actions", {}).get("food_reserve", 3))
        self.hunger_threshold = float(config.get("needs", {}).get("thresholds", {}).get("hunger", 80))
        self.rules = [
            HighHungerRule(config, self.generator),
            LowHealthRule(config, self.generator),
            LowEnergyRule(config, self.generator),
            LowMoneyRule(config, self.generator),
            LowSocialRule(config, self.generator, self.rng),
            LowFoodStockRule(config, self.generator),
            DefaultActivityRule(config, self.rng, self.generator),
        ]

    def decide(self, npc, perception, world) -> Decision:
        preferred = None
        for rule in self.rules:
            preferred = rule.evaluate(npc, perception, world)
            if preferred is not None:
                break
        if preferred is None:
            preferred = _rest(npc, 0.0)
        return self._apply_commitment(npc, perception, world, preferred)

    def _apply_commitment(self, npc, perception, world, preferred: Decision) -> Decision:
        current = npc.current_goal
        if current is None or current.started_tick is None:
            return preferred
        if preferred.goal.type == current.type:
            return preferred
        if preferred.urgent:
            return preferred
        if self._goal_satisfied(current, npc):
            return preferred
        elapsed = world.clock.tick - current.started_tick
        commitment = self._commitment_ticks(current.type)
        if elapsed < commitment:
            if log.isEnabledFor(logging.DEBUG):
                log.debug(
                    f"[{world.clock.stamp()}] {npc.name} action preserved: "
                    f"goal {current.type.value} committed ({commitment - elapsed} ticks remaining)."
                )
            continued = self._continue_goal(npc, perception, world, current)
            if continued is None:
                return preferred
            return continued
        return preferred

    def _goal_satisfied(self, goal: Goal, npc) -> bool:
        if goal.type is GoalType.EAT:
            return npc.needs.hunger <= self.hunger_threshold
        if goal.type is GoalType.SLEEP:
            return npc.needs.energy >= 90.0
        return False

    def _commitment_ticks(self, goal_type: GoalType) -> int:
        cfg = self.commitment_cfg
        if goal_type is GoalType.SLEEP:
            return int(cfg.get("sleep", 999))
        return int(cfg.get(goal_type.value, 0))

    def _continue_goal(self, npc, perception, world, goal: Goal) -> Decision:
        prio = goal.priority if goal.priority > 0 else 10.0
        if goal.type in (GoalType.WORK, GoalType.EARN_MONEY):
            return _work(npc, world, prio)
        if goal.type is GoalType.EAT:
            return _food(npc, perception, world, prio, self.food_reserve, self.hunger_threshold)
        if goal.type is GoalType.SOCIALIZE:
            return _social(npc, perception, world, prio, self.rng, self.social_location)
        if goal.type is GoalType.SLEEP:
            return _sleep(npc, world, prio)
        if goal.type is GoalType.SEEK_HEALTH:
            return _health(npc, world, prio)
        if goal.type is GoalType.EXPLORE:
            return _explore(npc, perception, world, prio)
        return _rest(npc, prio)