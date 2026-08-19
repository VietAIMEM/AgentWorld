import json
import unittest

from world_sim.npc.llm import (
    LLMError,
    LLMExecutor,
    StaticProvider,
    build_llm_context,
    deterministic_response,
    generate_npc_exchange,
    generate_player_reply,
    generate_thought,
    llm_config,
    record_conversation_completed,
)
from world_sim.tests.helpers import build_world, first_npc


def _cfg(**overrides):
    cfg = llm_config({"llm": {"enabled": True, "provider": "static", **overrides}})
    return cfg


class TestDeterministicFallback(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        self.npc = first_npc(self.world)
        self.partner = next((n for n in self.world.npcs if n.id != self.npc.id), None)

    def test_deterministic_response_is_valid(self):
        resp = deterministic_response(self.npc, self.world, topic="work", player=True)
        self.assertEqual(resp.source, "fallback")
        self.assertTrue(resp.dialogue)
        self.assertLessEqual(len(resp.dialogue), 300)
        self.assertIn(resp.emotion, ("content", "happy", "calm", "worried", "hungry", "tired", "lonely", "stressed"))
        self.assertIn(resp.topic, ("work", "place", "weather", "food", "market", "family", "greeting", "relationship", "recent_event", "shopping", "resting", "socializing", "farewell"))

    def test_deterministic_response_deterministic(self):
        a = deterministic_response(self.npc, self.world, topic="work", player=True)
        b = deterministic_response(self.npc, self.world, topic="work", player=True)
        self.assertEqual(a, b)

    def test_unknown_topic_maps_to_greeting(self):
        resp = deterministic_response(self.npc, self.world, topic="bogus", player=True)
        self.assertIn(resp.topic, ("greeting",))

    def test_no_rng_consumed(self):
        rng = self.world.rng.getstate()
        deterministic_response(self.npc, self.world, topic="work", player=True)
        self.assertEqual(self.world.rng.getstate(), rng)


class TestGeneratePlayerReply(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        self.npc = first_npc(self.world)

    def test_disabled_returns_none_none(self):
        cfg = llm_config({"llm": {"enabled": False}})
        resp, fut = generate_player_reply(self.npc, self.world, cfg, None, None, None, "work")
        self.assertIsNone(resp)
        self.assertIsNone(fut)

    def test_enabled_without_provider_returns_none_none(self):
        resp, fut = generate_player_reply(self.npc, self.world, _cfg(), None, None, None, "work")
        self.assertIsNone(resp)
        self.assertIsNone(fut)

    def test_sync_with_provider_returns_llm_override(self):
        resp, fut = generate_player_reply(
            self.npc, self.world, _cfg(), StaticProvider(), None, None, "work"
        )
        self.assertIsNone(fut)
        self.assertIsNotNone(resp)
        self.assertTrue(resp.llm)
        self.assertIn(resp.topic, ("work", "market", "greeting"))

    def test_async_with_provider(self):
        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            resp, fut = generate_player_reply(
                self.npc, self.world, _cfg(), prov, None, ex, "work"
            )
            self.assertIsNone(resp)
            self.assertIsNotNone(fut)
            out = fut.result(timeout=5)
            self.assertTrue(out.llm)
            self.assertTrue(out.dialogue)
        finally:
            ex.shutdown()

    def test_cache_hit_returns_immediately(self):
        cache = __import__("world_sim.npc.llm.llm_cache", fromlist=["LLMCache"]).LLMCache(enabled=True)
        prov = StaticProvider()
        resp, fut = generate_player_reply(
            self.npc, self.world, _cfg(), prov, cache, None, "work"
        )
        self.assertIsNotNone(resp)
        # identical request -> cache hit, still llm
        resp2, fut2 = generate_player_reply(
            self.npc, self.world, _cfg(), prov, cache, None, "work"
        )
        self.assertIsNotNone(resp2)
        self.assertTrue(resp2.llm)
        self.assertEqual(resp2, resp)

    def test_erroring_provider_falls_back(self):
        prov = StaticProvider(error=LLMError("boom"))
        resp, fut = generate_player_reply(
            self.npc, self.world, _cfg(), prov, None, None, "work"
        )
        self.assertIsNone(resp)
        self.assertIsNone(fut)

    def test_malformed_provider_falls_back(self):
        prov = StaticProvider(json_text="not json at all")
        resp, fut = generate_player_reply(
            self.npc, self.world, _cfg(), prov, None, None, "work"
        )
        self.assertIsNone(resp)
        self.assertIsNone(fut)


class TestGenerateThought(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        self.npc = first_npc(self.world)

    def test_disabled_returns_none(self):
        cfg = llm_config({"llm": {"enabled": False}})
        text, fut = generate_thought(self.npc, self.world, cfg, None, None, None)
        self.assertIsNone(text)
        self.assertIsNone(fut)

    def test_enabled_without_provider_returns_deterministic(self):
        text, fut = generate_thought(self.npc, self.world, _cfg(), None, None, None)
        self.assertIsNone(fut)
        self.assertIsInstance(text, str)
        self.assertTrue(text)

    def test_sync_with_provider_returns_llm_text(self):
        prov = StaticProvider()
        text, fut = generate_thought(self.npc, self.world, _cfg(), prov, None, None)
        self.assertIsNone(fut)
        self.assertIsInstance(text, str)
        self.assertTrue(text)

    def test_async_with_provider(self):
        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            text, fut = generate_thought(self.npc, self.world, _cfg(), prov, None, ex)
            self.assertIsNone(text)
            out = fut.result(timeout=5)
            self.assertIsInstance(out, str)
            self.assertTrue(out)
        finally:
            ex.shutdown()

    def test_erroring_provider_returns_deterministic_thought(self):
        prov = StaticProvider(error=LLMError("boom"))
        text, fut = generate_thought(self.npc, self.world, _cfg(), prov, None, None)
        self.assertIsInstance(text, str)
        self.assertTrue(text)


class TestGenerateNpcExchange(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        self.npc = first_npc(self.world)
        self.partner = next((n for n in self.world.npcs if n.id != self.npc.id), None)
        if self.partner is None:
            self.skipTest("no partner npc")

    def test_disabled_produces_deterministic_entries(self):
        cfg = llm_config({"llm": {"enabled": False}})
        entries = generate_npc_exchange(self.npc, self.partner, self.world, "weather", cfg, None, None)
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertEqual(e["source"], "fallback")
            self.assertTrue(e["dialogue"])
            self.assertEqual(e["speaker_id"], self.npc.id if e["speaker_name"] == self.npc.name else self.partner.id)

    def test_provider_produces_llm_entries(self):
        entries = generate_npc_exchange(
            self.npc, self.partner, self.world, "weather", _cfg(), StaticProvider(), None
        )
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertEqual(e["source"], "llm")
            self.assertTrue(e["dialogue"])
            self.assertIn(e["emotion"], ("content", "happy", "calm", "worried", "hungry", "tired", "lonely", "stressed"))

    def test_erroring_provider_falls_back_per_speaker(self):
        entries = generate_npc_exchange(
            self.npc, self.partner, self.world, "weather", _cfg(), StaticProvider(error=LLMError("x")), None
        )
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertEqual(e["source"], "fallback")


class TestRecordConversation(unittest.TestCase):
    def test_records_memory_for_alive_npc(self):
        world = build_world(seed=1)
        npc = first_npc(world)
        record_conversation_completed(npc, world, "the traveler", topic="work")
        self.assertTrue(any(e.event_type == "talked_with_npc" for e in npc.memory.entries))

    def test_no_op_for_dead_npc(self):
        world = build_world(seed=1)
        npc = first_npc(world)
        npc.alive = False
        record_conversation_completed(npc, world, "the traveler", topic="work")
        self.assertEqual(len(npc.memory.entries), 0)


if __name__ == "__main__":
    unittest.main()