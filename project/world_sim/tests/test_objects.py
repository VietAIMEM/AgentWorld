import json
import random
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.actions.action import ActionManager
from world_sim.actions.interacting import InteractAction
from world_sim.decision.decision_system import Decision
from world_sim.decision.rule_based import DefaultActivityRule, RuleBasedDecisionSystem
from world_sim.npc.goals import Goal, GoalGenerator, GoalType
from world_sim.npc.perception import PerceptionSystem
from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
from world_sim.tests.helpers import build_world, load_configs
from world_sim.world.object import WorldObject


def interaction_configs(gen_seed=42, objects_enabled=True, interactions_enabled=True, behavior_enabled=True):
    wc, nc = load_configs()
    gen = dict(wc["world_generation"])
    gen["enabled"] = True
    gen["seed"] = gen_seed
    wc["world_generation"] = gen
    se = dict(wc["settlement_economy"])
    se["enabled"] = True
    wc["settlement_economy"] = se
    wc["behavior"] = {
        "enabled": behavior_enabled,
        "objects": {"enabled": objects_enabled},
        "interactions": interactions_enabled,
    }
    return wc, nc


def interaction_world(gen_seed=42, sim_seed=1, **kwargs):
    wc, nc = interaction_configs(gen_seed=gen_seed, **kwargs)
    return World(wc, nc, random.Random(sim_seed), run_days=30, seed=sim_seed)


def object_ids(world):
    return [obj.id for obj in world.objects]


def _decision(interaction, target_object_id):
    return Decision(
        goal=Goal(GoalType.REST, 10.0),
        action_type="interact",
        priority=10.0,
        candidates={"interaction": interaction, "target_object_id": target_object_id},
    )


def _effect_world(interaction, target_object_id="bench_0", npc_at="market"):
    wc, nc = load_configs()
    wc["behavior"] = {"enabled": True, "interactions": True}
    world = World(wc, nc, random.Random(1))
    world.add_object(
        WorldObject(id=target_object_id, name="Bench", location_id="market", object_type="bench", interactions=["sit"])
    )
    npc = world.npcs[0]
    npc.location_id = npc_at
    action = InteractAction(random.Random(1), world.config, _decision(interaction, target_object_id))
    return world, npc, action


def _tick_to_completion(action, npc, world):
    action.start(npc, world)
    for _ in range(action.ticks):
        action.tick(npc, world)


class TestObjectGeneration(unittest.TestCase):
    def test_generated_world_populates_objects(self):
        world = interaction_world()
        self.assertGreater(len(world.objects), 0)
        for obj in world.objects:
            self.assertIn(obj.location_id, world.locations)

    def test_generated_objects_match_location_type(self):
        world = interaction_world()
        tavern = next(loc for loc in world.locations.values() if loc.type == "social")
        tavern_types = {obj.object_type for obj in world.objects_at(tavern.id)}
        self.assertTrue({"table", "bench", "fire"} <= tavern_types)
        market = next(loc for loc in world.locations.values() if loc.type == "commercial")
        market_types = {obj.object_type for obj in world.objects_at(market.id)}
        self.assertTrue({"stall", "counter"} <= market_types)

    def test_objects_disabled_creates_none(self):
        world = interaction_world(objects_enabled=False)
        self.assertEqual(world.objects, [])

    def test_behavior_disabled_creates_none(self):
        world = interaction_world(behavior_enabled=False)
        self.assertEqual(world.objects, [])

    def test_interactions_disabled_still_generates_objects(self):
        world = interaction_world(interactions_enabled=False)
        self.assertGreater(len(world.objects), 0)

    def test_generation_deterministic_across_sim_seeds(self):
        a = interaction_world(sim_seed=1)
        b = interaction_world(sim_seed=99)
        self.assertEqual(object_ids(a), object_ids(b))

    def test_object_id_format(self):
        import re

        world = interaction_world()
        ids = object_ids(world)
        market_ids = [oid for oid in ids if "_market_stall_" in oid]
        self.assertTrue(market_ids)
        self.assertTrue(
            all(re.fullmatch(r"settlement_\d+_market_stall_\d+", oid) for oid in market_ids)
        )

    def test_generated_objects_start_available(self):
        world = interaction_world()
        for obj in world.objects:
            self.assertTrue(obj.is_available())
            self.assertIsNone(obj.in_use_by)

    def test_no_objects_in_non_generated_world(self):
        world = build_world(world_config={"behavior": {"enabled": True, "objects": {"enabled": True}}}, seed=1)
        self.assertEqual(world.objects, [])

    def test_generation_consumes_no_sim_rng(self):
        on = interaction_world(sim_seed=1)
        off = interaction_world(sim_seed=1, objects_enabled=False)
        self.assertEqual(on.rng.getstate(), off.rng.getstate())


class TestInteractionDecision(unittest.TestCase):
    def setUp(self):
        self.world = interaction_world()
        self.rule = DefaultActivityRule(self.world.config, random.Random(1), GoalGenerator(self.world.config))
        self.npc = self.world.npcs[0]
        self.workshop = next(loc.id for loc in self.world.locations.values() if loc.type == "workplace")
        self.npc.location_id = self.workshop
        self.npc.money = 60.0
        self.npc.inventory["food"] = 5
        self.npc.needs.hunger = 20.0
        self.npc.personality.risk_tolerance = 0.1
        self.npc.personality.sociability = 0.5
        self.npc.personality.ambition = 0.5
        self.npc.personality.work_ethic = 0.5
        for other in self.world.npcs:
            if other.id != self.npc.id:
                other.location_id = next(
                    loc.id for loc in self.world.locations.values() if loc.type == "residence"
                )
        self.world.clock.hour = 7

    def _perceive(self):
        return PerceptionSystem().perceive(self.npc, self.world)

    def test_wanted_interaction_by_needs(self):
        npc = self.npc
        npc.needs.energy, npc.needs.social = 50.0, 50.0
        self.assertEqual(self.rule._wanted_interaction(npc), "sit")
        npc.needs.energy, npc.needs.social = 70.0, 30.0
        self.assertEqual(self.rule._wanted_interaction(npc), "inspect")
        npc.needs.energy, npc.needs.social = 70.0, 50.0
        self.assertEqual(self.rule._wanted_interaction(npc), "use")
        npc.needs.energy, npc.needs.social = 90.0, 50.0
        self.assertEqual(self.rule._wanted_interaction(npc), "tend")

    def test_interact_absent_when_behavior_disabled(self):
        world = build_world(seed=1)
        npc = world.npcs[0]
        rule = DefaultActivityRule(world.config, random.Random(1), GoalGenerator(world.config))
        scores = rule._score(npc, PerceptionSystem().perceive(npc, world), world)
        self.assertNotIn("interact", scores)

    def test_interact_absent_when_objects_disabled(self):
        world = interaction_world(objects_enabled=False)
        rule = DefaultActivityRule(world.config, random.Random(1), GoalGenerator(world.config))
        npc = world.npcs[0]
        scores = rule._score(npc, PerceptionSystem().perceive(npc, world), world)
        self.assertNotIn("interact", scores)

    def test_interact_present_with_available_object(self):
        self.npc.needs.energy, self.npc.needs.social = 80.0, 30.0
        scores = self.rule._score(self.npc, self._perceive(), self.world)
        self.assertIn("interact", scores)

    def test_interact_absent_during_cooldown(self):
        self.npc.needs.energy, self.npc.needs.social = 80.0, 30.0
        self.npc.last_interact_tick = self.world.clock.tick
        scores = self.rule._score(self.npc, self._perceive(), self.world)
        self.assertNotIn("interact", scores)

    def test_interact_suppressed_during_work_window(self):
        self.npc.needs.energy, self.npc.needs.social = 80.0, 30.0
        self.world.clock.hour = 12
        scores = self.rule._score(self.npc, self._perceive(), self.world)
        self.assertIn("interact", scores)
        self.assertLess(scores["interact"], scores["rest"])

    def test_evaluate_returns_interact_decision(self):
        self.npc.needs.energy, self.npc.needs.social = 80.0, 30.0
        self.npc.last_socialize_day = self.world.clock.day
        decision = self.rule.evaluate(self.npc, self._perceive(), self.world)
        self.assertEqual(decision.action_type, "interact")
        self.assertEqual(decision.goal.type, GoalType.REST)
        self.assertIn("target_object_id", decision.candidates)
        self.assertEqual(decision.candidates["interaction"], "inspect")
        obj = self.world.objects_at(self.npc.location_id)
        self.assertIn(decision.candidates["target_object_id"], [o.id for o in obj])

    def test_interact_targets_lowest_id_object(self):
        self.world.objects_at(self.npc.location_id).clear()
        self.world.add_object(
            WorldObject(id="crate_b", name="Crate B", location_id=self.npc.location_id, object_type="crate", interactions=["inspect"])
        )
        self.world.add_object(
            WorldObject(id="crate_a", name="Crate A", location_id=self.npc.location_id, object_type="crate", interactions=["inspect"])
        )
        self.npc.needs.energy, self.npc.needs.social = 80.0, 30.0
        self.npc.last_socialize_day = self.world.clock.day
        decision = self.rule.evaluate(self.npc, self._perceive(), self.world)
        self.assertEqual(decision.candidates["target_object_id"], "crate_a")

    def test_interact_decision_consumes_no_rng(self):
        self.npc.needs.energy, self.npc.needs.social = 80.0, 30.0
        self.npc.last_socialize_day = self.world.clock.day
        before = self.world.rng.getstate()
        self.rule.evaluate(self.npc, self._perceive(), self.world)
        after = self.world.rng.getstate()
        self.assertEqual(before, after)

    def test_action_manager_builds_interact_action(self):
        self.npc.needs.energy, self.npc.needs.social = 80.0, 30.0
        self.npc.last_socialize_day = self.world.clock.day
        decision = self.rule.evaluate(self.npc, self._perceive(), self.world)
        manager = ActionManager(random.Random(1), self.world.config)
        action = manager.update(self.npc, decision, self.world)
        self.assertIsInstance(action, InteractAction)
        target_id = decision.candidates["target_object_id"]
        obj = next(o for o in self.world.objects if o.id == target_id)
        self.assertEqual(obj.in_use_by, self.npc.id)
        for _ in range(action.ticks):
            action.tick(self.npc, self.world)
        self.assertTrue(obj.is_available())
        self.assertEqual(self.npc.last_interact_tick, self.world.clock.tick)


class TestInteractionEffects(unittest.TestCase):
    def test_sit_effects(self):
        world, npc, action = _effect_world("sit")
        npc.needs.energy, npc.needs.social = 50.0, 50.0
        _tick_to_completion(action, npc, world)
        self.assertAlmostEqual(npc.needs.energy, 51.5)
        self.assertAlmostEqual(npc.needs.social, 51.0)
        self.assertEqual(world.objects[0].state, "available")
        self.assertIsNone(npc.intent)

    def test_use_effects(self):
        world, npc, action = _effect_world("use")
        npc.needs.energy, npc.needs.social = 50.0, 50.0
        _tick_to_completion(action, npc, world)
        self.assertAlmostEqual(npc.needs.energy, 52.0)
        self.assertAlmostEqual(npc.needs.social, 50.0)

    def test_inspect_effects(self):
        world, npc, action = _effect_world("inspect")
        npc.needs.energy, npc.needs.social = 50.0, 50.0
        _tick_to_completion(action, npc, world)
        self.assertAlmostEqual(npc.needs.social, 50.5)
        self.assertGreater(len(npc.memory.entries), 0)

    def test_tend_effects(self):
        world, npc, action = _effect_world("tend")
        npc.needs.energy, npc.needs.social = 50.0, 50.0
        _tick_to_completion(action, npc, world)
        self.assertAlmostEqual(npc.needs.energy, 48.0)
        self.assertGreater(len(npc.memory.entries), 0)

    def test_finish_sets_cooldown_tick(self):
        world, npc, action = _effect_world("sit")
        _tick_to_completion(action, npc, world)
        self.assertEqual(npc.last_interact_tick, world.clock.tick)

    def test_can_execute_rejects_unsupported_interaction(self):
        world, npc, action = _effect_world("use")
        self.assertFalse(action.can_execute(npc, world))

    def test_effects_consume_no_rng(self):
        world, npc, action = _effect_world("sit")
        before = world.rng.getstate()
        _tick_to_completion(action, npc, world)
        after = world.rng.getstate()
        self.assertEqual(before, after)

    def test_effects_leave_economy_untouched(self):
        world, npc, action = _effect_world("sit")
        food_stock = world.economy.food_stock
        farm_stock = world.farm_stock
        money = npc.money
        _tick_to_completion(action, npc, world)
        self.assertEqual(world.economy.food_stock, food_stock)
        self.assertEqual(world.farm_stock, farm_stock)
        self.assertEqual(npc.money, money)


class TestInteractionsInSim(unittest.TestCase):
    def test_full_sim_no_deaths_and_objects_released(self):
        wc, nc = interaction_configs()
        sim = Simulation(wc, nc, seed=42, days=30, print_report=False)
        sim.run()
        world = sim.world
        self.assertEqual(world.stats.deaths, 0)
        for obj in world.objects:
            self.assertTrue(obj.is_available())
            self.assertIsNone(obj.in_use_by)

    def test_full_sim_deterministic(self):
        wc, nc = interaction_configs()
        sim_a = Simulation(wc, nc, seed=7, days=30, print_report=False)
        sim_a.run()
        snap_a = json.dumps(asdict(sim_a.world.stats), sort_keys=True)
        sim_b = Simulation(wc, nc, seed=7, days=30, print_report=False)
        sim_b.run()
        snap_b = json.dumps(asdict(sim_b.world.stats), sort_keys=True)
        self.assertEqual(snap_a, snap_b)

    def test_death_releases_held_objects(self):
        world = interaction_world()
        npc = world.npcs[0]
        obj = world.objects[0]
        obj.in_use_by = npc.id
        obj.state = "in_use"
        world.npc_die(npc)
        self.assertTrue(obj.is_available())
        self.assertIsNone(obj.in_use_by)

    def test_save_load_roundtrip_objects_and_cooldown(self):
        wc, nc = interaction_configs()
        sim = Simulation(wc, nc, seed=42, days=15, print_report=False)
        sim.run()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            loaded = load_state(path, wc, nc)
        self.assertIn("objects", data)
        self.assertEqual(object_ids(loaded.world), object_ids(sim.world))
        self.assertEqual(
            {obj.id: obj.in_use_by for obj in loaded.world.objects},
            {obj.id: obj.in_use_by for obj in sim.world.objects},
        )
        self.assertEqual(
            {n.id: n.last_interact_tick for n in loaded.world.npcs},
            {n.id: n.last_interact_tick for n in sim.world.npcs},
        )

    def test_old_save_without_objects_loads(self):
        wc, nc = interaction_configs()
        sim = Simulation(wc, nc, seed=42, days=10, print_report=False)
        sim.run()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("objects", None)
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = load_state(path, wc, nc)
        self.assertEqual(object_ids(loaded.world), object_ids(interaction_world()))
        for obj in loaded.world.objects:
            self.assertTrue(obj.is_available())

    def test_disabled_run_matches_no_behavior_block(self):
        def run(behavior_block):
            wc, nc = interaction_configs(behavior_enabled=False)
            if not behavior_block:
                wc.pop("behavior", None)
            sim = Simulation(wc, nc, seed=42, days=30, print_report=False)
            sim.run()
            return sim

        with tempfile.TemporaryDirectory() as tmp:
            path_a = Path(tmp) / "a.json"
            path_b = Path(tmp) / "b.json"
            save_state(run(True), path_a)
            save_state(run(False), path_b)
            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())


if __name__ == "__main__":
    unittest.main()