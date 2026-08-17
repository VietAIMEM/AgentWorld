import random
import unittest

from world_sim.actions.working import WorkAction
from world_sim.decision.decision_system import Decision
from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.goals import Goal, GoalType
from world_sim.npc.perception import PerceptionSystem
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import build_world, load_configs, set_time

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


def _sink_world(amount=15, interval=1, enabled=True, money=100):
    world = build_world(
        world_config={"living_cost": {"enabled": enabled, "amount": amount, "interval_days": interval}},
        npcs_config=SINGLE_NPC,
    )
    world.npcs[0].money = money
    return world


def _sim(days, seed=42, extra=None):
    world_config, npcs_config = load_configs()
    if extra:
        world_config.update(extra)
    return Simulation(world_config, npcs_config, seed=seed, days=days, print_report=False)


def _decide(world, npc):
    ds = RuleBasedDecisionSystem(world.config, random.Random(3))
    return ds.decide(npc, PerceptionSystem().perceive(npc, world), world)


class TestLivingCostSink(unittest.TestCase):
    def test_expense_occurs_each_day_with_interval_one(self):
        world = _sink_world(amount=10, interval=1)
        npc = world.npcs[0]
        self.assertEqual(npc.money, 100)
        _advance_days(world, 3)
        self.assertEqual(npc.money, 70)
        self.assertEqual(world.stats.money_spent, 30)

    def test_expense_occurs_at_configured_weekly_interval(self):
        world = _sink_world(amount=10, interval=7, money=200)
        npc = world.npcs[0]
        _advance_days(world, 6)
        self.assertEqual(npc.money, 200)
        self.assertEqual(world.stats.money_spent, 0)
        _advance_days(world, 1)
        self.assertEqual(npc.money, 190)
        self.assertEqual(world.stats.money_spent, 10)
        _advance_days(world, 7)
        self.assertEqual(npc.money, 180)
        self.assertEqual(world.stats.money_spent, 20)

    def test_expense_is_deterministic(self):
        a = _sink_world(amount=10, interval=1)
        b = _sink_world(amount=10, interval=1)
        _advance_days(a, 5)
        _advance_days(b, 5)
        self.assertEqual(a.npcs[0].money, b.npcs[0].money)
        self.assertEqual(a.stats.money_spent, b.stats.money_spent)

    def test_npc_with_sufficient_money_pays_correctly(self):
        world = _sink_world(amount=15, interval=1)
        npc = world.npcs[0]
        _advance_days(world, 2)
        self.assertEqual(npc.money, 70)
        self.assertEqual(world.stats.money_spent, 30)

    def test_npc_with_insufficient_money_does_not_go_negative(self):
        world = _sink_world(amount=15, interval=1, money=5)
        npc = world.npcs[0]
        _advance_days(world, 7)
        self.assertEqual(npc.money, 5)
        self.assertEqual(world.stats.money_spent, 0)
        world2 = _sink_world(amount=15, interval=1, money=9.5)
        npc2 = world2.npcs[0]
        _advance_days(world2, 3)
        self.assertEqual(npc2.money, 9.5)

    def test_expense_does_not_alter_unrelated_needs(self):
        world = _sink_world(amount=15, interval=1)
        npc = world.npcs[0]
        before = (npc.needs.hunger, npc.needs.energy, npc.needs.social, npc.needs.health)
        _advance_days(world, 3)
        after = (npc.needs.hunger, npc.needs.energy, npc.needs.social, npc.needs.health)
        self.assertEqual(before, after)

    def test_low_money_rule_still_works(self):
        world = _sink_world(amount=15, interval=1)
        npc = world.npcs[0]
        npc.money = 5.0
        npc.location_id = npc.job.work_location
        set_time(world, 12)
        decision = _decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        self.assertEqual(decision.action_type, "work")

    def test_sink_can_push_npc_below_threshold_triggering_low_money(self):
        world = _sink_world(amount=15, interval=1, money=25)
        npc = world.npcs[0]
        _advance_days(world, 1)
        self.assertLess(npc.money, 20)
        npc.location_id = npc.job.work_location
        set_time(world, 12)
        decision = _decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)

    def test_work_income_remains_unchanged(self):
        world = _sink_world(amount=15, interval=1, money=100)
        npc = world.npcs[0]
        npc.location_id = "farm"
        decision = Decision(
            goal=Goal(GoalType.WORK, 10, npc.job.work_location),
            action_type="work",
            priority=10,
        )
        action = WorkAction(random.Random(1), world.config, decision)
        action.start(npc, world)
        for _ in range(npc.job.shift_ticks):
            action.tick(npc, world)
        self.assertAlmostEqual(npc.money, 100 + npc.job.income_per_tick * npc.job.shift_ticks, places=6)
        self.assertEqual(world.stats.money_spent, 0)

    def test_farmer_production_remains_unchanged(self):
        world = _sink_world(amount=15, interval=1, money=100)
        npc = world.npcs[0]
        npc.location_id = "farm"
        decision = Decision(
            goal=Goal(GoalType.WORK, 10, npc.job.work_location),
            action_type="work",
            priority=10,
        )
        action = WorkAction(random.Random(1), world.config, decision)
        action.start(npc, world)
        for _ in range(npc.job.shift_ticks):
            action.tick(npc, world)
        self.assertEqual(world.farm_stock, world.farming_yield)
        self.assertEqual(world.stats.food_produced, world.farming_yield)

    def test_birth_death_aging_unchanged(self):
        def outcome(sink_on):
            extra = {
                "aging": {"days_per_year": 10},
                "old_age": {"enabled": True, "max_age": 40},
                "birth": {"enabled": True, "interval_days": 10, "max_population": 40, "money": 10},
                "living_cost": {"enabled": sink_on, "amount": 0.01, "interval_days": 1},
            }
            sim = _sim(days=40, seed=42, extra=extra)
            sim.run()
            w = sim.world
            return (
                tuple((n.id, n.age) for n in w.npcs),
                w.stats.deaths,
                w.stats.old_age_deaths,
                w.stats.births,
                sum(n.money for n in w.npcs),
                w.stats.money_spent,
            )

        on = outcome(True)
        off = outcome(False)
        self.assertEqual(on[0], off[0])
        self.assertEqual(on[1], off[1])
        self.assertEqual(on[2], off[2])
        self.assertEqual(on[3], off[3])
        self.assertAlmostEqual(on[4], off[4] - on[5], places=4)

    def test_same_seed_remains_deterministic(self):
        def outcome(seed):
            sim = _sim(days=15, seed=seed)
            sim.run()
            return (
                sim.world.stats.money_spent,
                tuple(n.money for n in sim.world.npcs),
                tuple((n.id, n.age) for n in sim.world.npcs),
                sim.world.stats.deaths,
                sim.world.stats.food_produced,
            )

        self.assertEqual(outcome(42), outcome(42))
        self.assertEqual(outcome(1), outcome(1))

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

    def test_money_spent_recorded_in_stats(self):
        world = _sink_world(amount=12.5, interval=1)
        _advance_days(world, 4)
        self.assertAlmostEqual(world.stats.money_spent, 50.0, places=6)
        self.assertEqual(world.npcs[0].money, 50.0)


if __name__ == "__main__":
    unittest.main()