import random
import unittest
import warnings
from dataclasses import asdict

from world_sim.actions.eating import BuyFoodAction
from world_sim.actions.working import WorkAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.goals import Goal, GoalType
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
from world_sim.world.economy import SettlementEconomy
from world_sim.tests.helpers import load_configs


def settlement_configs(gen_seed=42, se_overrides=None, **gen_overrides):
    wc, nc = load_configs()
    gen = dict(wc["world_generation"])
    gen["enabled"] = True
    gen["seed"] = gen_seed
    gen.update(gen_overrides)
    wc["world_generation"] = gen
    se = dict(wc["settlement_economy"])
    se["enabled"] = True
    if se_overrides:
        se.update(se_overrides)
    wc["settlement_economy"] = se
    return wc, nc


def settlement_world(gen_seed=42, sim_seed=1, **overrides):
    wc, nc = settlement_configs(gen_seed=gen_seed, **overrides)
    return World(wc, nc, random.Random(sim_seed), run_days=30, seed=sim_seed)


def settlement_simulation(gen_seed=42, sim_seed=42, days=30, **overrides):
    wc, nc = settlement_configs(gen_seed=gen_seed, **overrides)
    return Simulation(wc, nc, seed=sim_seed, days=days, print_report=False)


def settlement_ids(world):
    return sorted(sid for sid, region in world.regions.items() if region.kind == "settlement")


def npc_of(world, sid):
    return next(npc for npc in world.npcs if npc.settlement_id == sid)


def work_shift(npc, world):
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


class TestSettlementEconomyState(unittest.TestCase):
    def test_settlement_economies_created_when_enabled(self):
        world = settlement_world(gen_seed=7, settlements=2)
        expected = set(settlement_ids(world))
        self.assertEqual(set(world.settlement_economies), expected)
        for sid in expected:
            econ = world.settlement_economies[sid]
            self.assertEqual(econ.market_id, f"{sid}_market")
            self.assertIn(econ.primary_farm_id, world.locations)
            self.assertTrue(econ.primary_farm_id.startswith(f"{sid}_farm_"))
            self.assertEqual(econ.restock_amount, world.config["settlement_economy"]["restock_amount"])

    def test_no_settlement_economies_when_disabled(self):
        wc, nc = load_configs()
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        self.assertFalse(world.settlement_economy_enabled)
        self.assertEqual(world.settlement_economies, {})
        self.assertFalse(world.local_market_enabled)
        self.assertFalse(world.local_farm_stock_enabled)
        self.assertFalse(world.local_social_enabled)
        self.assertFalse(world.fallback_travel_enabled)

    def test_enabled_requires_generated_world(self):
        wc, nc = load_configs()
        wc["settlement_economy"]["enabled"] = True
        wc["world_generation"]["enabled"] = False
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        self.assertFalse(world.settlement_economy_enabled)
        self.assertEqual(world.settlement_economies, {})
        self.assertTrue(any("settlement_economy" in str(item.message) for item in caught))

    def test_helpers_resolve_local_market(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        self.assertIs(world.economy_for(npc), world.settlement_economies[sid])
        self.assertEqual(world.local_market_id(npc), f"{sid}_market")
        self.assertIs(
            world.economy_for_location(f"{sid}_market"),
            world.settlement_economies[sid],
        )

    def test_helpers_fallback_to_global_when_disabled(self):
        wc, nc = load_configs()
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        npc = world.npcs[0]
        self.assertIs(world.economy_for(npc), world.economy)
        self.assertEqual(world.local_market_id(npc), world.market_id)
        self.assertIs(world.economy_for_location(world.market_id), world.economy)
        self.assertIsNone(world.economy_for_location("tavern"))
        self.assertEqual(world.local_farm_stock(npc), world.farm_stock)

    def test_trade_is_always_disabled(self):
        world = settlement_world(gen_seed=7, se_overrides={"trade": True})
        self.assertFalse(world.trade_enabled)


class TestSettlementEconomyBehavior(unittest.TestCase):
    def test_is_shop_open_respects_hours(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        econ = world.settlement_economies[sid]
        world.clock.hour = econ.open_hour
        self.assertTrue(econ.is_shop_open(world.clock))
        world.clock.hour = econ.close_hour
        self.assertFalse(econ.is_shop_open(world.clock))

    def test_food_price_applies_multiplier(self):
        world = settlement_world(gen_seed=7, se_overrides={"price_multiplier": 2.0})
        sid = settlement_ids(world)[0]
        econ = world.settlement_economies[sid]
        base = world.resources["food"].price
        self.assertAlmostEqual(econ.food_price(world), base * 2.0, places=6)

    def test_buy_food_deducts_money_and_stock(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        econ = world.settlement_economies[sid]
        econ.food_stock = 5
        npc = npc_of(world, sid)
        npc.money = 100.0
        price = econ.food_price(world)
        self.assertTrue(econ.can_buy_food(npc, world))
        self.assertTrue(econ.buy_food(npc, world))
        self.assertAlmostEqual(npc.money, 100.0 - price, places=6)
        self.assertEqual(econ.food_stock, 4)

    def test_can_buy_false_when_out_of_stock(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        econ = world.settlement_economies[sid]
        econ.food_stock = 0
        npc = npc_of(world, sid)
        npc.money = 100.0
        self.assertFalse(econ.can_buy_food(npc, world))
        self.assertFalse(econ.buy_food(npc, world))
        self.assertEqual(npc.money, 100.0)

    def test_can_buy_false_when_insufficient_money(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        econ = world.settlement_economies[sid]
        econ.food_stock = 5
        npc = npc_of(world, sid)
        npc.money = 0.0
        self.assertFalse(econ.can_buy_food(npc, world))

    def test_restock_only_pulls_from_farm_stock(self):
        econ = SettlementEconomy(
            settlement_id="s0", market_id="s0_market", primary_farm_id="s0_farm_0",
            food_stock=190, restock_amount=200, farm_stock=10, farm_stock_cap=100,
            open_hour=8, close_hour=20,
        )
        taken = econ.restock()
        self.assertEqual(taken, 10)
        self.assertEqual(econ.food_stock, 200)
        self.assertEqual(econ.farm_stock, 0)

    def test_restock_never_exceeds_restock_amount(self):
        econ = SettlementEconomy(
            settlement_id="s0", market_id="s0_market", primary_farm_id="s0_farm_0",
            food_stock=190, restock_amount=200, farm_stock=50, farm_stock_cap=100,
            open_hour=8, close_hour=20,
        )
        taken = econ.restock()
        self.assertEqual(taken, 10)
        self.assertEqual(econ.food_stock, 200)
        self.assertEqual(econ.farm_stock, 40)

    def test_farm_produce_caps_at_cap(self):
        econ = SettlementEconomy(
            settlement_id="s0", market_id="s0_market", primary_farm_id="s0_farm_0",
            food_stock=0, restock_amount=200, farm_stock=95, farm_stock_cap=100,
            open_hour=8, close_hour=20,
        )
        produced = econ.farm_produce(10)
        self.assertEqual(produced, 5)
        self.assertEqual(econ.farm_stock, 100)


class TestSettlementMarketCommerce(unittest.TestCase):
    def test_buy_food_action_at_local_market(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        econ = world.settlement_economies[sid]
        econ.food_stock = 10
        world.clock.hour = econ.open_hour
        npc.location_id = econ.market_id
        npc.needs.hunger = 96.0
        npc.money = 100.0
        decision = Decision(
            goal=Goal(GoalType.BUY_FOOD, 20.0), action_type="buy_food", priority=20.0
        )
        action = BuyFoodAction(random.Random(3), world.config, decision)
        self.assertTrue(action.can_execute(npc, world))
        action.apply(npc, world)
        self.assertEqual(npc.inventory.get("food", 0), 1)
        self.assertEqual(world.stats.food_bought, 1)
        self.assertEqual(econ.food_stock, 9)

    def test_buy_food_action_fails_when_shop_closed(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        econ = world.settlement_economies[sid]
        econ.food_stock = 10
        world.clock.hour = econ.close_hour
        npc.location_id = econ.market_id
        npc.money = 100.0
        decision = Decision(
            goal=Goal(GoalType.BUY_FOOD, 20.0), action_type="buy_food", priority=20.0
        )
        action = BuyFoodAction(random.Random(3), world.config, decision)
        self.assertFalse(action.can_execute(npc, world))

    def test_work_produces_into_local_farm_stock(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        farmer = next(n for n in world.npcs if n.settlement_id == sid and n.job.produces_food)
        econ = world.settlement_economies[sid]
        farmer.location_id = farmer.job.work_location
        global_before = world.farm_stock
        work_shift(farmer, world)
        self.assertGreater(econ.farm_stock, 0)
        self.assertEqual(world.farm_stock, global_before)
        self.assertGreaterEqual(world.stats.food_produced, world.farming_yield)

    def test_restock_moves_farm_stock_to_market_on_rollover(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        econ = world.settlement_economies[sid]
        econ.food_stock = 0
        econ.farm_stock = 25
        day_before = world.clock.day
        for _ in range(200):
            world.update_time()
            if world.clock.day != day_before:
                break
        self.assertEqual(world.clock.day, day_before + 1)
        self.assertEqual(econ.food_stock, 25)
        self.assertEqual(econ.farm_stock, 0)

    def test_local_farm_stock_helper(self):
        world = settlement_world(gen_seed=7)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        econ = world.settlement_economies[sid]
        econ.farm_stock = 13
        self.assertEqual(world.local_farm_stock(npc), 13)


class TestSettlementEconomySimulation(unittest.TestCase):
    def test_local_mode_runs_simulation_invariants(self):
        sim = settlement_simulation(gen_seed=42, sim_seed=42, days=30)
        sim.run(days=30)
        world = sim.world
        self.assertEqual(world.stats.deaths, 0)
        self.assertEqual(world.stats.cross_settlement_travel, 0)
        self.assertGreater(world.stats.food_consumed, 0)
        for npc in world.npcs:
            self.assertGreaterEqual(npc.money, 0.0)
        for econ in world.settlement_economies.values():
            self.assertGreaterEqual(econ.food_stock, 0)
            self.assertGreaterEqual(econ.farm_stock, 0)

    def test_same_seed_local_mode_is_deterministic(self):
        a = settlement_simulation(gen_seed=42, sim_seed=99, days=10)
        b = settlement_simulation(gen_seed=42, sim_seed=99, days=10)
        a.run(days=10)
        b.run(days=10)
        self.assertEqual(asdict(a.world.stats), asdict(b.world.stats))
        self.assertEqual(
            {sid: asdict(econ) for sid, econ in a.world.settlement_economies.items()},
            {sid: asdict(econ) for sid, econ in b.world.settlement_economies.items()},
        )


if __name__ == "__main__":
    unittest.main()
