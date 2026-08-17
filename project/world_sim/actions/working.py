from __future__ import annotations

from ..npc.needs import clamp
from .action import Action, log


def _stamp(world) -> str:
    return world.clock.stamp()


class WorkAction(Action):
    action_type = "work"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.shift_ticks: int | None = None

    def can_execute(self, npc, world) -> bool:
        return npc.location_id == npc.job.work_location

    def start(self, npc, world) -> None:
        self.shift_ticks = npc.job.shift_ticks
        location_name = world.get_location(npc.job.work_location).name
        log.info(f"[{_stamp(world)}] {npc.name} started working at {location_name}.")

    def apply(self, npc, world) -> None:
        npc.money += npc.job.income_per_tick
        npc.needs.energy = clamp(npc.needs.energy - npc.job.energy_cost, 0.0, 100.0)
        world.stats.money_earned += npc.job.income_per_tick

    def is_complete(self, npc, world) -> bool:
        return self.ticks_elapsed >= (self.shift_ticks or npc.job.shift_ticks)

    def finish(self, npc, world) -> None:
        shift_ticks = self.shift_ticks or npc.job.shift_ticks
        earned = npc.job.income_per_tick * shift_ticks
        npc.add_memory(_stamp(world), "worked", f"{npc.name} worked as a {npc.job.name}.", 3.0, npc.job.id)
        npc.add_memory(_stamp(world), "received_money", f"{npc.name} earned {earned:.0f} money.", 3.0, npc.job.id)
        world.stats.work_actions += 1
        log.info(f"[{_stamp(world)}] {npc.name} earned ${earned:.0f}.")
        if (
            world.farming_enabled
            and npc.job.produces_food
            and npc.location_id == npc.job.work_location
        ):
            produced = world.farm_produce(world.farming_yield)
            if produced > 0:
                npc.add_memory(
                    _stamp(world),
                    "produced_food",
                    f"{npc.name} harvested {produced} food on the farm.",
                    3.0,
                    "food",
                )
                log.info(f"[{_stamp(world)}] {npc.name} produced {produced} food on the farm.")

    def cancel(self, npc, world) -> None:
        if self.ticks_elapsed > 0:
            log.debug(f"[{_stamp(world)}] {npc.name} stopped working early.")