import json
import random
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.actions.movement import MoveAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.conversation import (
    TOPIC_POOL,
    Conversation,
    ConversationSystem,
    threshold_ok,
)
from world_sim.npc.goals import Goal, GoalType
from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
from world_sim.tests.helpers import build_world, load_configs


def conversation_configs(behavior_enabled=True, conversations_enabled=True, **overrides):
    wc, nc = load_configs()
    conv = {
        "enabled": conversations_enabled,
        "max_turns": 4,
        "initiation_threshold": 0.5,
        "acceptance_threshold": 0.5,
        "social_restore": 0,
        "relationship_delta": 0,
    }
    conv.update(overrides)
    wc["behavior"] = {"enabled": behavior_enabled, "conversations": conv}
    return wc, nc


def conversation_world(seed=1, **overrides):
    wc, nc = conversation_configs(**overrides)
    return World(wc, nc, random.Random(seed), run_days=30, seed=seed)


def pair(world):
    a, b = world.npcs[0], world.npcs[1]
    a.location_id = "market"
    b.location_id = "market"
    a.current_action = None
    b.current_action = None
    return a, b


def _init_key(a, b, day, hour):
    return f"init|{a.id}|{b.id}|{day}|{hour}"


def _accept_key(a, b, day, hour):
    return f"accept|{b.id}|{a.id}|{day}|{hour}"


def _hour_ok(a, b, day, hour):
    return threshold_ok(_init_key(a, b, day, hour), 0.5) and threshold_ok(
        _accept_key(a, b, day, hour), 0.5
    )


def _find_hour(world, a, b, want_accept=True):
    for day in range(1, 8):
        for hour in range(24):
            if _hour_ok(a, b, day, hour) == want_accept:
                world.clock.day = day
                world.clock.hour = hour
                return day, hour
    raise AssertionError("no suitable deterministic hour found")


def start_conv(world, a, b):
    _find_hour(world, a, b, want_accept=True)
    conv = world.start_conversation(a, b.id)
    assert conv is not None, "conversation failed to start at found hour"
    return conv


def advance(world, system, steps=1):
    for _ in range(steps):
        world.clock.tick += 1
        system.tick(world)


class TestConversationDataModel(unittest.TestCase):
    def test_conversation_creation(self):
        conv = Conversation(
            id="conv_1_a_b",
            initiator_id="a",
            responder_id="b",
            turns_left=4,
            started_tick=10,
            last_turn_tick=10,
        )
        self.assertEqual(conv.id, "conv_1_a_b")
        self.assertEqual(conv.initiator_id, "a")
        self.assertEqual(conv.responder_id, "b")
        self.assertIsNone(conv.topic)
        self.assertEqual(conv.stage, "greeting")
        self.assertEqual(conv.turns_left, 4)
        self.assertEqual(conv.started_tick, 10)
        self.assertEqual(conv.last_turn_tick, 10)
        self.assertEqual(conv.open_slots, 2)

    def test_deterministic_ids(self):
        world_a = conversation_world(seed=1)
        world_b = conversation_world(seed=2)
        a1, b1 = pair(world_a)
        a2, b2 = pair(world_b)
        c1 = start_conv(world_a, a1, b1)
        c2 = start_conv(world_b, a2, b2)
        self.assertEqual(c1.id, c2.id)


class TestInitiationAndAcceptance(unittest.TestCase):
    def test_initiation_succeeds(self):
        world = conversation_world()
        a, b = pair(world)
        conv = start_conv(world, a, b)
        self.assertIn(conv, world.conversations)
        self.assertEqual(a.conversation_id, conv.id)
        self.assertEqual(b.conversation_id, conv.id)
        self.assertEqual(a.facing, b.id)
        self.assertEqual(b.facing, a.id)
        self.assertEqual(a.intent.kind, "conversing")
        self.assertEqual(a.intent.target_npc_id, b.id)
        self.assertEqual(b.intent.kind, "conversing")
        self.assertEqual(conv.stage, "greeting")
        self.assertEqual(conv.turns_left, 4)

    def test_acceptance_requires_idle_or_socializing(self):
        world = conversation_world()
        a, b = pair(world)
        b.current_action = MoveAction(
            random.Random(1),
            world.config,
            Decision(goal=Goal(GoalType.REST, 10.0), action_type="move", target_location_id="tavern"),
        )
        _find_hour(world, a, b, want_accept=True)
        self.assertIsNone(world.start_conversation(a, b.id))
        self.assertEqual(world.conversations, [])

    def test_rejection_when_deterministic_check_fails(self):
        world = conversation_world()
        a, b = pair(world)
        _find_hour(world, a, b, want_accept=False)
        self.assertIsNone(world.start_conversation(a, b.id))
        self.assertEqual(world.conversations, [])
        self.assertIsNone(a.conversation_id)
        self.assertIsNone(b.conversation_id)

    def test_requires_same_location(self):
        world = conversation_world()
        a, b = pair(world)
        b.location_id = "tavern"
        _find_hour(world, a, b, want_accept=True)
        self.assertIsNone(world.start_conversation(a, b.id))

    def test_dead_partner_rejected(self):
        world = conversation_world()
        a, b = pair(world)
        b.alive = False
        _find_hour(world, a, b, want_accept=True)
        self.assertIsNone(world.start_conversation(a, b.id))

    def test_one_conversation_per_npc(self):
        world = conversation_world()
        a, b = pair(world)
        c = world.npcs[2]
        c.location_id = "market"
        c.current_action = None
        start_conv(world, a, b)
        _find_hour(world, a, c, want_accept=True)
        self.assertIsNone(world.start_conversation(a, c.id))
        self.assertEqual(len(world.conversations), 1)

    def test_lower_id_wins(self):
        world = conversation_world()
        a, b = pair(world)
        start_conv(world, a, b)
        _find_hour(world, b, a, want_accept=True)
        self.assertIsNone(world.start_conversation(b, a.id))
        self.assertEqual(len(world.conversations), 1)
        self.assertEqual(world.conversations[0].initiator_id, a.id)


class TestConversationLifecycle(unittest.TestCase):
    def setUp(self):
        self.world = conversation_world()
        self.a, self.b = pair(self.world)
        self.conv = start_conv(self.world, self.a, self.b)
        self.system = ConversationSystem(self.world.config)

    def test_greeting_stage(self):
        self.assertEqual(self.conv.stage, "greeting")
        self.assertIsNone(self.conv.topic)

    def test_exchange_stage(self):
        advance(self.world, self.system)
        self.assertEqual(self.conv.stage, "exchange")
        self.assertIn(self.conv.topic, TOPIC_POOL)

    def test_turns_left_progression(self):
        advance(self.world, self.system)
        self.assertEqual(self.conv.turns_left, 4)
        advance(self.world, self.system)
        self.assertEqual(self.conv.turns_left, 3)
        advance(self.world, self.system)
        self.assertEqual(self.conv.turns_left, 2)

    def test_farewell_stage_and_completion(self):
        advance(self.world, self.system, steps=5)
        self.assertEqual(self.conv.stage, "farewell")
        self.assertIn(self.conv, self.world.conversations)
        advance(self.world, self.system)
        self.assertNotIn(self.conv, self.world.conversations)
        self.assertIsNone(self.a.conversation_id)
        self.assertIsNone(self.b.conversation_id)

    def test_maximum_lifetime(self):
        self.conv.started_tick = self.world.clock.tick - (self.system.max_turns + 3)
        self.conv.last_turn_tick = self.conv.started_tick
        advance(self.world, self.system)
        self.assertNotIn(self.conv, self.world.conversations)
        self.assertIsNone(self.a.conversation_id)
        self.assertIsNone(self.b.conversation_id)


class TestTopics(unittest.TestCase):
    def setUp(self):
        self.world = conversation_world()
        self.a, self.b = pair(self.world)
        self.conv = start_conv(self.world, self.a, self.b)
        self.system = ConversationSystem(self.world.config)

    def test_deterministic_topic_selection(self):
        first = self.system._select_topic(self.conv, self.world)
        second = self.system._select_topic(self.conv, self.world)
        self.assertEqual(first, second)
        self.assertIn(first, TOPIC_POOL)

    def test_memory_informed_topics(self):
        self.a.add_memory("t", "family", "family memory", 3.0)
        self.assertIn("family", self.system._candidate_topics(self.conv, self.world))
        self.b.add_memory("t", "recent_event", "festival memory", 3.0)
        self.assertIn("recent_event", self.system._candidate_topics(self.conv, self.world))

    def test_relationship_topic_threshold(self):
        self.assertNotIn("relationship", self.system._candidate_topics(self.conv, self.world))
        self.a.relationships[self.b.id] = 1
        self.assertIn("relationship", self.system._candidate_topics(self.conv, self.world))

    def test_recent_event_topic(self):
        self.assertNotIn("recent_event", self.system._candidate_topics(self.conv, self.world))
        self.a.add_memory("t", "rain", "rained yesterday", 3.0)
        self.assertIn("recent_event", self.system._candidate_topics(self.conv, self.world))


class TestConversationEffects(unittest.TestCase):
    def setUp(self):
        self.world = conversation_world()
        self.a, self.b = pair(self.world)
        self.a.needs.social = 40.0
        self.b.needs.social = 40.0
        self.a.personality.sociability = 1.0
        self.b.personality.sociability = 1.0
        self.a.personality.generosity = 1.0
        self.b.personality.generosity = 1.0
        self.conv = start_conv(self.world, self.a, self.b)
        self.system = ConversationSystem(self.world.config)

    def complete(self):
        advance(self.world, self.system, steps=7)

    def test_memory_creation(self):
        self.complete()
        self.assertEqual(len(self.a.memory.recent("met_npc")), 1)
        self.assertEqual(len(self.a.memory.recent("conversation")), 1)
        self.assertEqual(len(self.b.memory.recent("met_npc")), 1)
        self.assertEqual(len(self.b.memory.recent("conversation")), 1)

    def test_social_restore_exactly_once(self):
        self.complete()
        self.assertAlmostEqual(self.a.needs.social, 55.0)
        self.assertAlmostEqual(self.b.needs.social, 47.5)
        for _ in range(10):
            self.world.clock.tick += 1
            self.system.tick(self.world)
        self.assertAlmostEqual(self.a.needs.social, 55.0)
        self.assertAlmostEqual(self.b.needs.social, 47.5)

    def test_relationship_update_exactly_once(self):
        self.complete()
        self.assertEqual(self.a.relationships.get(self.b.id, 0), 1)
        self.assertEqual(self.b.relationships.get(self.a.id, 0), 1)

    def test_responder_half_reward(self):
        self.complete()
        self.assertAlmostEqual(self.a.needs.social - 40.0, 15.0)
        self.assertAlmostEqual(self.b.needs.social - 40.0, 7.5)

    def test_low_compatibility_relationship_delta(self):
        self.a.personality.sociability = 0.0
        self.b.personality.sociability = 0.0
        self.a.personality.generosity = 0.0
        self.b.personality.generosity = 0.0
        self.complete()
        self.assertEqual(self.a.relationships.get(self.b.id, 0), 0)
        self.assertEqual(self.b.relationships.get(self.a.id, 0), 0)

    def _socialize_action(self, npc, partner_id):
        from world_sim.actions.social import SocializeAction

        decision = Decision(
            goal=Goal(GoalType.SOCIALIZE, 10.0, npc.location_id),
            action_type="socialize",
            priority=10.0,
            target_npc_id=partner_id,
        )
        return SocializeAction(random.Random(1), self.world.config, decision)

    def test_failed_initiation_falls_back_to_legacy_socialize(self):
        self.world.end_conversation(self.conv)
        _find_hour(self.world, self.a, self.b, want_accept=False)
        self.assertIsNone(self.world.start_conversation(self.a, self.b.id))
        self.assertIsNone(self.a.conversation_id)
        action = self._socialize_action(self.a, self.b.id)
        action.start(self.a, self.world)
        action.tick(self.a, self.world)
        action.tick(self.a, self.world)
        self.assertAlmostEqual(self.a.needs.social, 55.0)
        self.assertAlmostEqual(self.b.needs.social, 47.5)
        self.assertEqual(self.a.relationships.get(self.b.id, 0), 1)
        self.assertEqual(len(self.a.memory.recent("met_npc")), 1)

    def test_active_conversation_skips_legacy_socialize(self):
        self.a.needs.social = 40.0
        action = self._socialize_action(self.a, self.b.id)
        action.start(self.a, self.world)
        action.tick(self.a, self.world)
        action.tick(self.a, self.world)
        self.assertAlmostEqual(self.a.needs.social, 40.0)
        self.assertAlmostEqual(self.b.needs.social, 40.0)
        self.assertIn(self.conv, self.world.conversations)
        self.assertIsNotNone(self.a.intent)
        self.complete()
        self.assertAlmostEqual(self.a.needs.social, 55.0)


class TestConversationState(unittest.TestCase):
    def setUp(self):
        self.world = conversation_world()
        self.a, self.b = pair(self.world)
        self.conv = start_conv(self.world, self.a, self.b)
        self.system = ConversationSystem(self.world.config)

    def test_npc_facing(self):
        self.assertEqual(self.a.facing, self.b.id)
        self.assertEqual(self.b.facing, self.a.id)
        advance(self.world, self.system, steps=7)
        self.assertIsNone(self.a.facing)
        self.assertIsNone(self.b.facing)

    def test_intent_assignment(self):
        self.assertEqual(self.a.intent.kind, "conversing")
        self.assertEqual(self.b.intent.kind, "conversing")
        self.assertEqual(self.a.intent.target_npc_id, self.b.id)

    def test_intent_clearing(self):
        advance(self.world, self.system, steps=7)
        self.assertIsNone(self.a.intent)
        self.assertIsNone(self.b.intent)

    def test_participant_leaves(self):
        self.b.location_id = "tavern"
        advance(self.world, self.system)
        self.assertNotIn(self.conv, self.world.conversations)
        self.assertIsNone(self.a.conversation_id)
        self.assertIsNone(self.b.conversation_id)
        self.assertIsNone(self.a.facing)
        self.assertIsNone(self.a.intent)

    def test_participant_dies(self):
        self.world.npc_die(self.b)
        self.assertNotIn(self.conv, self.world.conversations)
        self.assertIsNone(self.a.conversation_id)
        self.assertIsNone(self.b.conversation_id)
        self.assertIsNone(self.a.facing)

    def test_day_rollover_cleanup(self):
        self.conv.started_day = self.world.clock.day - 1
        advance(self.world, self.system)
        self.assertNotIn(self.conv, self.world.conversations)
        self.assertIsNone(self.a.conversation_id)
        self.assertIsNone(self.b.conversation_id)

    def test_stale_conversation_cleanup(self):
        self.a.conversation_id = None
        advance(self.world, self.system)
        self.assertNotIn(self.conv, self.world.conversations)
        self.assertIsNone(self.b.conversation_id)


class TestRngAndDeterminism(unittest.TestCase):
    def test_no_rng_consumption(self):
        world = conversation_world()
        a, b = pair(world)
        _find_hour(world, a, b, want_accept=True)
        system = ConversationSystem(world.config)
        before = world.rng.getstate()
        conv = world.start_conversation(a, b.id)
        self.assertIsNotNone(conv)
        advance(world, system, steps=8)
        after = world.rng.getstate()
        self.assertEqual(before, after)

    def test_same_seed_determinism(self):
        def snapshot():
            wc, nc = conversation_configs()
            gen = dict(wc["world_generation"])
            gen["enabled"] = True
            gen["seed"] = 42
            wc["world_generation"] = gen
            sim = Simulation(wc, nc, seed=42, days=30, print_report=False)
            sim.run()
            self.assertGreater(sim.world.stats.social_interactions, 0)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "s.json"
                save_state(sim, path)
                return path.read_bytes()

        self.assertEqual(snapshot(), snapshot())

    def test_pairs_do_not_collide(self):
        world = conversation_world()
        a, b = pair(world)
        c, d = world.npcs[2], world.npcs[3]
        c.location_id = "tavern"
        d.location_id = "tavern"
        c.current_action = None
        d.current_action = None
        conv1 = start_conv(world, a, b)
        _find_hour(world, c, d, want_accept=True)
        conv2 = world.start_conversation(c, d.id)
        self.assertIsNotNone(conv2)
        self.assertEqual(len(world.conversations), 2)
        self.assertNotEqual(conv1.id, conv2.id)
        participants1 = {conv1.initiator_id, conv1.responder_id}
        participants2 = {conv2.initiator_id, conv2.responder_id}
        self.assertTrue(participants1.isdisjoint(participants2))

    def test_acceptance_consumes_no_rng(self):
        world = conversation_world()
        a, b = pair(world)
        _find_hour(world, a, b, want_accept=True)
        before = world.rng.getstate()
        conv = world.start_conversation(a, b.id)
        self.assertIsNotNone(conv)
        after = world.rng.getstate()
        self.assertEqual(before, after)


class TestPersistence(unittest.TestCase):
    def test_persistence_roundtrip(self):
        wc, nc = conversation_configs()
        sim = Simulation(wc, nc, seed=1, days=5, print_report=False)
        world = sim.world
        a, b = pair(world)
        conv = start_conv(world, a, b)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("conversations", data)
            self.assertEqual(data["conversations"][0]["id"], conv.id)
            loaded = load_state(path, wc, nc)
        self.assertEqual(len(loaded.world.conversations), 1)
        lconv = loaded.world.conversations[0]
        for field in (
            "id",
            "initiator_id",
            "responder_id",
            "topic",
            "stage",
            "turns_left",
            "started_tick",
            "last_turn_tick",
            "open_slots",
        ):
            self.assertEqual(getattr(lconv, field), getattr(conv, field))
        la = loaded.world.get_npc(a.id)
        lb = loaded.world.get_npc(b.id)
        self.assertEqual(la.conversation_id, conv.id)
        self.assertEqual(lb.conversation_id, conv.id)

    def test_old_save_compatibility(self):
        wc, nc = conversation_configs()
        sim = Simulation(wc, nc, seed=1, days=5, print_report=False)
        world = sim.world
        a, b = pair(world)
        start_conv(world, a, b)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("conversations", None)
            for npc_data in data["npcs"]:
                npc_data.pop("conversation_id", None)
                npc_data.pop("facing", None)
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = load_state(path, wc, nc)
        self.assertEqual(loaded.world.conversations, [])
        for npc in loaded.world.npcs:
            self.assertIsNone(npc.conversation_id)
            self.assertIsNone(npc.facing)

    def test_90d_save_load_invariant(self):
        for seed in (42, 99):
            wc, nc = conversation_configs()
            gen = dict(wc["world_generation"])
            gen["enabled"] = True
            gen["seed"] = seed
            wc["world_generation"] = gen
            sim_a = Simulation(wc, nc, seed=seed, days=90, print_report=False)
            sim_a.run()
            with tempfile.TemporaryDirectory() as tmp:
                path_a = Path(tmp) / "a.json"
                save_state(sim_a, path_a)
                sim_b = Simulation(wc, nc, seed=seed, days=90, print_report=False)
                sim_b.run(days=45)
                path_b = Path(tmp) / "b.json"
                save_state(sim_b, path_b)
                loaded = load_state(path_b, wc, nc, continue_days=45)
                loaded.run()
                path_c = Path(tmp) / "c.json"
                save_state(loaded, path_c)
                self.assertEqual(path_a.read_bytes(), path_c.read_bytes())
                rng_a = [sim_a.rng.random() for _ in range(100)]
                rng_b = [loaded.rng.random() for _ in range(100)]
                self.assertEqual(rng_a, rng_b)


if __name__ == "__main__":
    unittest.main()