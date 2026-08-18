from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SettlementEconomy:
    """Deterministic, RNG-free local economy for a single generated settlement."""

    settlement_id: str
    market_id: str
    primary_farm_id: str
    food_stock: int
    restock_amount: int
    farm_stock: int
    farm_stock_cap: int
    open_hour: int
    close_hour: int
    price_multiplier: float = 1.0

    def is_shop_open(self, clock) -> bool:
        return self.open_hour <= clock.hour < self.close_hour

    def food_price(self, world) -> float:
        resource = world.resources.get("food")
        base = resource.price if resource else 0.0
        return base * self.price_multiplier

    def can_buy_food(self, npc, world) -> bool:
        return self.food_stock > 0 and npc.money >= self.food_price(world)

    def buy_food(self, npc, world) -> bool:
        if not self.can_buy_food(npc, world):
            return False
        npc.money -= self.food_price(world)
        self.food_stock -= 1
        return True

    def restock(self) -> int:
        need = max(0, self.restock_amount - self.food_stock)
        take = min(self.farm_stock, need)
        self.food_stock += take
        self.farm_stock -= take
        return take

    def farm_produce(self, amount: int) -> int:
        if amount <= 0:
            return 0
        space = self.farm_stock_cap - self.farm_stock
        produced = min(amount, max(0, space))
        if produced > 0:
            self.farm_stock += produced
        return produced


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

    def restock(self, farm_stock: int) -> int:
        need = max(0, self.restock_amount - self.food_stock)
        take = min(farm_stock, need)
        self.food_stock += take
        if self.food_stock < self.restock_amount:
            self.food_stock = self.restock_amount
        return take
