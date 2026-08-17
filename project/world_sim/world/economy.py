from __future__ import annotations


class EconomySystem:
    def __init__(self, config: dict, rng):
        econ = config.get("economy", {})
        self.food_stock = int(econ.get("food_stock", 200))
        self.restock_amount = int(econ.get("restock_amount", 200))
        shop = config.get("shop_hours", {})
        self.open_hour = int(shop.get("open", 8))
        self.close_hour = int(shop.get("close", 20))
        self.rng = rng

    def is_shop_open(self, clock) -> bool:
        return self.open_hour <= clock.hour < self.close_hour

    def food_price(self, world) -> float:
        resource = world.resources.get("food")
        return resource.price if resource else 0.0

    def can_buy_food(self, npc, world) -> bool:
        return self.food_stock > 0 and npc.money >= self.food_price(world)

    def buy_food(self, npc, world) -> bool:
        if not self.can_buy_food(npc, world):
            return False
        npc.money -= self.food_price(world)
        self.food_stock -= 1
        return True

    def restock(self) -> None:
        self.food_stock = self.restock_amount
