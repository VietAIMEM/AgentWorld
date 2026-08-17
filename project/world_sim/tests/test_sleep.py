import unittest

from world_sim.actions.sleeping import SleepAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.goals import Goal, GoalType

from world_sim.tests.helpers import build_world, first_npc, set_time


def _sleep_action(world, npc):
    decision = Decision(Goal(GoalType.SLEEP, 20.0), "sleep", 20.0)
    return SleepAction(world.rng, world.config, decision)


class TestContinuousNightSleep(unittest.TestCase):
    def setUp(self):
        self.world = build_world()
        self.npc = first_npc(self.world)
        self.npc.location_id = "home"
        self.npc.needs.hunger = 30.0
        self.npc.needs.social = 60.0

    def test_night_sleep_does_not_end_when_energy_reaches_full(self):
        self.npc.needs.energy = 60.0
        set_time(self.world, 22)
        action = _sleep_action(self.world, self.npc)
        action.start(self.npc, self.world)
        for _ in range(10):
            self.world.update_time()
            action.tick(self.npc, self.world)
        self.assertGreaterEqual(self.npc.needs.energy, 90.0)
        self.assertFalse(action.is_complete(self.npc, self.world))

    def test_night_sleep_ends_in_morning_wake_window(self):
        self.npc.needs.energy = 60.0
        set_time(self.world, 23)
        action = _sleep_action(self.world, self.npc)
        action.start(self.npc, self.world)
        for _ in range(42):
            self.world.update_time()
            action.tick(self.npc, self.world)
        self.assertEqual(self.world.clock.hour, 6)
        self.assertTrue(action.is_complete(self.npc, self.world))
        self.assertEqual(self.npc.last_wake_day, self.world.clock.day)

    def test_daytime_nap_ends_when_energy_restored(self):
        self.npc.needs.energy = 30.0
        set_time(self.world, 13)
        action = _sleep_action(self.world, self.npc)
        action.start(self.npc, self.world)
        for _ in range(12):
            action.tick(self.npc, self.world)
            if action.is_complete(self.npc, self.world):
                break
        self.assertTrue(action.is_complete(self.npc, self.world))
        self.assertGreaterEqual(self.npc.needs.energy, 90.0)

    def test_night_sleep_does_not_end_early_even_at_high_energy(self):
        self.npc.needs.energy = 95.0
        set_time(self.world, 22)
        action = _sleep_action(self.world, self.npc)
        action.start(self.npc, self.world)
        for _ in range(20):
            self.world.update_time()
            action.tick(self.npc, self.world)
        self.assertEqual(self.npc.needs.energy, 100.0)
        self.assertFalse(action.is_complete(self.npc, self.world))

    def test_no_sleep_restart_churn_during_night(self):
        from world_sim.actions.action import ActionManager
        from world_sim.decision.rule_based import RuleBasedDecisionSystem
        from world_sim.npc.perception import PerceptionSystem

        import random

        npc = self.npc
        npc.needs.energy = 60.0
        set_time(self.world, 22)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        manager = ActionManager(random.Random(3), self.world.config)
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        action = manager.update(npc, decision, self.world)
        self.assertEqual(action.action_type, "sleep")
        sleep_starts = 1
        prev_action = action
        for _ in range(47):
            self.world.update_time()
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            action = manager.update(npc, decision, self.world)
            if action.action_type == "sleep" and action is not prev_action:
                sleep_starts += 1
            prev_action = action
            action.tick(npc, self.world)
        self.assertEqual(sleep_starts, 1)


if __name__ == "__main__":
    unittest.main()