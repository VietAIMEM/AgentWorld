import random
import unittest

from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.goals import GoalType
from world_sim.npc.perception import PerceptionSystem
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import build_world, load_configs, set_time

SINGLE_NPC = {
    "npcs": [
        {
            "id": "npc_001",
            "name": "Alice",
            "age": 30,
            "money": 100,
            "job": "farmer",
            "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5},
        }
    ]
}


def _advance_days(world, days):
    for _ in range(days * 24 * (60 // world.clock.tick_minutes)):
        world.update_time()


def _prog_world(money=100, amount=15, exempt=30, rate=0.8, interval=1, enabled=True):
    world = build_world(
        world_config={
            "living_cost": {
                "enabled": enabled,
                "amount": amount,
                "interval_days": interval,
                "exempt": exempt,
                "rate": rate,
            }
        },
        npcs_config=SINGLE_NPC,
    )
    world.npcs[0].money = money
    return world


def _sim(days, seed=42, extra=None):
    world_config, npcs_config = load_configs()
    if extra:
        world_config.update(extra)
    return Simulation(world_config, npcs_config, seed=seed, days=days, print_report=False)


class TestProgressiveLivingCost(unittest.TestCase):
    def test_below_exempt_pays_base_only(self):
        world = _prog_world(money=20)
        npc = world.npcs[0]
        world._apply_living_cost()
        self.assertEqual(npc.money, 5)
        self.assertAlmostEqual(world.stats.money_spent, 15.0, places=6)

    def test_at_exempt_pays_base_only(self):
        world = _prog_world(money=30)
        npc = world.npcs[0]
        world._apply_living_cost()
        self.assertEqual(npc.money, 15)
        self.assertAlmostEqual(world.stats.money_spent, 15.0, places=6)

    def test_above_exempt_pays_progressive_fee(self):
        world = _prog_world(money=50)
        npc = world.npcs[0]
        world._apply_living_cost()
        self.assertEqual(npc.money, 19)
        self.assertAlmostEqual(world.stats.money_spent, 31.0, places=6)
        world = _prog_world(money=100)
        npc = world.npcs[0]
        world._apply_living_cost()
        self.assertEqual(npc.money, 29)
        self.assertAlmostEqual(world.stats.money_spent, 71.0, places=6)

    def test_fee_formula_is_exact(self):
        cases = [(15, 15.0), (20, 15.0), (30, 15.0), (31, 15.8), (50, 31.0), (70, 47.0), (100, 71.0), (200, 151.0), (1000, 791.0)]
        for money, expected_fee in cases:
            world = _prog_world(money=money)
            npc = world.npcs[0]
            world._apply_living_cost()
            self.assertAlmostEqual(world.stats.money_spent, expected_fee, places=6, msg=f"money={money}")
            self.assertAlmostEqual(npc.money, money - expected_fee, places=6, msg=f"money={money}")

    def test_money_never_becomes_negative(self):
        for money in (0.0, 5.0, 14.0):
            world = _prog_world(money=money)
            npc = world.npcs[0]
            world._apply_living_cost()
            self.assertEqual(npc.money, money)
            self.assertAlmostEqual(world.stats.money_spent, 0.0, places=6)
        world = _prog_world(money=15)
        npc = world.npcs[0]
        world._apply_living_cost()
        self.assertEqual(npc.money, 0.0)
        self.assertAlmostEqual(world.stats.money_spent, 15.0, places=6)

    def test_progressive_fee_respects_interval(self):
        world = _prog_world(money=200, interval=7)
        npc = world.npcs[0]
        _advance_days(world, 6)
        self.assertEqual(npc.money, 200)
        self.assertAlmostEqual(world.stats.money_spent, 0.0, places=6)
        _advance_days(world, 1)
        self.assertEqual(npc.money, 49)
        self.assertAlmostEqual(world.stats.money_spent, 151.0, places=6)

    def test_progressive_cost_is_deterministic(self):
        a = _prog_world(money=100)
        b = _prog_world(money=100)
        _advance_days(a, 5)
        _advance_days(b, 5)
        self.assertEqual(a.npcs[0].money, b.npcs[0].money)
        self.assertAlmostEqual(a.stats.money_spent, b.stats.money_spent, places=6)

        def outcome(seed):
            sim = _sim(days=15, seed=seed)
            sim.run()
            return (sim.world.stats.money_spent, tuple(round(n.money, 4) for n in sim.world.npcs))

        self.assertEqual(outcome(42), outcome(42))
        self.assertEqual(outcome(1), outcome(1))

    def test_no_additional_rng_consumed(self):
        world = _prog_world(money=100)
        state_before = world.rng.getstate()
        world._apply_living_cost()
        self.assertEqual(world.rng.getstate(), state_before)

    def test_backward_compatibility_without_exempt_rate(self):
        world = build_world(
            world_config={"living_cost": {"enabled": True, "amount": 15, "interval_days": 1}},
            npcs_config=SINGLE_NPC,
        )
        npc = world.npcs[0]
        _advance_days(world, 2)
        self.assertEqual(npc.money, 70)
        self.assertAlmostEqual(world.stats.money_spent, 30.0, places=6)

    def test_money_spent_stats_accumulate_fees(self):
        world = _prog_world(money=100)
        npc = world.npcs[0]
        world._apply_living_cost()
        self.assertAlmostEqual(world.stats.money_spent, 71.0, places=6)
        npc.money = 100
        world._apply_living_cost()
        self.assertAlmostEqual(world.stats.money_spent, 142.0, places=6)
        self.assertEqual(npc.money, 29)

    def test_low_money_rule_still_fires(self):
        world = _prog_world(money=5)
        npc = world.npcs[0]
        npc.location_id = npc.job.work_location
        set_time(world, 12)
        ds = RuleBasedDecisionSystem(world.config, random.Random(3))
        decision = ds.decide(npc, PerceptionSystem().perceive(npc, world), world)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        self.assertEqual(decision.action_type, "work")

    def test_money_stays_bounded_over_long_run(self):
        sim = _sim(days=60, seed=42)
        sim.run()
        world = sim.world
        self.assertGreater(world.stats.money_spent, 0)
        for npc in world.npcs:
            self.assertGreaterEqual(npc.money, 0)
            self.assertLess(npc.money, 150)


if __name__ == "__main__":
    unittest.main()
