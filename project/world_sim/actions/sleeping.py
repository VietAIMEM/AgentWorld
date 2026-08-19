from __future__ import annotations

from ..npc.intent import clear_intent, set_intent
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
        schedule = config.get("schedule", {})
        self.sleep_start = int(schedule.get("sleep_start", 22))
        self.wake = int(schedule.get("wake", 6))
        self.work_start = int(schedule.get("work_start", 8))
        self._night_sleep = False

    def can_execute(self, npc, world) -> bool:
        return npc.location_id == npc.home_id

    def start(self, npc, world) -> None:
        home_name = world.get_location(npc.home_id).name
        hour = world.clock.hour
        self._night_sleep = hour >= self.sleep_start or hour < self.wake
        set_intent(npc, world, "sleeping", target_location_id=npc.home_id)
        log.info(f"[{_stamp(world)}] {npc.name} went to sleep at {home_name}.")

    def apply(self, npc, world) -> None:
        npc.needs.energy = clamp(npc.needs.energy + self.energy_restore, 0.0, 100.0)

    def is_complete(self, npc, world) -> bool:
        if self._night_sleep:
            self._maybe_log_wake(npc, world)
        if self.ticks_elapsed >= self.max_ticks:
            return True
        if self._night_sleep:
            if self.ticks_elapsed >= self.min_ticks and self.wake <= world.clock.hour <= self.work_start:
                return True
            return False
        return self.ticks_elapsed >= self.min_ticks and npc.needs.energy >= 90.0

    def finish(self, npc, world) -> None:
        self._maybe_log_wake(npc, world)
        home_name = world.get_location(npc.home_id).name
        npc.add_memory(_stamp(world), "slept", f"{npc.name} slept at {home_name}.", 2.0, npc.home_id)
        clear_intent(npc, world)

    def cancel(self, npc, world) -> None:
        self._maybe_log_wake(npc, world)
        clear_intent(npc, world)

    def _maybe_log_wake(self, npc, world) -> None:
        if not self._night_sleep:
            return
        hour = world.clock.hour
        if self.wake <= hour <= self.work_start and npc.last_wake_day != world.clock.day:
            npc.last_wake_day = world.clock.day
            home_name = world.get_location(npc.home_id).name
            log.info(f"[{_stamp(world)}] {npc.name} woke up at {home_name}.")