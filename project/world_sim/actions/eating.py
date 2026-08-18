from __future__ import annotations

from .action import Action, log


def _stamp(world) -> str:
    return world.clock.stamp()


class EatAction(Action):
    action_type = "eat"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.ticks = self._int("eat_ticks", 1)
        self._applied = False

    def can_execute(self, npc, world) -> bool:
        return npc.has_resource("food")

    def start(self, npc, world) -> None:
        log.debug(f"[{_stamp(world)}] {npc.name} started eating.")

    def apply(self, npc, world) -> None:
        if self._applied or not npc.has_resource("food"):
            return
        self._applied = True
        food = world.resources["food"]
        npc.consume_resource("food", 1)
        npc.needs.hunger = max(0.0, npc.needs.hunger - food.hunger_restore)
        npc.add_memory(_stamp(world), "ate", f"{npc.name} ate food at {npc.location_id}.", 3.0, "food")
        world.record_food_consumed(npc)
        log.info(f"[{_stamp(world)}] {npc.name} ate food.")

    def is_complete(self, npc, world) -> bool:
        return self._applied or self.ticks_elapsed >= self.ticks


class BuyFoodAction(Action):
    action_type = "buy_food"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.ticks = self._int("buy_ticks", 1)
        self.reserve = self._int("food_reserve", 3)

    def can_execute(self, npc, world) -> bool:
        economy = world.economy_for_location(npc.location_id)
        return (
            economy is not None
            and economy.is_shop_open(world.clock)
            and economy.can_buy_food(npc, world)
        )

    def start(self, npc, world) -> None:
        log.debug(f"[{_stamp(world)}] {npc.name} went shopping at the Market.")

    def apply(self, npc, world) -> None:
        if npc.inventory.get("food", 0) >= self.reserve:
            return
        economy = world.economy_for_location(npc.location_id)
        if economy is not None and economy.buy_food(npc, world):
            npc.add_resource("food", 1)
            npc.add_memory(_stamp(world), "bought_food", f"{npc.name} bought food at Market.", 4.0, "food")
            npc.add_memory(_stamp(world), "lost_money", f"{npc.name} spent money on food.", 2.0, "food")
            world.record_food_bought(npc)
            log.info(f"[{_stamp(world)}] {npc.name} bought food.")

    def is_complete(self, npc, world) -> bool:
        if npc.inventory.get("food", 0) >= self.reserve:
            return True
        return self.ticks_elapsed >= self.ticks