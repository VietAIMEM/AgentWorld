from __future__ import annotations

import random
from collections import Counter
from typing import Optional

from ..actions.action import ActionManager
from ..decision.rule_based import RuleBasedDecisionSystem
from ..logging import get_logger
from ..npc.memory import MemorySystem
from ..npc.needs import NeedsSystem
from ..npc.perception import PerceptionSystem
from .world import World

log = get_logger()


class Simulation:
    def __init__(
        self,
        world_config: dict,
        npcs_config: dict,
        *,
        seed: int = 42,
        days: Optional[int] = None,
        decision_system=None,
        verbose: bool = False,
        print_report: bool = True,
    ):
        self.seed = seed
        self.rng = random.Random(seed)
        self.days = days if days is not None else int(world_config.get("simulation", {}).get("days", 30))
        self._total_days = self.days
        self.verbose = verbose
        self.print_report = print_report
        self.world = World(world_config, npcs_config, self.rng, run_days=self.days, seed=self.seed)
        self.decision_system = decision_system or RuleBasedDecisionSystem(world_config, self.rng)
        self.perception_system = PerceptionSystem()
        self.needs_system = NeedsSystem(world_config)
        self.memory_system = MemorySystem()
        self.action_manager = ActionManager(self.rng, world_config)
        self._hunger_threshold = float(
            world_config.get("needs", {}).get("thresholds", {}).get("hunger", 80)
        )

    def run(self, days: Optional[int] = None) -> None:
        world = self.world
        run_days = days if days is not None else self.days
        log.info(f"Starting simulation: {len(world.npcs)} NPCs, {run_days} days, seed {self.seed}.")
        ticks_per_hour = 60 // world.clock.tick_minutes
        total_ticks = run_days * 24 * ticks_per_hour
        for _ in range(total_ticks):
            world.update_time()
            self._tick()
            if self.verbose and world.clock.minute == 0 and world.clock.hour % 3 == 0:
                self.display_state()
        if self.print_report:
            self.print_summary()

    def _tick(self) -> None:
        world = self.world
        for npc in list(world.alive_npcs()):
            perception = self.perception_system.perceive(npc, world)
            self.needs_system.update(npc, world)
            self.memory_system.update(npc)
            if npc.needs.hunger > self._hunger_threshold and not npc.hungry_logged:
                npc.hungry_logged = True
                log.info(f"[{world.clock.stamp()}] {npc.name} became hungry.")
            elif npc.needs.hunger < 50.0:
                npc.hungry_logged = False
            decision = self.decision_system.decide(npc, perception, world)
            action = self.action_manager.update(npc, decision, world)
            action.tick(npc, world)
            self._check_death(npc)
        world.process_events()

    def _check_death(self, npc) -> None:
        if npc.needs.health <= 0.0 and npc.alive:
            self.world.npc_die(npc)

    def display_state(self) -> None:
        world = self.world
        print(f"== {world.clock.stamp()} ==")
        for npc in world.alive_npcs():
            action = npc.current_action.action_type if npc.current_action else "-"
            goal = npc.current_goal.type.value if npc.current_goal else "-"
            print(
                f"  {npc.name:<10} {npc.location_id:<8} $ {npc.money:>7.1f} "
                f"H {npc.needs.hunger:>5.1f} E {npc.needs.energy:>5.1f} "
                f"S {npc.needs.social:>5.1f} goal={goal:<11} act={action}"
            )

    def print_summary(self) -> None:
        world = self.world
        alive = world.alive_npcs()
        bar = "=" * 42
        print()
        print(bar)
        print("WORLD SUMMARY")
        print(bar)
        print(f"Days simulated: {self.days}")
        print(f"Population: {len(alive)} alive, {len(world.dead)} dead")
        print(f"Total money: {sum(npc.money for npc in alive):.1f}")
        food_held = sum(npc.inventory.get("food", 0) for npc in alive)
        print(f"Food held: {food_held}, Farm stock: {world.farm_stock}, Market stock: {world.economy.food_stock}")
        if alive:
            print(f"Average hunger: {sum(npc.needs.hunger for npc in alive) / len(alive):.1f}")
            print(f"Average energy: {sum(npc.needs.energy for npc in alive) / len(alive):.1f}")
            print(f"Average social: {sum(npc.needs.social for npc in alive) / len(alive):.1f}")
        jobs = Counter(npc.job.id for npc in alive)
        print("Jobs: " + ", ".join(f"{key}: {value}" for key, value in sorted(jobs.items())))
        stats = world.stats
        print(f"Deaths: {stats.deaths}")
        print(f"Births: {stats.births}")
        print(f"Old-age deaths: {stats.old_age_deaths}")
        print(f"Food consumed: {stats.food_consumed}")
        print(f"Food bought: {stats.food_bought}")
        print(f"Food produced: {stats.food_produced}")
        print(f"Work actions: {stats.work_actions}")
        print(f"Social interactions: {stats.social_interactions}")
        print(f"Money earned: {stats.money_earned:.1f}")
        print(f"Money spent (living cost): {stats.money_spent:.1f}")
        print()
        print(bar)
        print("NPC SUMMARY")
        print(bar)
        for npc in alive:
            goal = npc.current_goal.type.value if npc.current_goal else "-"
            action = npc.current_action.action_type if npc.current_action else "-"
            print(
                f"{npc.name:<10} age {npc.age:<3} {npc.job.id:<9} $ {npc.money:>7.1f} "
                f"loc {npc.location_id:<8} H {npc.needs.hunger:>5.1f} E {npc.needs.energy:>5.1f} "
                f"S {npc.needs.social:>5.1f} goal={goal:<11} act={action}"
            )