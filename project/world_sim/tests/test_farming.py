import random
import unittest

from world_sim.actions.working import WorkAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.goals import Goal, GoalType
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import build_world, load_configs

VALID_GOAL_ACTION = {
    "eat": {"eat", "move", "buy_food"},
    "buy_food": {"buy_food", "move"},
    "sleep": {"sleep", "move"},
    "work": {"work", "move"},
    "earn_money": {"work", "move"},
    "socialize": {"socialize", "move", "rest"},
    "explore": {"explore", "move"},
    "rest": {"rest"},
    "seek_health": {"rest", "move"},
    "move": {"move"},
}


def _farmer(world):
    return next(npc for npc in world.npcs if npc.job.id == "farmer")


def _non_farmer(world):
    return next(npc for npc in world.npcs if npc.job.id != "farmer")


def _run_shift(npc, world):
    decision = Decision(
        goal=Goal(GoalType.WORK, 10, npc.job.work_location),
        action_type="work",
        priority=10,
    )
    action = WorkAction(random.Random(1), world.config, decision)
    action.start(npc, world)
    for _ in range(npc.job.shift_ticks):
        action.tick(npc, world)
    return action


def _farming_world(farming_cfg=None, npcs=None):
    return build_world(world_config={"farming": farming_cfg or {}}, npcs_config=npcs)


def _sim(days, seed=42, extra=None, npcs=None):
    world_config, _ = load_configs()
    if extra:
        world_config.update(extra)
    return Simulation(world_config, npcs if npcs is not None else load_configs()[1], seed=seed, days=days, print_report=False)


class TestFarmerFoodProduction(unittest.TestCase):
    def test_farmer_produces_food_while_working(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 3, "farm_stock_cap": 100})
        farmer = _farmer(world)
        farmer.location_id = "farm"
        _run_shift(farmer, world)
        self.assertGreater(world.farm_stock, 0)
        self.assertEqual(world.stats.food_produced, world.farming_yield)

    def test_non_farmer_does_not_produce_farm_food(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 3, "farm_stock_cap": 100})
        merchant = _non_farmer(world)
        merchant.location_id = merchant.job.work_location
        self.assertFalse(merchant.job.produces_food)
        _run_shift(merchant, world)
        self.assertEqual(world.farm_stock, 0)
        self.assertEqual(world.stats.food_produced, 0)

    def test_production_only_during_valid_farmer_work_at_farm(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 3, "farm_stock_cap": 100})
        farmer = _farmer(world)
        farmer.location_id = "home"
        action = WorkAction(
            random.Random(1),
            world.config,
            Decision(goal=Goal(GoalType.WORK, 10, farmer.job.work_location), action_type="work", priority=10),
        )
        self.assertFalse(action.can_execute(farmer, world))
        _run_shift(farmer, world)
        self.assertEqual(world.farm_stock, 0)
        self.assertEqual(world.stats.food_produced, 0)

    def test_production_amount_follows_configuration(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 7, "farm_stock_cap": 100})
        farmer = _farmer(world)
        farmer.location_id = "farm"
        _run_shift(farmer, world)
        self.assertEqual(world.farm_stock, 7)
        self.assertEqual(world.stats.food_produced, 7)

    def test_production_is_deterministic_same_seed(self):
        def outcome(seed):
            sim = _sim(days=5, seed=seed)
            sim.run()
            return sim.world.stats.food_produced, sim.world.farm_stock, sim.world.stats.food_consumed

        self.assertEqual(outcome(42), outcome(42))
        self.assertEqual(outcome(1), outcome(1))

    def test_production_does_not_depend_on_rng_draws(self):
        a = build_world(seed=1, world_config={"farming": {"enabled": True, "yield_per_shift": 3, "farm_stock_cap": 100}})
        b = build_world(seed=9999, world_config={"farming": {"enabled": True, "yield_per_shift": 3, "farm_stock_cap": 100}})
        a.farm_stock = 10
        b.farm_stock = 10
        self.assertEqual(a.farm_produce(3), b.farm_produce(3))
        self.assertEqual(a.farm_stock, b.farm_stock)

    def test_produced_food_enters_correct_stock(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 4, "farm_stock_cap": 100})
        farmer = _farmer(world)
        farmer.location_id = "farm"
        before = world.stats.food_produced
        _run_shift(farmer, world)
        self.assertEqual(world.farm_stock, 4)
        self.assertEqual(world.stats.food_produced - before, world.farm_stock)

    def test_stock_cap_is_respected(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 10, "farm_stock_cap": 5})
        farmer = _farmer(world)
        farmer.location_id = "farm"
        _run_shift(farmer, world)
        self.assertEqual(world.farm_stock, 5)
        self.assertEqual(world.stats.food_produced, 5)
        _run_shift(farmer, world)
        self.assertEqual(world.farm_stock, 5)
        self.assertEqual(world.stats.food_produced, 5)

    def test_farmer_income_is_unchanged(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 3, "farm_stock_cap": 100})
        farmer = _farmer(world)
        farmer.location_id = "farm"
        before = farmer.money
        _run_shift(farmer, world)
        expected = before + farmer.job.income_per_tick * farmer.job.shift_ticks
        self.assertAlmostEqual(farmer.money, expected, places=6)

    def test_food_consumption_is_unchanged(self):
        def consumed(farming_enabled):
            sim = _sim(
                days=10,
                seed=42,
                extra={"farming": {"enabled": farming_enabled, "yield_per_shift": 3, "farm_stock_cap": 100}},
            )
            sim.run()
            return sim.world.stats.food_consumed

        self.assertEqual(consumed(True), consumed(False))

    def test_birth_and_death_do_not_break_production(self):
        sim = _sim(
            days=60,
            seed=42,
            extra={
                "aging": {"days_per_year": 10},
                "old_age": {"enabled": True, "max_age": 40},
                "birth": {"enabled": True, "interval_days": 10, "max_population": 40, "money": 10},
            },
        )
        sim.run()
        world = sim.world
        self.assertGreater(world.stats.food_produced, 0)
        self.assertGreater(world.stats.deaths, 0)
        self.assertGreater(world.stats.births, 0)
        self.assertGreaterEqual(world.farm_stock, 0)
        self.assertEqual(len(world.alive_npcs()), 20 - world.stats.deaths + world.stats.births)

    def test_no_invalid_goal_action_combinations(self):
        sim = _sim(days=30, seed=42)
        sim.run()
        for npc in sim.world.npcs:
            if not npc.alive:
                self.assertIsNone(npc.current_action)
                continue
            if npc.current_goal is not None and npc.current_action is not None:
                allowed = VALID_GOAL_ACTION.get(npc.current_goal.type.value, set())
                self.assertIn(npc.current_action.action_type, allowed)

    def test_market_draws_farm_stock_on_restock(self):
        world = _farming_world({"enabled": True, "yield_per_shift": 3, "farm_stock_cap": 100})
        world.farm_stock = 60
        world.economy.food_stock = 150
        drawn = world.economy.restock(world.farm_stock)
        world.farm_stock -= drawn
        self.assertGreater(drawn, 0)
        self.assertEqual(world.economy.food_stock, world.economy.restock_amount)
        self.assertEqual(world.farm_stock, 60 - drawn)


if __name__ == "__main__":
    unittest.main()