import unittest

from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.perception import PerceptionSystem
from world_sim.simulation.simulation import Simulation

from world_sim.tests.helpers import build_world, load_configs, set_time

SMALL_NPCS = {
    "npcs": [
        {
            "id": "npc_001",
            "name": "Alice",
            "age": 29,
            "money": 60,
            "job": "farmer",
            "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5},
        },
        {
            "id": "npc_002",
            "name": "Bob",
            "age": 41,
            "money": 45,
            "job": "merchant",
            "personality": {"sociability": 0.4, "ambition": 0.5, "risk_tolerance": 0.4, "work_ethic": 0.7, "generosity": 0.6},
        },
        {
            "id": "npc_003",
            "name": "Carla",
            "age": 34,
            "money": 55,
            "job": "worker",
            "personality": {"sociability": 0.6, "ambition": 0.6, "risk_tolerance": 0.2, "work_ethic": 0.8, "generosity": 0.7},
        },
    ]
}


def _run(seed, days=4):
    world_config, _ = load_configs()
    return Simulation(
        world_config,
        SMALL_NPCS,
        seed=seed,
        days=days,
        print_report=False,
    )


class TestSimulation(unittest.TestCase):
    def test_run_completes_and_produces_activity(self):
        sim = _run(seed=7)
        sim.run()
        stats = sim.world.stats
        self.assertGreater(stats.food_consumed, 0)
        self.assertGreater(stats.work_actions, 0)
        self.assertEqual(stats.deaths, 0)

    def test_same_seed_produces_same_result(self):
        first = _run(seed=42, days=3)
        first.run()
        second = _run(seed=42, days=3)
        second.run()
        money_a = [npc.money for npc in first.world.npcs]
        money_b = [npc.money for npc in second.world.npcs]
        self.assertEqual(money_a, money_b)
        self.assertEqual(first.world.stats.food_consumed, second.world.stats.food_consumed)
        self.assertEqual(first.world.stats.social_interactions, second.world.stats.social_interactions)

    def test_different_seed_produces_different_result(self):
        first = _run(seed=1, days=25)
        first.run()
        second = _run(seed=99, days=25)
        second.run()
        relationships_a = [dict(npc.relationships) for npc in first.world.npcs]
        relationships_b = [dict(npc.relationships) for npc in second.world.npcs]
        self.assertNotEqual(relationships_a, relationships_b)


class TestDecisionDiversity(unittest.TestCase):
    def test_npcs_make_diverse_decisions_in_morning(self):
        import random

        world = build_world()
        set_time(world, 7)
        ds = RuleBasedDecisionSystem(world.config, random.Random(3))
        perception_system = PerceptionSystem()
        goals = {
            ds.decide(npc, perception_system.perceive(npc, world), world).goal.type for npc in world.npcs
        }
        self.assertGreater(len(goals), 1)


class TrackingSimulation(Simulation):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.location_history = {}

    def _tick(self):
        super()._tick()
        for npc in self.world.alive_npcs():
            self.location_history.setdefault(npc.id, []).append(npc.location_id)


class TestNoOscillation(unittest.TestCase):
    def test_no_social_ping_pong_between_tavern_and_market(self):
        world_config, _ = load_configs()
        sim = TrackingSimulation(world_config, SMALL_NPCS, seed=7, days=3, print_report=False)
        sim.run()
        bounces = 0
        for history in sim.location_history.values():
            bounces += sum(
                1
                for i in range(len(history) - 2)
                if history[i] == history[i + 2] and {history[i], history[i + 1]} == {"tavern", "market"}
            )
        self.assertLessEqual(bounces, 4)


if __name__ == "__main__":
    unittest.main()