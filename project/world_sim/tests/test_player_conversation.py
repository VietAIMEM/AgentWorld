import unittest

from world_sim.presentation.player import (
    PlayerConversation,
    PlayerSession,
    response_for,
)
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import load_configs

VALID_CATEGORIES = {
    "greeting", "working", "eating", "shopping", "resting",
    "socializing", "busy", "farewell", "location",
}


def feature_configs(gen_seed=42):
    wc, nc = load_configs()
    gen = dict(wc["world_generation"])
    gen["enabled"] = True
    gen["seed"] = gen_seed
    wc["world_generation"] = gen
    se = dict(wc["settlement_economy"])
    se["enabled"] = True
    wc["settlement_economy"] = se
    wc["behavior"] = {
        "enabled": True,
        "routines": {"enabled": True, "default_bias": 0.5},
        "objects": {"enabled": True},
        "interactions": True,
        "conversations": {"enabled": True, "max_turns": 4},
    }
    return wc, nc


def _alive_npc(sim):
    for npc in sim.world.npcs:
        if npc.alive:
            return npc
    raise AssertionError("no alive npc found")


class TestPlayerConversation(unittest.TestCase):
    def setUp(self):
        wc, nc = feature_configs(gen_seed=42)
        self.sim = Simulation(wc, nc, seed=7, days=30, print_report=False)
        self.sim.run(days=2)
        self.session = PlayerSession()
        self.npc = _alive_npc(self.sim)

    def _talk(self, option=None):
        body = {"type": "player_talk", "target_id": self.npc.id}
        if option is not None:
            body["option"] = option
        return self.session.handle_command(self.sim, body)

    def test_responses_are_deterministic(self):
        a = response_for(self.npc, self.sim.world, "work")
        b = response_for(self.npc, self.sim.world, "work")
        self.assertEqual(a, b)
        self.assertEqual(self.npc.conversation_id, None)

    def test_response_category_always_valid(self):
        for option in (None, "work", "place", "farewell"):
            category, text = response_for(self.npc, self.sim.world, option)
            self.assertIn(category, VALID_CATEGORIES)
            self.assertTrue(text)

    def test_option_produces_distinct_categories(self):
        work = response_for(self.npc, self.sim.world, "work")[0]
        place = response_for(self.npc, self.sim.world, "place")[0]
        farewell = response_for(self.npc, self.sim.world, "farewell")[0]
        self.assertEqual(work, "working")
        self.assertEqual(place, "location")
        self.assertEqual(farewell, "farewell")

    def test_dead_npc_always_farewell(self):
        self.npc.alive = False
        category, _ = response_for(self.npc, self.sim.world, None)
        self.assertEqual(category, "farewell")

    def test_start_conversation_activates(self):
        result = self._talk()
        self.assertTrue(result["ok"])
        self.assertTrue(result["conversation"]["active"])
        self.assertEqual(result["conversation"]["npc_id"], self.npc.id)
        self.assertEqual(len(result["conversation"]["options"]), 3)

    def test_farewell_closes_conversation(self):
        self._talk()
        result = self._talk(option="farewell")
        self.assertTrue(result["ok"])
        self.assertFalse(result["conversation"]["active"])
        self.assertIsNone(self.session.conversation)

    def test_farewell_has_no_options(self):
        result = self._talk(option="farewell")
        self.assertEqual(result["conversation"]["options"], [])

    def test_session_tracks_conversation(self):
        self._talk(option="work")
        conv = self.session.conversation
        self.assertIsInstance(conv, PlayerConversation)
        self.assertEqual(conv.npc_id, self.npc.id)
        self.assertTrue(conv.last_text)

    def test_switching_npc_resets_conversation(self):
        self._talk(option="work")
        other = None
        for npc in self.sim.world.npcs:
            if npc.alive and npc.id != self.npc.id:
                other = npc
                break
        if other is None:
            self.skipTest("only one alive npc")
        result = self.session.handle_command(
            self.sim, {"type": "player_talk", "target_id": other.id, "option": "place"}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(self.session.conversation.npc_id, other.id)
        self.assertEqual(self.session.conversation.last_category, "location")

    def test_dead_npc_clears_stale_conversation(self):
        self._talk(option="work")
        self.npc.alive = False
        self.session.expire_conversation(self.sim.world)
        self.assertIsNone(self.session.conversation)

    def test_conversation_uses_no_sim_rng(self):
        rng_before = self.sim.rng.getstate()
        self._talk(option="work")
        self._talk(option="place")
        self._talk(option="farewell")
        self.assertEqual(self.sim.rng.getstate(), rng_before)

    def test_conversation_never_touches_npc_conversation_system(self):
        self._talk(option="work")
        self._talk(option="place")
        self.assertIsNone(self.npc.conversation_id)
        self.assertEqual(len(self.sim.world.conversations), 0)


if __name__ == "__main__":
    unittest.main()