import copy
import json
import random
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.actions.idle import IdleAction
from world_sim.actions.interacting import InteractAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.goals import Goal, GoalType
from world_sim.npc.intent import Intent
from world_sim.npc.perception import PerceptionSystem
from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
from world_sim.tests.helpers import build_world, load_configs
from world_sim.world.object import WorldObject

_IDLE_TOKENS = ["look_around", "stretch", "sit", "inspect_nearby"]


def _build_world_with_behavior(behavior, seed=1):
    wc, nc = load_configs()
    wc["behavior"] = behavior
    return World(wc, nc, random.Random(seed), run_days=30, seed=seed)


def _interact_decision():
    return Decision(goal=Goal(GoalType.REST, 10.0), action_type="interact", priority=10.0)


def _idle_decision():
    return Decision(goal=Goal(GoalType.REST, 10.0), action_type="idle", priority=10.0)


class TestBehaviorConfig(unittest.TestCase):
    def test_behavior_config_defaults_to_disabled(self):
        wc, nc = load_configs()
        self.assertFalse(wc["behavior"]["enabled"])
        self.assertFalse(wc["behavior"]["routines"]["enabled"])
        self.assertEqual(wc["behavior"]["routines"]["default_bias"], 0.5)
        self.assertFalse(wc["behavior"]["idle"])
        self.assertFalse(wc["behavior"]["objects"]["enabled"])
        self.assertFalse(wc["behavior"]["interactions"])
        self.assertFalse(wc["behavior"]["conversations"]["enabled"])
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        self.assertFalse(world.behavior_enabled)
        self.assertFalse(world.behavior_routines_enabled)
        self.assertFalse(world.behavior_idle_enabled)
        self.assertFalse(world.behavior_objects_enabled)
        self.assertFalse(world.behavior_interactions_enabled)
        self.assertFalse(world.behavior_conversations_enabled)
        self.assertEqual(world.objects, [])

    def test_behavior_enabled_alone_leaves_subfeatures_disabled(self):
        world = _build_world_with_behavior({"enabled": True}, seed=1)
        self.assertTrue(world.behavior_enabled)
        self.assertFalse(world.behavior_routines_enabled)
        self.assertFalse(world.behavior_idle_enabled)
        self.assertFalse(world.behavior_objects_enabled)
        self.assertFalse(world.behavior_interactions_enabled)
        self.assertFalse(world.behavior_conversations_enabled)

    def test_behavior_flags_drive_world_storage(self):
        world = _build_world_with_behavior({"enabled": True, "objects": True}, seed=1)
        self.assertTrue(world.behavior_objects_enabled)
        self.assertEqual(world.objects_at("market"), [])


class TestNpcDefaults(unittest.TestCase):
    def test_npc_new_fields_have_safe_defaults(self):
        world = build_world(seed=1)
        npc = world.npcs[0]
        self.assertIsNone(npc.facing)
        self.assertIsNone(npc.intent)
        self.assertEqual(npc.routine_id, "farmer")
        self.assertIsNone(npc.conversation_id)
        self.assertIsNone(npc.idle_state)

    def test_intent_creation(self):
        intent = Intent(
            kind="work",
            started_tick=42,
            target_location_id="farm",
            context="routine",
        )
        self.assertEqual(intent.kind, "work")
        self.assertEqual(intent.started_tick, 42)
        self.assertEqual(intent.target_location_id, "farm")
        self.assertIsNone(intent.target_npc_id)
        self.assertIsNone(intent.target_object_id)
        self.assertEqual(intent.context, "routine")


class TestWorldObject(unittest.TestCase):
    def test_world_object_creation(self):
        obj = WorldObject(
            id="market_bench_0",
            name="Bench",
            location_id="market",
            object_type="bench",
            interactions=["sit"],
        )
        self.assertEqual(obj.id, "market_bench_0")
        self.assertEqual(obj.name, "Bench")
        self.assertEqual(obj.location_id, "market")
        self.assertEqual(obj.object_type, "bench")
        self.assertEqual(obj.interactions, ["sit"])
        self.assertEqual(obj.state, "available")
        self.assertIsNone(obj.in_use_by)
        self.assertTrue(obj.is_available())
        self.assertFalse(obj.is_in_use())

    def test_objects_at_lookup(self):
        world = _build_world_with_behavior({"enabled": True, "objects": True}, seed=1)
        world.add_object(
            WorldObject(id="bench_0", name="Bench", location_id="market", object_type="bench", interactions=["sit"])
        )
        world.add_object(
            WorldObject(id="table_0", name="Table", location_id="tavern", object_type="table", interactions=["sit"])
        )
        self.assertEqual([obj.id for obj in world.objects_at("market")], ["bench_0"])
        self.assertEqual([obj.id for obj in world.objects_at("tavern")], ["table_0"])
        self.assertEqual(world.objects_at("nowhere"), [])
        self.assertEqual(len(world.objects), 2)

    def test_objects_at_returns_copy(self):
        world = _build_world_with_behavior({"enabled": True, "objects": True}, seed=1)
        world.add_object(
            WorldObject(id="bench_0", name="Bench", location_id="market", object_type="bench", interactions=["sit"])
        )
        result = world.objects_at("market")
        result.clear()
        self.assertEqual(len(world.objects_at("market")), 1)


class TestInteractAction(unittest.TestCase):
    def _world_with_object(self, npc_at="market"):
        world = _build_world_with_behavior({"enabled": True, "interactions": True}, seed=1)
        world.add_object(
            WorldObject(id="bench_0", name="Bench", location_id="market", object_type="bench", interactions=["sit"])
        )
        for npc in world.npcs:
            npc.location_id = npc_at
        return world

    def test_lifecycle(self):
        world = self._world_with_object()
        npc = world.npcs[0]
        action = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        self.assertTrue(action.can_execute(npc, world))
        action.start(npc, world)
        obj = world.objects[0]
        self.assertEqual(obj.state, "in_use")
        self.assertEqual(obj.in_use_by, npc.id)
        self.assertFalse(action.is_complete(npc, world))
        for _ in range(action.ticks):
            action.tick(npc, world)
        self.assertTrue(action.is_complete(npc, world))
        self.assertEqual(obj.state, "available")
        self.assertIsNone(obj.in_use_by)

    def test_object_contention(self):
        world = self._world_with_object()
        npc1, npc2 = world.npcs[0], world.npcs[1]
        a1 = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        a2 = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        self.assertTrue(a1.can_execute(npc1, world))
        a1.start(npc1, world)
        self.assertFalse(a2.can_execute(npc2, world))

    def test_can_execute_requires_same_location(self):
        world = _build_world_with_behavior({"enabled": True, "interactions": True}, seed=1)
        world.add_object(
            WorldObject(id="bench_0", name="Bench", location_id="market", object_type="bench", interactions=["sit"])
        )
        npc = world.npcs[0]
        npc.location_id = "tavern"
        action = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        self.assertFalse(action.can_execute(npc, world))

    def test_can_execute_requires_object_to_exist(self):
        world = self._world_with_object()
        npc = world.npcs[0]
        action = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="missing")
        self.assertFalse(action.can_execute(npc, world))

    def test_cancel_releases_object(self):
        world = self._world_with_object()
        npc = world.npcs[0]
        action = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        action.start(npc, world)
        obj = world.objects[0]
        self.assertEqual(obj.state, "in_use")
        action.cancel(npc, world)
        self.assertEqual(obj.state, "available")
        self.assertIsNone(obj.in_use_by)

    def test_inert_when_interactions_disabled(self):
        world = _build_world_with_behavior({"enabled": True}, seed=1)
        world.add_object(
            WorldObject(id="bench_0", name="Bench", location_id="market", object_type="bench", interactions=["sit"])
        )
        npc = world.npcs[0]
        npc.location_id = "market"
        action = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        self.assertFalse(action.can_execute(npc, world))

    def test_no_rng_consumed(self):
        world = self._world_with_object()
        npc = world.npcs[0]
        action = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        before = world.rng.getstate()
        action.start(npc, world)
        for _ in range(action.ticks):
            action.tick(npc, world)
        after = world.rng.getstate()
        self.assertEqual(before, after)

    def test_no_economy_changes(self):
        world = self._world_with_object()
        npc = world.npcs[0]
        food_stock = world.economy.food_stock
        farm_stock = world.farm_stock
        money = npc.money
        action = InteractAction(random.Random(1), world.config, _interact_decision(), target_object_id="bench_0")
        action.start(npc, world)
        for _ in range(action.ticks):
            action.tick(npc, world)
        self.assertEqual(world.economy.food_stock, food_stock)
        self.assertEqual(world.farm_stock, farm_stock)
        self.assertEqual(npc.money, money)


class TestIdleAction(unittest.TestCase):
    def test_deterministic_token_selection(self):
        def pick(seed):
            world = _build_world_with_behavior({"enabled": True, "idle": True}, seed=seed)
            npc = world.npcs[0]
            action = IdleAction(random.Random(3), world.config, _idle_decision())
            self.assertTrue(action.can_execute(npc, world))
            action.start(npc, world)
            return action.idle_state, npc.idle_state

        first = pick(1)
        second = pick(1)
        self.assertEqual(first, second)
        self.assertIn(first[0], _IDLE_TOKENS)
        self.assertEqual(first[0], first[1])

    def test_no_rng_consumed(self):
        world = _build_world_with_behavior({"enabled": True, "idle": True}, seed=1)
        npc = world.npcs[0]
        action = IdleAction(random.Random(3), world.config, _idle_decision())
        before = world.rng.getstate()
        action.start(npc, world)
        action.tick(npc, world)
        after = world.rng.getstate()
        self.assertEqual(before, after)

    def test_idle_state_cleared_on_finish(self):
        world = _build_world_with_behavior({"enabled": True, "idle": True}, seed=1)
        npc = world.npcs[0]
        action = IdleAction(random.Random(3), world.config, _idle_decision())
        action.start(npc, world)
        self.assertIsNotNone(npc.idle_state)
        action.cancel(npc, world)
        self.assertIsNone(npc.idle_state)

    def test_inert_when_idle_disabled(self):
        world = _build_world_with_behavior({"enabled": True}, seed=1)
        npc = world.npcs[0]
        action = IdleAction(random.Random(3), world.config, _idle_decision())
        self.assertFalse(action.can_execute(npc, world))


class TestBehaviorDisabledParity(unittest.TestCase):
    def _snapshot(self, world):
        return {
            "clock": (world.clock.day, world.clock.hour, world.clock.minute, world.clock.tick),
            "elapsed_days": world._elapsed_days,
            "farm_stock": world.farm_stock,
            "npcs": [
                (
                    npc.id,
                    npc.location_id,
                    asdict(npc.needs),
                    npc.money,
                    npc.current_goal.type.value if npc.current_goal else None,
                    npc.alive,
                )
                for npc in world.npcs
            ],
            "stats": asdict(world.stats),
            "economy_food_stock": world.economy.food_stock,
            "events": [(event.type, event.start_tick, event.state.value) for event in world.events],
            "rng_state": world.rng.getstate(),
        }

    def test_behavior_disabled_matches_no_behavior_block(self):
        wc, nc = load_configs()
        with_behavior = copy.deepcopy(wc)
        self.assertIn("behavior", with_behavior)
        without_behavior = copy.deepcopy(wc)
        without_behavior.pop("behavior")
        sim_a = Simulation(with_behavior, nc, seed=42, days=10, print_report=False)
        sim_a.run(days=10)
        sim_b = Simulation(without_behavior, nc, seed=42, days=10, print_report=False)
        sim_b.run(days=10)
        self.assertEqual(self._snapshot(sim_a.world), self._snapshot(sim_b.world))

    def test_no_interact_or_idle_actions_emitted_when_disabled(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=42, days=5, print_report=False)
        sim.run(days=5)
        for npc in sim.world.npcs:
            self.assertNotEqual(getattr(npc.current_action, "action_type", None), "interact")
            self.assertNotEqual(getattr(npc.current_action, "action_type", None), "idle")


class TestPerceptionWhenDisabled(unittest.TestCase):
    def test_objects_empty_when_disabled(self):
        world = build_world(seed=1)
        npc = world.npcs[0]
        perception = PerceptionSystem().perceive(npc, world)
        self.assertEqual(perception.objects, [])
        self.assertEqual(perception.visible_npcs, perception.nearby_npcs)

    def test_objects_populated_when_enabled(self):
        world = _build_world_with_behavior({"enabled": True, "objects": True}, seed=1)
        npc = world.npcs[0]
        world.add_object(
            WorldObject(id="bench_0", name="Bench", location_id=npc.location_id, object_type="bench", interactions=["sit"])
        )
        perception = PerceptionSystem().perceive(npc, world)
        self.assertEqual([obj.id for obj in perception.objects], ["bench_0"])
        self.assertEqual(perception.nearby_npcs, perception.visible_npcs)


class TestBehaviorPersistence(unittest.TestCase):
    def test_old_save_without_new_fields_loads(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=1, days=5, print_report=False)
        sim.run(days=5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            for npc_data in data["npcs"]:
                for key in ("facing", "intent", "routine_id", "conversation_id", "idle_state"):
                    npc_data.pop(key, None)
            data.pop("objects", None)
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = load_state(path, wc, nc)
        for npc in loaded.world.npcs:
            self.assertIsNone(npc.facing)
            self.assertIsNone(npc.intent)
            self.assertIsNone(npc.routine_id)
            self.assertIsNone(npc.conversation_id)
            self.assertIsNone(npc.idle_state)
        self.assertEqual(loaded.world.objects, [])

    def test_round_trip_with_intent_and_objects(self):
        wc, nc = load_configs()
        wc["behavior"] = {"enabled": True, "objects": True}
        sim = Simulation(wc, nc, seed=1, days=5, print_report=False)
        sim.world.add_object(
            WorldObject(id="bench_0", name="Bench", location_id="market", object_type="bench", interactions=["sit"])
        )
        npc = sim.world.npcs[0]
        npc.intent = Intent(kind="work", started_tick=7, target_location_id="farm", context="routine")
        npc.facing = "south"
        npc.idle_state = "look_around"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            loaded = load_state(path, wc, nc)
        self.assertEqual(len(loaded.world.objects), 1)
        self.assertEqual(loaded.world.objects[0].id, "bench_0")
        loaded_npc = loaded.world.get_npc(npc.id)
        self.assertEqual(loaded_npc.intent.kind, "work")
        self.assertEqual(loaded_npc.intent.started_tick, 7)
        self.assertEqual(loaded_npc.intent.target_location_id, "farm")
        self.assertEqual(loaded_npc.intent.context, "routine")
        self.assertEqual(loaded_npc.facing, "south")
        self.assertEqual(loaded_npc.idle_state, "look_around")


if __name__ == "__main__":
    unittest.main()