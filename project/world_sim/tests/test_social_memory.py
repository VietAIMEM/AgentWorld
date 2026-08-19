import random
import unittest

from world_sim.actions.working import WorkAction
from world_sim.actions.eating import EatAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.goals import Goal, GoalType
from world_sim.npc.social_memory import SocialMemorySystem
from world_sim.tests.helpers import build_world, load_configs


def social_configs(enabled=True, memory_size=50):
    wc, nc = load_configs()
    wc["memory"] = {"max_size": memory_size}
    wc["behavior"] = {
        "enabled": True,
        "conversations": {"enabled": True, "max_turns": 4},
        "social_life": {"enabled": enabled},
    }
    return wc, nc


def social_world(seed=1, enabled=True, memory_size=50):
    wc, nc = social_configs(enabled=enabled, memory_size=memory_size)
    return build_world(seed, wc, nc)


def _work_action(config, npc):
    decision = Decision(
        goal=Goal(GoalType.WORK, 10.0, npc.job.work_location),
        action_type="work",
        priority=10.0,
    )
    return WorkAction(random.Random(1), config, decision)


def _eat_action(config, npc):
    decision = Decision(goal=Goal(GoalType.EAT, 10.0), action_type="eat", priority=10.0)
    return EatAction(random.Random(1), config, decision)


def _place(world, npc, location_id, action):
    npc.location_id = location_id
    npc.current_action = action


class TestSocialMemorySystem(unittest.TestCase):
    def setUp(self):
        self.system = SocialMemorySystem()

    def test_disabled_mode_does_nothing(self):
        world = social_world(enabled=False)
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "farm", _work_action(world.config, a))
        _place(world, b, "farm", _work_action(world.config, b))
        world.clock.hour = 12
        world.clock.minute = 0
        self.system.tick(world)
        self.assertEqual(len(a.memory.entries), 0)
        self.assertEqual(len(b.memory.entries), 0)

    def test_other_hour_does_nothing(self):
        world = social_world()
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "farm", _work_action(world.config, a))
        _place(world, b, "farm", _work_action(world.config, b))
        world.clock.hour = 9
        self.system.tick(world)
        self.assertEqual(len(a.memory.entries), 0)

    def test_working_together_writes_worked_with(self):
        world = social_world()
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "farm", _work_action(world.config, a))
        _place(world, b, "farm", _work_action(world.config, b))
        world.clock.hour = 12
        world.clock.minute = 0
        self.system.tick(world)
        self.assertEqual(len(a.memory.recent("worked_with")), 1)
        self.assertEqual(len(b.memory.recent("worked_with")), 1)
        self.assertEqual(a.memory.recent("worked_with")[0].related_entity, b.id)
        self.assertEqual(b.memory.recent("worked_with")[0].related_entity, a.id)

    def test_eating_together_writes_ate_with(self):
        world = social_world()
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "market", _eat_action(world.config, a))
        _place(world, b, "market", _eat_action(world.config, b))
        world.clock.hour = 12
        world.clock.minute = 0
        self.system.tick(world)
        self.assertEqual(len(a.memory.recent("ate_with")), 1)
        self.assertEqual(len(b.memory.recent("ate_with")), 1)

    def test_mixed_activities_write_nothing(self):
        world = social_world()
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "farm", _work_action(world.config, a))
        _place(world, b, "farm", _eat_action(world.config, b))
        world.clock.hour = 12
        world.clock.minute = 0
        self.system.tick(world)
        self.assertEqual(len(a.memory.entries), 0)
        self.assertEqual(len(b.memory.entries), 0)

    def test_only_one_write_per_day(self):
        world = social_world()
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "farm", _work_action(world.config, a))
        _place(world, b, "farm", _work_action(world.config, b))
        world.clock.hour = 12
        world.clock.minute = 0
        world.clock.minute = 0
        self.system.tick(world)
        world.clock.minute = 30
        self.system.tick(world)
        world.clock.minute = 50
        self.system.tick(world)
        self.assertEqual(len(a.memory.recent("worked_with")), 1)
        world.clock.day = 2
        world.clock.minute = 0
        self.system.tick(world)
        self.assertEqual(len(a.memory.recent("worked_with")), 2)

    def test_respects_memory_cap(self):
        world = social_world(memory_size=3)
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "farm", _work_action(world.config, a))
        _place(world, b, "farm", _work_action(world.config, b))
        world.clock.hour = 12
        world.clock.minute = 0
        for _ in range(5):
            self.system.tick(world)
            self.system.tick(world)
            self.system.tick(world)
        self.assertLessEqual(len(a.memory.entries), 3)
        self.assertLessEqual(len(b.memory.entries), 3)

    def test_deterministic(self):
        def snapshot():
            world = social_world()
            a, b = world.npcs[0], world.npcs[1]
            _place(world, a, "farm", _work_action(world.config, a))
            _place(world, b, "farm", _work_action(world.config, b))
            world.clock.hour = 12
            world.clock.minute = 0
            self.system.tick(world)
            return [
                (e.event_type, e.description, e.related_entity)
                for e in sorted(a.memory.entries, key=lambda e: e.description)
            ]

        self.assertEqual(snapshot(), snapshot())

    def test_no_rng_consumption(self):
        world = social_world()
        a, b = world.npcs[0], world.npcs[1]
        _place(world, a, "farm", _work_action(world.config, a))
        _place(world, b, "farm", _work_action(world.config, b))
        before = world.rng.getstate()
        world.clock.hour = 12
        world.clock.minute = 0
        self.system.tick(world)
        self.assertEqual(world.rng.getstate(), before)


if __name__ == "__main__":
    unittest.main()