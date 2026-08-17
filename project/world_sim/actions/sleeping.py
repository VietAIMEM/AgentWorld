from __future__ import annotations

from ..npc.needs import clamp
from .action import Action, log


def _stamp(world) -> str:
    return world.clock.stamp()


class SleepAction(Action):
    action_type = "sleep"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.min_ticks = self._int("sleep_min_ticks", 3)
        self.max_ticks = self._int("sleep_max_ticks", 48)
        self.energy_restore = self._float("sleep_energy_restore", 8.0)

    def can_execute(self, npc, world) -> bool:
        return npc.location_id == npc.home_id

    def start(self, npc, world) -> None:
        home_name = world.get_location(npc.home_id).name
        log.info(f"[{_stamp(world)}] {npc.name} went to sleep at {home_name}.")

    def apply(self, npc, world) -> None:
        npc.needs.energy = clamp(npc.needs.energy + self.energy_restore, 0.0, 100.0)

    def is_complete(self, npc, world) -> bool:
        if self.ticks_elapsed >= self.max_ticks:
            return True
        return self.ticks_elapsed >= self.min_ticks and npc.needs.energy >= 90.0

    def finish(self, npc, world) -> None:
        home_name = world.get_location(npc.home_id).name
        hour = world.clock.hour
        if 4 <= hour <= 8 and npc.last_wake_day != world.clock.day:
            npc.last_wake_day = world.clock.day
            log.info(f"[{_stamp(world)}] {npc.name} woke up at {home_name}.")
        npc.add_memory(_stamp(world), "slept", f"{npc.name} slept at {home_name}.", 2.0, npc.home_id)