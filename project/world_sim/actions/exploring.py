from __future__ import annotations

from .action import Action, log


def _stamp(world) -> str:
    return world.clock.stamp()


class ExploreAction(Action):
    action_type = "explore"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.ticks = self._int("explore_ticks", 3)
        self.forage_chance = self._float("forage_chance", 0.35)
        self.food_cap = self._int("food_cap", 6)

    def can_execute(self, npc, world) -> bool:
        return True

    def start(self, npc, world) -> None:
        location_name = world.get_location(npc.location_id).name
        log.debug(f"[{_stamp(world)}] {npc.name} started exploring {location_name}.")

    def apply(self, npc, world) -> None:
        location = world.get_location(npc.location_id)
        if (
            "food" in location.resources
            and npc.inventory.get("food", 0) < self.food_cap
            and self.rng.random() < self.forage_chance
        ):
            npc.add_resource("food", 1)
            npc.add_memory(_stamp(world), "found_food", f"{npc.name} foraged food in {location.name}.", 3.0, "food")
            log.debug(f"[{_stamp(world)}] {npc.name} found food while exploring.")

    def is_complete(self, npc, world) -> bool:
        return self.ticks_elapsed >= self.ticks

    def finish(self, npc, world) -> None:
        location_name = world.get_location(npc.location_id).name
        npc.add_memory(_stamp(world), "visited_location", f"{npc.name} explored {location_name}.", 2.0, npc.location_id)