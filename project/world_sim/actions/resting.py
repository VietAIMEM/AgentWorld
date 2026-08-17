from __future__ import annotations

from ..npc.needs import clamp
from .action import Action, log


def _stamp(world) -> str:
    return world.clock.stamp()


class RestAction(Action):
    action_type = "rest"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.ticks = self._int("rest_ticks", 12)

    def can_execute(self, npc, world) -> bool:
        return True

    def start(self, npc, world) -> None:
        location_name = world.get_location(npc.location_id).name
        log.debug(f"[{_stamp(world)}] {npc.name} is resting at {location_name}.")

    def apply(self, npc, world) -> None:
        npc.needs.energy = clamp(npc.needs.energy + 0.4, 0.0, 100.0)
        npc.needs.social = clamp(npc.needs.social + 0.1, 0.0, 100.0)

    def is_complete(self, npc, world) -> bool:
        return self.ticks_elapsed >= self.ticks