import unittest

from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.goals import GoalType
from world_sim.npc.perception import PerceptionSystem
from world_sim.tests.helpers import build_world, load_configs


def social_configs(enabled=True):
    wc, nc = load_configs()
    wc["behavior"] = {
        "enabled": True,
        "routines": {"enabled": True, "default_bias": 0.5},
        "objects": {"enabled": True},
        "interactions": True,
        "conversations": {"enabled": True, "max_turns": 4},
        "social_life": {"enabled": enabled},
    }
    return wc, nc


def social_world(seed=1, enabled=True):
    wc, nc = social_configs(enabled=enabled)
    return build_world(seed, wc, nc)


def _place_together(world, npc_ids, location_id):
    placed = []
    for npc_id in npc_ids:
        npc = world.get_npc(npc_id)
        npc.location_id = location_id
        npc.current_action = None
        placed.append(npc)
    return placed


def _socialize_state(world, npc):
    npc.needs.social = 10.0
    npc.needs.hunger = 30.0
    npc.needs.energy = 90.0
    npc.money = 50.0
    world.clock.hour = 18


def _decide(world, npc):
    ds = RuleBasedDecisionSystem(world.config, world.rng)
    perception = PerceptionSystem().perceive(npc, world)
    return ds.decide(npc, perception, world)


class TestFriendBasedTargeting(unittest.TestCase):
    def test_friend_preferred_over_stranger_at_social_location(self):
        world = social_world()
        npc, friend, stranger = world.npcs[0], world.npcs[1], world.npcs[2]
        _place_together(world, [npc.id, friend.id, stranger.id], "market")
        npc.relationships[friend.id] = 30
        _socialize_state(world, npc)
        decision = _decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "socialize")
        self.assertEqual(decision.target_npc_id, friend.id)

    def test_close_friend_preferred_over_friend(self):
        world = social_world()
        npc, close, friend = world.npcs[0], world.npcs[1], world.npcs[2]
        _place_together(world, [npc.id, close.id, friend.id], "market")
        npc.relationships[close.id] = 70
        npc.relationships[friend.id] = 30
        _socialize_state(world, npc)
        decision = _decide(world, npc)
        self.assertEqual(decision.target_npc_id, close.id)

    def test_tie_broken_by_lowest_id(self):
        world = social_world()
        npc = world.npcs[0]
        _place_together(world, [npc.id] + [other.id for other in world.npcs[1:4]], "market")
        _socialize_state(world, npc)
        decision = _decide(world, npc)
        nearby = sorted(other.id for other in world.npcs[1:4])
        self.assertEqual(decision.target_npc_id, nearby[0])

    def test_deterministic_same_state(self):
        world = social_world()
        npc, friend = world.npcs[0], world.npcs[1]
        _place_together(world, [npc.id, friend.id], "market")
        npc.relationships[friend.id] = 30
        _socialize_state(world, npc)
        a = _decide(world, npc)
        b = _decide(world, npc)
        self.assertEqual(a.target_npc_id, b.target_npc_id)

    def test_no_new_rng_draws_when_enabled(self):
        world = social_world()
        npc, friend = world.npcs[0], world.npcs[1]
        _place_together(world, [npc.id, friend.id], "market")
        npc.relationships[friend.id] = 30
        _socialize_state(world, npc)
        before = world.rng.getstate()
        decision = _decide(world, npc)
        after = world.rng.getstate()
        self.assertEqual(decision.target_npc_id, friend.id)
        self.assertEqual(before, after)


class TestDisabledParity(unittest.TestCase):
    def test_disabled_mode_consumes_choice_draw(self):
        world = social_world(enabled=False)
        npc, friend = world.npcs[0], world.npcs[1]
        _place_together(world, [npc.id, friend.id], "market")
        npc.relationships[friend.id] = 30
        _socialize_state(world, npc)
        before = world.rng.getstate()
        _decide(world, npc)
        after = world.rng.getstate()
        self.assertNotEqual(before, after)

    def test_disabled_target_does_not_use_friendship(self):
        world = social_world(enabled=False)
        npc, stranger = world.npcs[0], world.npcs[1]
        npc2, stranger2 = world.npcs[2], world.npcs[3]
        _place_together(world, [npc.id, stranger.id, npc2.id, stranger2.id], "market")
        npc.relationships[stranger.id] = 30
        npc2.relationships[stranger2.id] = -70
        _socialize_state(world, npc)
        _socialize_state(world, npc2)
        d1 = _decide(world, npc)
        d2 = _decide(world, npc2)
        self.assertEqual(d1.action_type, "socialize")
        self.assertEqual(d2.action_type, "socialize")
        nearby_ids = {other.id for other in world.npcs if other.location_id == "market"} - {npc2.id}
        self.assertIn(d2.target_npc_id, nearby_ids)


class TestSocialTone(unittest.TestCase):
    def test_warm_tone_for_close_friend(self):
        from world_sim.presentation.animation import animate

        world = social_world()
        npc, close = world.npcs[0], world.npcs[1]
        _place_together(world, [npc.id, close.id], "market")
        npc.relationships[close.id] = 70
        world.clock.hour = 18
        from world_sim.npc.conversation import threshold_ok

        found = False
        for hour in range(24):
            world.clock.hour = hour
            if threshold_ok(f"init|{npc.id}|{close.id}|{world.clock.day}|{hour}", 0.5) and threshold_ok(
                f"accept|{close.id}|{npc.id}|{world.clock.day}|{hour}", 0.5
            ):
                found = True
                break
        self.assertTrue(found)
        world.clock.hour = world.clock.hour
        conv = world.start_conversation(npc, close.id)
        self.assertIsNotNone(conv)
        state = animate(npc, world)
        self.assertEqual(state.tone, "warm")

    def test_neutral_tone_when_disabled(self):
        from world_sim.presentation.animation import animate

        world = social_world(enabled=False)
        npc, other = world.npcs[0], world.npcs[1]
        _place_together(world, [npc.id, other.id], "market")
        npc.relationships[other.id] = 70
        for hour in range(24):
            world.clock.hour = hour
            conv = world.start_conversation(npc, other.id)
            if conv is not None:
                break
        state = animate(npc, world)
        self.assertEqual(state.tone, "neutral")


if __name__ == "__main__":
    unittest.main()