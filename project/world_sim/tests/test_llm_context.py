import json
import unittest

from world_sim.npc.llm import build_llm_context, llm_config
from world_sim.tests.helpers import build_world, first_npc

KNOWN_KEYS = {"npc", "location", "time", "relationship", "memories", "conversation", "player"}


class TestLLMContext(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)
        self.npc = first_npc(self.world)
        partner = next((n for n in self.world.npcs if n.id != self.npc.id), None)
        self.partner = partner
        self.ctx = build_llm_context(self.npc, self.world, topic="work", player=True)

    def test_top_level_keys(self):
        self.assertEqual(set(self.ctx.keys()), KNOWN_KEYS)

    def test_npc_block(self):
        npc = self.ctx["npc"]
        for key in ("id", "name", "age", "job", "personality", "emotion",
                    "needs", "goal", "action", "intent"):
            self.assertIn(key, npc)
        self.assertEqual(npc["id"], self.npc.id)
        self.assertEqual(npc["name"], self.npc.name)
        for trait in ("sociability", "ambition", "risk_tolerance", "work_ethic", "generosity"):
            self.assertIn(trait, npc["personality"])

    def test_location_and_time(self):
        loc = self.world.get_location(self.npc.location_id)
        if loc is not None:
            self.assertEqual(self.ctx["location"]["name"], loc.name)
        self.assertEqual(self.ctx["time"]["tick"], self.world.clock.tick)
        self.assertEqual(self.ctx["time"]["day"], self.world.clock.day)
        self.assertEqual(self.ctx["time"]["stamp"], self.world.clock.stamp())

    def test_player_conversation_block(self):
        conv = self.ctx["conversation"]
        self.assertEqual(conv["topic"], "work")
        self.assertEqual(conv["partner"], "the traveler")
        self.assertTrue(self.ctx["player"]["present"])

    def test_partner_relationship(self):
        if self.partner is None:
            self.skipTest("no partner npc")
        ctx = build_llm_context(self.npc, self.world, partner=self.partner, topic="weather", player=False)
        rel = ctx["relationship"]
        self.assertEqual(rel["npc_id"], self.partner.id)
        self.assertEqual(rel["name"], self.partner.name)
        self.assertIsInstance(rel["value"], (int, float))
        self.assertEqual(ctx["conversation"]["partner"], self.partner.name)
        self.assertFalse(ctx["player"]["present"])

    def test_memories_bounded(self):
        self.npc.add_memory(self.world.clock.stamp(), "test_event", "a memorable thing", 1.0)
        ctx = build_llm_context(self.npc, self.world, max_memories=1)
        self.assertEqual(len(ctx["memories"]), 1)
        ctx2 = build_llm_context(self.npc, self.world, max_memories=8)
        self.assertLessEqual(len(ctx2["memories"]), 8)
        ctx0 = build_llm_context(self.npc, self.world, max_memories=0)
        self.assertEqual(ctx0["memories"], [])

    def test_context_is_jsonable_and_deterministic(self):
        a = json.dumps(self.ctx, sort_keys=True)
        b = json.dumps(build_llm_context(self.npc, self.world, topic="work", player=True), sort_keys=True)
        self.assertEqual(a, b)

    def test_context_consumes_no_rng(self):
        rng = self.world.rng.getstate()
        build_llm_context(self.npc, self.world, topic="work", player=True)
        self.assertEqual(self.world.rng.getstate(), rng)

    def test_llm_config_defaults_and_overrides(self):
        cfg = llm_config({})
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["temperature"], 0.7)
        self.assertEqual(cfg["max_context_memories"], 8)
        cfg2 = llm_config({"llm": {"enabled": True, "temperature": "0.5", "max_context_memories": 3}})
        self.assertTrue(cfg2["enabled"])
        self.assertEqual(cfg2["temperature"], 0.5)
        self.assertEqual(cfg2["max_context_memories"], 3)


if __name__ == "__main__":
    unittest.main()