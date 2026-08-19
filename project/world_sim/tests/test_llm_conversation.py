import unittest

from world_sim.npc.conversation import Conversation
from world_sim.npc.llm import (
    LLMConversationObserver,
    LLMDialogueStore,
    LLMError,
    LLMExecutor,
    LLMPlayerBridge,
    LLMThoughtWriter,
    StaticProvider,
    build_llm_layer,
    llm_config,
)
from world_sim.presentation.player import PlayerConversation
from world_sim.tests.helpers import build_world, first_npc


def _cfg(**overrides):
    return llm_config({"llm": {"enabled": True, "provider": "static", **overrides}})


class _Sim:
    def __init__(self, world):
        self.world = world


class TestPlayerBridge(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        self.npc = first_npc(self.world)
        self.conv = PlayerConversation(
            npc_id=self.npc.id, npc_name=self.npc.name, started_tick=self.world.clock.tick,
            last_category="working", last_text="deterministic line",
        )

    def test_no_provider_returns_none(self):
        bridge = LLMPlayerBridge(_cfg(), provider=None)
        self.assertIsNone(bridge.maybe_reply(self.npc, self.world, "work", self.conv))
        self.assertFalse(self.conv.llm)
        self.assertEqual(self.conv.last_text, "deterministic line")

    def test_sync_provider_overrides_and_updates_conv(self):
        bridge = LLMPlayerBridge(_cfg(), provider=StaticProvider())
        out = bridge.maybe_reply(self.npc, self.world, "work", self.conv)
        self.assertIsNotNone(out)
        self.assertTrue(out["llm"])
        self.assertTrue(self.conv.llm)
        self.assertEqual(self.conv.last_text, out["dialogue"])
        self.assertEqual(self.conv.llm_emotion, out["emotion"])
        self.assertTrue(self.conv.llm_topic)

    def test_async_provider_then_poll_applies(self):
        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            bridge = LLMPlayerBridge(_cfg(), provider=prov, executor=ex)
            out = bridge.maybe_reply(self.npc, self.world, "work", self.conv)
            self.assertIsNone(out)
            self.assertFalse(self.conv.llm)
            bridge.poll()
            self.assertTrue(self.conv.llm)
            self.assertTrue(self.conv.last_text)
            self.assertTrue(self.conv.llm_topic)
        finally:
            ex.shutdown()

    def test_async_does_not_double_submit(self):
        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            bridge = LLMPlayerBridge(_cfg(), provider=prov, executor=ex)
            bridge.maybe_reply(self.npc, self.world, "work", self.conv)
            n_pending = len(bridge._pending)
            bridge.maybe_reply(self.npc, self.world, "work", self.conv)
            self.assertEqual(len(bridge._pending), n_pending)
        finally:
            ex.shutdown()

    def test_cache_hit_returns_immediate_override(self):
        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            bridge = LLMPlayerBridge(_cfg(), provider=prov, executor=ex)
            self.assertIsNone(bridge.maybe_reply(self.npc, self.world, "work", self.conv))
            bridge.poll()
            self.assertTrue(self.conv.llm)
            conv2 = PlayerConversation(npc_id=self.npc.id, npc_name=self.npc.name, started_tick=0)
            out = bridge.maybe_reply(self.npc, self.world, "work", conv2)
            self.assertIsNotNone(out)
            self.assertTrue(out["llm"])
        finally:
            ex.shutdown()

    def test_farewell_records_memory_only_when_llm(self):
        prov = StaticProvider()
        bridge = LLMPlayerBridge(_cfg(), provider=prov)
        self.conv.llm = True
        self.conv.llm_topic = "work"
        bridge.maybe_reply(self.npc, self.world, "work", self.conv)
        bridge.on_farewell(self.npc, self.world, self.conv)
        self.assertTrue(any(e.event_type == "talked_with_npc" for e in self.npc.memory.entries))

    def test_farewell_skips_memory_when_deterministic(self):
        bridge = LLMPlayerBridge(_cfg(), provider=None)
        bridge.on_farewell(self.npc, self.world, self.conv)
        self.assertEqual(len(self.npc.memory.entries), 0)

    def test_erroring_provider_keeps_deterministic(self):
        bridge = LLMPlayerBridge(_cfg(), provider=StaticProvider(error=LLMError("boom")))
        out = bridge.maybe_reply(self.npc, self.world, "work", self.conv)
        self.assertIsNone(out)
        self.assertFalse(self.conv.llm)


class TestDialogueStore(unittest.TestCase):
    def test_bounded_and_recent(self):
        store = LLMDialogueStore(cap=3)
        for i in range(5):
            store.record({"tick": i, "dialogue": f"line {i}"})
        self.assertEqual(len(store), 3)
        recent = store.recent(2)
        self.assertEqual([r["tick"] for r in recent], [3, 4])
        self.assertEqual(store.recent(10)[0]["tick"], 2)

    def test_record_exchange(self):
        store = LLMDialogueStore()
        entries = [
            {"speaker_id": "a", "speaker_name": "A", "dialogue": "hi"},
            {"speaker_id": "b", "speaker_name": "B", "dialogue": "hey"},
        ]
        store.record_exchange("conv_1", 7, entries)
        self.assertEqual(len(store), 2)
        self.assertEqual(store.recent(1)[0]["conversation_id"], "conv_1")
        self.assertEqual(store.recent(1)[0]["tick"], 7)


class TestConversationObserver(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        npcs = [n for n in self.world.npcs if n.alive]
        self.a, self.b = npcs[0], npcs[1]
        conv = Conversation(
            id="conv_obs_1", initiator_id=self.a.id, responder_id=self.b.id,
            topic="weather", stage="exchange", turns_left=2, last_turn_tick=0,
        )
        self.world.conversations.append(conv)

    def test_observes_exchange_and_stores(self):
        observer = LLMConversationObserver(_cfg(), provider=StaticProvider(), store=LLMDialogueStore())
        sim = _Sim(self.world)
        observer.observe(sim)
        self.assertGreaterEqual(len(observer.store), 2)
        self.assertIn("weather", observer.store.recent(1)[0]["topic"])

    def test_ignores_non_exchange_stage(self):
        self.world.conversations[0].stage = "greeting"
        observer = LLMConversationObserver(_cfg(), provider=StaticProvider(), store=LLMDialogueStore())
        observer.observe(_Sim(self.world))
        self.assertEqual(len(observer.store), 0)

    def test_seen_key_not_reprocessed(self):
        observer = LLMConversationObserver(_cfg(), provider=StaticProvider(), store=LLMDialogueStore())
        sim = _Sim(self.world)
        observer.observe(sim)
        first = len(observer.store)
        observer.observe(sim)
        self.assertEqual(len(observer.store), first)

    def test_erroring_provider_falls_back_per_speaker(self):
        observer = LLMConversationObserver(
            _cfg(), provider=StaticProvider(error=LLMError("x")), store=LLMDialogueStore()
        )
        observer.observe(_Sim(self.world))
        self.assertEqual(len(observer.store), 2)
        for e in observer.store.recent(2):
            self.assertEqual(e["source"], "fallback")

    def test_async_observer_populates_store(self):
        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            observer = LLMConversationObserver(_cfg(), provider=prov, executor=ex, store=LLMDialogueStore())
            observer.observe(_Sim(self.world))
            self.assertGreaterEqual(len(observer.store), 2)
        finally:
            ex.shutdown()


class TestThoughtWriter(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        self.npc = first_npc(self.world)
        self.sim = _Sim(self.world)

    def test_writes_deterministic_thought_without_provider(self):
        writer = LLMThoughtWriter(_cfg(), provider=None, interval_ticks=1)
        writer.observe(self.sim)
        self.assertIsNotNone(self.npc.thought)
        self.assertTrue(self.npc.thought)

    def test_writes_llm_thought_with_provider(self):
        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            writer = LLMThoughtWriter(_cfg(), provider=prov, executor=ex, interval_ticks=1)
            writer.observe(self.sim)
            self.assertIsNone(self.npc.thought)
            writer.poll()
            self.assertIsNotNone(self.npc.thought)
            self.assertTrue(self.npc.thought)
        finally:
            ex.shutdown()

    def test_disabled_writer_never_writes(self):
        cfg = llm_config({"llm": {"enabled": False}})
        writer = LLMThoughtWriter(cfg, provider=None, interval_ticks=1)
        writer.observe(self.sim)
        self.assertIsNone(self.npc.thought)

    def test_throttle_respects_interval(self):
        writer = LLMThoughtWriter(_cfg(), provider=None, interval_ticks=1000)
        writer.observe(self.sim)
        self.assertIsNotNone(self.npc.thought)
        writer.observe(self.sim)
        self.assertEqual(self.npc.thought, self.npc.thought)


class TestLLMLayer(unittest.TestCase):
    def test_build_returns_none_when_disabled(self):
        self.assertIsNone(build_llm_layer({"behavior": {"llm": {"enabled": False}}}))

    def test_build_returns_layer_when_enabled(self):
        layer = build_llm_layer({"behavior": {"llm": {"enabled": True}}})
        self.assertIsNotNone(layer)
        layer.shutdown()
        layer.shutdown()

    def test_observe_and_poll_noop_without_provider(self):
        layer = build_llm_layer({"behavior": {"llm": {"enabled": True}}})
        try:
            world = build_world(seed=1)
            layer.observe(_Sim(world))
            layer.poll()
            self.assertIsNotNone(world.npcs[0].thought)
        finally:
            layer.shutdown()


if __name__ == "__main__":
    unittest.main()