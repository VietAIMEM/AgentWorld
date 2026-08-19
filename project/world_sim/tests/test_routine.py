import copy
import json
import random
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.actions.movement import MoveAction
from world_sim.actions.working import WorkAction
from world_sim.decision.decision_system import Decision
from world_sim.decision.rule_based import DefaultActivityRule, RoutineRule, RuleBasedDecisionSystem
from world_sim.npc.goals import Goal, GoalGenerator, GoalStatus, GoalType
from world_sim.npc.intent import clear_intent, set_intent
from world_sim.npc.perception import PerceptionSystem
from world_sim.npc.routine import (
    ROUTINES,
    active_block,
    routine_for_npc,
    routine_id_for_job,
)
from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
from world_sim.tests.helpers import build_world, load_configs


def routines_config(behavior_enabled=True, routines_enabled=True, default_bias=0.5):
    return {
        "behavior": {
            "enabled": behavior_enabled,
            "routines": {"enabled": routines_enabled, "default_bias": default_bias},
        }
    }


def worker_npc(world):
    return next(n for n in world.npcs if n.job.id == "worker")


class TestRoutineProfile(unittest.TestCase):
    def test_job_to_routine_mapping(self):
        self.assertEqual(routine_id_for_job("farmer", 30), "farmer")
        self.assertEqual(routine_id_for_job("merchant", 30), "merchant")
        self.assertEqual(routine_id_for_job("worker", 30), "worker")
        self.assertEqual(routine_id_for_job("unknown", 30), "unemployed")
        self.assertEqual(routine_id_for_job(None, 30), "unemployed")

    def test_elderly_mapping(self):
        self.assertEqual(routine_id_for_job("farmer", 61), "elderly")
        self.assertEqual(routine_id_for_job("worker", 70), "elderly")
        self.assertEqual(routine_id_for_job("farmer", 59), "farmer")

    def test_built_npc_has_job_routine(self):
        world = build_world(seed=1)
        by_job = {}
        for npc in world.npcs:
            by_job.setdefault(npc.job.id, set()).add(npc.routine_id)
        self.assertEqual(by_job["farmer"], {"farmer"})
        self.assertEqual(by_job["merchant"], {"merchant"})
        self.assertEqual(by_job["worker"], {"worker"})

    def test_routine_profiles_exist(self):
        for name in ("worker", "farmer", "merchant", "unemployed", "social", "elderly"):
            self.assertIn(name, ROUTINES)
            self.assertEqual(ROUTINES[name].id, name)
            self.assertTrue(ROUTINES[name].blocks)

    def test_routine_for_npc_uses_routine_id(self):
        world = build_world(seed=1)
        npc = worker_npc(world)
        self.assertEqual(routine_for_npc(npc, world), ROUTINES["worker"])
        npc.routine_id = "social"
        self.assertEqual(routine_for_npc(npc, world), ROUTINES["social"])

    def test_routine_for_npc_falls_back_when_routine_id_missing(self):
        world = build_world(seed=1)
        npc = worker_npc(world)
        npc.routine_id = None
        self.assertEqual(routine_for_npc(npc, world), ROUTINES["worker"])

    def test_active_block_and_boundaries(self):
        routine = ROUTINES["worker"]
        self.assertEqual(active_block(routine, 8).activity, "work")
        self.assertEqual(active_block(routine, 11).activity, "work")
        self.assertEqual(active_block(routine, 12).activity, "eat")
        self.assertEqual(active_block(routine, 12).end_hour, 13)
        self.assertEqual(active_block(routine, 17).activity, "rest")
        self.assertEqual(active_block(routine, 18).activity, "socialize")
        self.assertEqual(active_block(routine, 23).activity, "rest")

    def test_active_block_wraps_midnight(self):
        routine = ROUTINES["unemployed"]
        self.assertEqual(active_block(routine, 2).activity, "sleep")
        self.assertEqual(active_block(routine, 6).activity, "sleep")
        self.assertEqual(active_block(routine, 7).activity, "rest")

    def test_deterministic_routine_selection(self):
        world = build_world(seed=1)
        npc = worker_npc(world)
        first = routine_for_npc(npc, world)
        second = routine_for_npc(npc, world)
        self.assertEqual(first.id, second.id)
        for hour in range(0, 24):
            self.assertEqual(active_block(first, hour), active_block(second, hour))


class TestRoutineScoring(unittest.TestCase):
    def _score_rules(self, config, rng):
        generator = GoalGenerator(config)
        return DefaultActivityRule(config, rng, generator), RoutineRule(config, rng, generator)

    def test_routine_bias_when_enabled(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        world.clock.hour = 10
        npc = worker_npc(world)
        perception = PerceptionSystem().perceive(npc, world)
        base_rule, routine_rule = self._score_rules(wc, random.Random(1))
        base = base_rule._score(npc, perception, world)
        biased = routine_rule._score(npc, perception, world)
        self.assertAlmostEqual(biased["work"] - base["work"], 0.5)
        self.assertEqual(biased["eat"], base["eat"])
        self.assertEqual(biased["socialize"], base["socialize"])

    def test_deterministic_scoring(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        npc = worker_npc(world)
        perception = PerceptionSystem().perceive(npc, world)
        _, routine_rule = self._score_rules(wc, random.Random(1))
        self.assertEqual(
            routine_rule._score(npc, perception, world),
            routine_rule._score(npc, perception, world),
        )

    def test_routine_bias_zero_when_disabled(self):
        wc, nc = load_configs()
        wc.update(routines_config(behavior_enabled=False))
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        world.clock.hour = 10
        npc = worker_npc(world)
        perception = PerceptionSystem().perceive(npc, world)
        base_rule, routine_rule = self._score_rules(wc, random.Random(1))
        self.assertIsNone(routine_rule.evaluate(npc, perception, world))
        self.assertEqual(
            routine_rule._score(npc, perception, world),
            base_rule._score(npc, perception, world),
        )

    def test_disabled_matches_no_behavior_block(self):
        wc, nc = load_configs()
        with_block = copy.deepcopy(wc)
        without_block = copy.deepcopy(wc)
        without_block.pop("behavior")

        def decisions(config):
            ds = RuleBasedDecisionSystem(config, random.Random(7))
            world = World(config, nc, random.Random(7), run_days=30, seed=7)
            npc = worker_npc(world)
            out = []
            for hour in range(0, 24):
                world.clock.hour = hour
                perception = PerceptionSystem().perceive(npc, world)
                decision = ds.decide(npc, perception, world)
                out.append((decision.action_type, decision.goal.type.value, decision.urgent))
            return out

        self.assertEqual(decisions(with_block), decisions(without_block))

    def test_urgent_needs_override_routine(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        world.clock.hour = 10
        npc = worker_npc(world)
        npc.needs.hunger = 96.0
        npc.money = 100.0
        ds = RuleBasedDecisionSystem(wc, random.Random(1))
        perception = PerceptionSystem().perceive(npc, world)
        decision = ds.decide(npc, perception, world)
        self.assertTrue(decision.urgent)
        self.assertEqual(decision.reason, "hunger_critical")
        self.assertEqual(decision.goal.type, GoalType.EAT)

    def test_commitment_prevents_routine_interruption(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        world.clock.hour = 20
        npc = worker_npc(world)
        npc.location_id = npc.job.work_location
        npc.current_goal = Goal(
            type=GoalType.WORK,
            priority=10.0,
            target=npc.job.work_location,
            status=GoalStatus.ACTIVE,
            started_tick=world.clock.tick,
        )
        ds = RuleBasedDecisionSystem(wc, random.Random(1))
        perception = PerceptionSystem().perceive(npc, world)
        decision = ds.decide(npc, perception, world)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        self.assertEqual(decision.action_type, "work")


class RecordingDecisionSystem:
    def __init__(self, inner):
        self.inner = inner
        self.log = []

    def decide(self, npc, perception, world):
        decision = self.inner.decide(npc, perception, world)
        self.log.append((npc.id, world.clock.tick, decision.goal.type))
        return decision


class TestRoutineNoOscillation(unittest.TestCase):
    def test_no_consecutive_goal_oscillation(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        recorder = RecordingDecisionSystem(RuleBasedDecisionSystem(copy.deepcopy(wc), random.Random(42)))
        sim = Simulation(copy.deepcopy(wc), nc, seed=42, days=3, decision_system=recorder, print_report=False)
        sim.run(days=3)
        by_npc = {}
        for npc_id, tick, goal_type in recorder.log:
            by_npc.setdefault(npc_id, []).append(goal_type)
        flip_targets = {GoalType.WORK, GoalType.SOCIALIZE}
        for npc_id, sequence in by_npc.items():
            for i in range(2, len(sequence)):
                a, b, c = sequence[i - 2], sequence[i - 1], sequence[i]
                if a == c and a != b and a in flip_targets and b in flip_targets:
                    self.fail(f"{npc_id} oscillated work/social on consecutive ticks")


class TestIntent(unittest.TestCase):
    def _world(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        return World(wc, nc, random.Random(1), run_days=30, seed=1), wc

    def test_intent_creation_on_work(self):
        world, wc = self._world()
        npc = worker_npc(world)
        npc.location_id = npc.job.work_location
        action = WorkAction(
            random.Random(1),
            wc,
            Decision(goal=Goal(GoalType.WORK, 10.0, npc.job.work_location), action_type="work", priority=10.0),
        )
        action.start(npc, world)
        self.assertIsNotNone(npc.intent)
        self.assertEqual(npc.intent.kind, "working")
        self.assertEqual(npc.intent.target_location_id, npc.job.work_location)
        self.assertEqual(npc.intent.started_tick, world.clock.tick)

    def test_intent_transition(self):
        world, wc = self._world()
        npc = worker_npc(world)
        npc.location_id = npc.home_id
        commute = MoveAction(
            random.Random(1),
            wc,
            Decision(
                goal=Goal(GoalType.WORK, 10.0, npc.job.work_location),
                action_type="move",
                priority=10.0,
                target_location_id=npc.job.work_location,
            ),
        )
        commute.start(npc, world)
        self.assertEqual(npc.intent.kind, "commute_to_work")
        self.assertEqual(npc.intent.target_location_id, npc.job.work_location)

        npc.location_id = npc.job.work_location
        work = WorkAction(
            random.Random(1),
            wc,
            Decision(goal=Goal(GoalType.WORK, 10.0, npc.job.work_location), action_type="work", priority=10.0),
        )
        work.start(npc, world)
        self.assertEqual(npc.intent.kind, "working")

        home_move = MoveAction(
            random.Random(1),
            wc,
            Decision(
                goal=Goal(GoalType.SLEEP, 10.0, npc.home_id),
                action_type="move",
                priority=10.0,
                target_location_id=npc.home_id,
            ),
        )
        home_move.start(npc, world)
        self.assertEqual(npc.intent.kind, "returning_home")
        self.assertEqual(npc.intent.target_location_id, npc.home_id)

    def test_intent_cleared_on_finish(self):
        world, wc = self._world()
        npc = worker_npc(world)
        npc.location_id = npc.job.work_location
        action = WorkAction(
            random.Random(1),
            wc,
            Decision(goal=Goal(GoalType.WORK, 10.0, npc.job.work_location), action_type="work", priority=10.0),
        )
        action.start(npc, world)
        self.assertEqual(npc.intent.kind, "working")
        action.finish(npc, world)
        self.assertIsNone(npc.intent)

    def test_intent_not_set_when_behavior_disabled(self):
        wc, nc = load_configs()
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        npc = worker_npc(world)
        npc.location_id = npc.job.work_location
        action = WorkAction(
            random.Random(1),
            wc,
            Decision(goal=Goal(GoalType.WORK, 10.0, npc.job.work_location), action_type="work", priority=10.0),
        )
        action.start(npc, world)
        self.assertIsNone(npc.intent)

    def test_set_intent_helper_no_rng(self):
        world, wc = self._world()
        npc = worker_npc(world)
        before = world.rng.getstate()
        set_intent(npc, world, "eating", target_location_id=npc.location_id)
        clear_intent(npc, world)
        self.assertEqual(world.rng.getstate(), before)


class TestRoutinePersistence(unittest.TestCase):
    def test_routine_and_intent_persist(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        sim = Simulation(copy.deepcopy(wc), nc, seed=1, days=5, print_report=False)
        npc = worker_npc(sim.world)
        set_intent(npc, sim.world, "working", target_location_id=npc.job.work_location)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            loaded = load_state(path, wc, nc)
        loaded_npc = loaded.world.get_npc(npc.id)
        self.assertEqual(loaded_npc.routine_id, npc.routine_id)
        self.assertEqual(loaded_npc.intent.kind, "working")
        self.assertEqual(loaded_npc.intent.target_location_id, npc.job.work_location)

    def test_old_save_without_routine_and_intent_loads(self):
        wc, nc = load_configs()
        sim = Simulation(copy.deepcopy(wc), nc, seed=1, days=5, print_report=False)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            for npc_data in data["npcs"]:
                npc_data.pop("routine_id", None)
                npc_data.pop("intent", None)
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = load_state(path, wc, nc)
        for loaded_npc in loaded.world.npcs:
            self.assertIsNone(loaded_npc.intent)
            self.assertIsNone(loaded_npc.routine_id)


class TestRoutineRng(unittest.TestCase):
    def test_routine_selection_no_rng(self):
        world = build_world(seed=1)
        npc = worker_npc(world)
        before = world.rng.getstate()
        routine_for_npc(npc, world)
        for hour in range(0, 24):
            active_block(routine_for_npc(npc, world), hour)
        self.assertEqual(world.rng.getstate(), before)

    def test_routine_scoring_no_rng(self):
        wc, nc = load_configs()
        wc.update(routines_config())
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        npc = worker_npc(world)
        perception = PerceptionSystem().perceive(npc, world)
        before = world.rng.getstate()
        _, routine_rule = self._score_rules(wc, random.Random(1))
        routine_rule._score(npc, perception, world)
        self.assertEqual(world.rng.getstate(), before)

    def _score_rules(self, config, rng):
        generator = GoalGenerator(config)
        return DefaultActivityRule(config, rng, generator), RoutineRule(config, rng, generator)

    def test_full_sim_routines_enabled_no_rng_consumption(self):
        wc, nc = load_configs()
        disabled = copy.deepcopy(wc)
        zero_bias = copy.deepcopy(wc)
        zero_bias.update(routines_config(default_bias=0.0))

        def snapshot(sim):
            world = sim.world
            return (
                sim.rng.getstate(),
                world.clock.tick,
                [(n.id, n.location_id, n.money, n.alive) for n in world.npcs],
                world.stats.food_consumed,
                world.stats.work_actions,
                world.stats.social_interactions,
                (world.economy.food_stock, world.farm_stock),
            )

        sim_off = Simulation(copy.deepcopy(disabled), nc, seed=42, days=5, print_report=False)
        sim_off.run(days=5)
        sim_zero = Simulation(copy.deepcopy(zero_bias), nc, seed=42, days=5, print_report=False)
        sim_zero.run(days=5)
        self.assertEqual(snapshot(sim_off), snapshot(sim_zero))

    def test_same_seed_identical_results(self):
        wc, nc = load_configs()
        wc.update(routines_config())

        def snapshot(sim):
            world = sim.world
            return (
                sim.rng.getstate(),
                [(n.id, n.location_id, n.money, n.alive, asdict(n.needs)) for n in world.npcs],
                world.stats.food_consumed,
                world.stats.work_actions,
                world.stats.social_interactions,
            )

        sim_a = Simulation(copy.deepcopy(wc), nc, seed=99, days=5, print_report=False)
        sim_a.run(days=5)
        sim_b = Simulation(copy.deepcopy(wc), nc, seed=99, days=5, print_report=False)
        sim_b.run(days=5)
        self.assertEqual(snapshot(sim_a), snapshot(sim_b))


if __name__ == "__main__":
    unittest.main()