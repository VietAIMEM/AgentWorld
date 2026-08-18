import random
import unittest

from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.goals import GoalType
from world_sim.npc.perception import PerceptionSystem
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


def global_world():
    wc, nc = load_configs()
    return World(wc, nc, random.Random(1), run_days=30, seed=1)


def settlement_ids(world):
    return sorted(sid for sid, region in world.regions.items() if region.kind == "settlement")


def npc_of(world, sid):
    return next(npc for npc in world.npcs if npc.settlement_id == sid)


def decide(world, npc, seed=3):
    ds = RuleBasedDecisionSystem(world.config, random.Random(seed))
    perception = PerceptionSystem().perceive(npc, world)
    return ds.decide(npc, perception, world)


class TestLocalSocialLocation(unittest.TestCase):
    def test_local_social_location_is_own_tavern(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        self.assertEqual(world.local_social_location(npc), f"{sid}_tavern")

    def test_local_social_location_exists(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        tavern = world.local_social_location(npc)
        self.assertIn(tavern, world.locations)
        self.assertEqual(world.locations[tavern].type, "social")

    def test_global_social_location_when_disabled(self):
        world = global_world()
        npc = world.npcs[0]
        self.assertEqual(world.local_social_location(npc), world.social_location)


class TestSocialDecisionLocal(unittest.TestCase):
    def test_evening_moves_to_own_tavern(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        npc.location_id = f"{sid}_farm_0"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        world.clock.hour = 18
        decision = decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.target_location_id, f"{sid}_tavern")

    def test_each_settlement_uses_its_own_tavern(self):
        world = settlement_world(gen_seed=7, settlements=2)
        for sid in settlement_ids(world):
            npc = npc_of(world, sid)
            npc.location_id = f"{sid}_farm_0"
            npc.needs.social = 10.0
            npc.needs.hunger = 30.0
            npc.needs.energy = 90.0
            npc.money = 50.0
            world.clock.hour = 18
            decision = decide(world, npc)
            self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
            self.assertEqual(decision.target_location_id, f"{sid}_tavern")

    def test_disabled_mode_moves_to_global_tavern(self):
        world = global_world()
        npc = world.npcs[0]
        npc.location_id = "market"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        world.clock.hour = 18
        decision = decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.target_location_id, "tavern")

    def test_nearby_npc_triggers_socialize_with_partner(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        npc.location_id = f"{sid}_tavern"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        world.clock.hour = 18
        nearby = [other for other in world.npcs if other.location_id == npc.location_id and other.id != npc.id]
        decision = decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        if nearby:
            self.assertEqual(decision.action_type, "socialize")
            self.assertIn(decision.target_npc_id, {other.id for other in nearby})

    def test_partner_choice_deterministic(self):
        world = settlement_world(gen_seed=7, settlements=2)
        sid = settlement_ids(world)[0]
        npc = npc_of(world, sid)
        npc.location_id = f"{sid}_tavern"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        world.clock.hour = 18
        a = decide(world, npc, seed=3)
        b = decide(world, npc, seed=3)
        self.assertEqual(a.target_npc_id, b.target_npc_id)


if __name__ == "__main__":
    unittest.main()