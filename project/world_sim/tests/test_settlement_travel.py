import random
import unittest
from collections import deque

from world_sim.decision.rule_based import (
    _fallback_markets,
    _food_market_candidates,
    _nearest_natural,
)
from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.goals import GoalType
from world_sim.npc.perception import PerceptionSystem
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
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


def reachable(world, start):
    if start not in world.locations:
        return set()
    seen = {start}
    queue = deque(world.locations[start].connected)
    while queue:
        nid = queue.popleft()
        if nid in seen or nid not in world.locations:
            continue
        seen.add(nid)
        queue.extend(world.locations[nid].connected)
    return seen


def decide(world, npc, seed=3):
    ds = RuleBasedDecisionSystem(world.config, random.Random(seed))
    perception = PerceptionSystem().perceive(npc, world)
    return ds.decide(npc, perception, world)


class TestFallbackMarkets(unittest.TestCase):
    def test_fallback_markets_empty_when_disabled(self):
        wc, nc = load_configs()
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        self.assertFalse(world.fallback_travel_enabled)
        npc = world.npcs[0]
        self.assertEqual(_fallback_markets(npc, world), [])

    def test_fallback_markets_empty_in_single_settlement(self):
        world = settlement_world(gen_seed=7, settlements=1)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        self.assertEqual(_fallback_markets(npc, world), [])

    def test_fallback_markets_ordered_by_distance_then_id(self):
        world = settlement_world(gen_seed=7, settlements=3)
        sids = settlement_ids(world)
        npc = npc_of(world, sids[0])
        world.clock.hour = 8
        for econ in world.settlement_economies.values():
            econ.food_stock = 50
        markets = _fallback_markets(npc, world)
        self.assertGreater(len(markets), 0)
        self.assertNotIn(world.local_market_id(npc), markets)
        for market in markets:
            self.assertIn(market, world.locations)
            self.assertEqual(world.locations[market].type, "commercial")
        self.assertEqual(markets, sorted(markets))

    def test_fallback_markets_exclude_unstocked_markets(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sids = settlement_ids(world)
        npc = npc_of(world, sids[0])
        world.clock.hour = 8
        for econ in world.settlement_economies.values():
            econ.food_stock = 0
        self.assertEqual(_fallback_markets(npc, world), [])

    def test_fallback_markets_consume_no_rng(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sids = settlement_ids(world)
        npc = npc_of(world, sids[0])
        world.clock.hour = 8
        for econ in world.settlement_economies.values():
            econ.food_stock = 50
        before = world.rng.getstate()
        _fallback_markets(npc, world)
        self.assertEqual(world.rng.getstate(), before)

    def test_fallback_markets_deterministic_same_seed(self):
        def outcome(seed):
            world = settlement_world(gen_seed=seed, settlements=2)
            npc = npc_of(world, settlement_ids(world)[0])
            world.clock.hour = 8
            for econ in world.settlement_economies.values():
                econ.food_stock = 50
            return tuple(_fallback_markets(npc, world))

        self.assertEqual(outcome(3), outcome(3))

    def test_food_market_candidates_local_first(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        candidates = _food_market_candidates(npc, world)
        self.assertEqual(candidates[0], f"{sid}_market")

    def test_food_market_candidates_single_market_when_disabled(self):
        wc, nc = load_configs()
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        npc = world.npcs[0]
        self.assertEqual(_food_market_candidates(npc, world), [world.market_id])


class TestFallbackDecision(unittest.TestCase):
    def test_local_empty_fallback_stocked_triggers_fallback_move(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sids = settlement_ids(world)
        local, other = sids[0], sids[1]
        npc = npc_of(world, local)
        npc.location_id = npc.home_id
        npc.inventory.pop("food", None)
        npc.needs.hunger = 95.0
        npc.needs.social = 50.0
        npc.needs.energy = 90.0
        npc.money = 100.0
        world.settlement_economies[local].food_stock = 0
        world.settlement_economies[other].food_stock = 50
        world.clock.hour = world.settlement_economies[other].open_hour
        decision = decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, f"{other}_market")

    def test_local_stocked_no_fallback_move(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sids = settlement_ids(world)
        local = sids[0]
        npc = npc_of(world, local)
        npc.location_id = npc.home_id
        npc.inventory.pop("food", None)
        npc.needs.hunger = 95.0
        npc.needs.social = 50.0
        npc.needs.energy = 90.0
        npc.money = 100.0
        world.settlement_economies[local].food_stock = 50
        world.clock.hour = world.settlement_economies[local].open_hour
        decision = decide(world, npc)
        self.assertEqual(decision.target_location_id, f"{local}_market")


class TestCrossSettlementRecording(unittest.TestCase):
    def test_crossing_between_settlements_counts(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sids = settlement_ids(world)
        npc = npc_of(world, sids[0])
        world.record_settlement_crossing(npc, f"{sids[0]}_market", f"{sids[1]}_market")
        self.assertEqual(world.stats.cross_settlement_travel, 1)

    def test_crossing_within_settlement_not_counted(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        world.record_settlement_crossing(npc, f"{sid}_market", f"{sid}_tavern")
        self.assertEqual(world.stats.cross_settlement_travel, 0)

    def test_crossing_from_wilderness_not_counted(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        world.record_settlement_crossing(npc, "wilderness_0", f"{sid}_market")
        self.assertEqual(world.stats.cross_settlement_travel, 0)

    def test_no_cross_settlement_travel_without_shortage(self):
        sim = settlement_simulation(gen_seed=42, sim_seed=42, days=30)
        sim.run(days=30)
        self.assertEqual(sim.world.stats.cross_settlement_travel, 0)


class TestExplorationPreference(unittest.TestCase):
    def test_exploration_prefers_same_region_natural(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        adjacent = {
            lid
            for lid, loc in world.locations.items()
            if loc.type == "natural"
            and any(world.locations[c].region_id == sid for c in loc.connected)
        }
        reach = reachable(world, npc.home_id)
        candidates = adjacent & reach
        if not candidates:
            self.skipTest("no same-region natural reachable for this seed")
        result = _nearest_natural(world, npc.home_id, npc)
        self.assertIsNotNone(result)
        self.assertIn(result, candidates)

    def test_nearest_natural_without_npc_is_deterministic(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        a = _nearest_natural(world, npc.home_id)
        b = _nearest_natural(world, npc.home_id)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()