import unittest

from world_sim.npc.relationships import player_tier
from world_sim.presentation.player import PlayerSession
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import load_configs


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
        "social_life": {"enabled": True},
    }
    return wc, nc


def _alive_npc(sim):
    for npc in sim.world.npcs:
        if npc.alive:
            return npc
    raise AssertionError("no alive npc found")


class TestPlayerRelationship(unittest.TestCase):
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

    def test_relationships_start_empty(self):
        self.assertEqual(self.session.relationships, {})

    def test_greeting_increments_by_one(self):
        self._talk()
        self.assertEqual(self.session.relationships[self.npc.id], 1)

    def test_work_increments_by_two(self):
        self._talk(option="work")
        self.assertEqual(self.session.relationships[self.npc.id], 2)

    def test_place_increments_by_one(self):
        self._talk(option="place")
        self.assertEqual(self.session.relationships[self.npc.id], 1)

    def test_farewell_does_not_increment(self):
        self._talk(option="farewell")
        self.assertNotIn(self.npc.id, self.session.relationships)

    def test_accumulates_over_interactions(self):
        self._talk(option="work")
        self._talk(option="work")
        self._talk(option="place")
        self.assertEqual(self.session.relationships[self.npc.id], 5)

    def test_tier_progresses_stranger_to_friend(self):
        for _ in range(10):
            self._talk(option="work")
        value = self.session.relationships[self.npc.id]
        self.assertGreaterEqual(value, 20)
        self.assertEqual(player_tier(value), "friend")

    def test_tier_acquaintance_after_one_interaction(self):
        self._talk(option="work")
        self.assertEqual(player_tier(self.session.relationships[self.npc.id]), "acquaintance")

    def test_identical_command_is_deterministic(self):
        a = self._talk()
        b = self._talk()
        self.assertEqual(a, b)

    def test_no_sim_rng_consumed(self):
        rng_before = self.sim.rng.getstate()
        self._talk(option="work")
        self._talk(option="place")
        self._talk(option="farewell")
        self.assertEqual(self.sim.rng.getstate(), rng_before)

    def test_no_sim_state_mutated(self):
        before = (self.npc.money, self.npc.needs.hunger, self.npc.needs.energy, self.npc.location_id)
        self._talk(option="work")
        self._talk(option="place")
        after = (self.npc.money, self.npc.needs.hunger, self.npc.needs.energy, self.npc.location_id)
        self.assertEqual(after, before)
        self.assertIsNone(self.npc.conversation_id)

    def test_relationships_never_touch_npc(self):
        before = dict(self.npc.relationships)
        self._talk(option="work")
        self._talk(option="place")
        self.assertEqual(self.npc.relationships, before)

    def test_value_clamped_upper(self):
        for _ in range(200):
            self._talk(option="work")
        self.assertLessEqual(self.session.relationships[self.npc.id], 100)

    def test_payload_exposes_player_relationship(self):
        self.session.handle_command(self.sim, {"type": "player_inspect", "target_id": self.npc.id})
        self._talk(option="work")
        payload = self.session.build_interaction_payload(self.sim)
        pr = payload["target"]["player_relationship"]
        self.assertEqual(pr["value"], self.session.relationships[self.npc.id])
        self.assertEqual(pr["tier"], player_tier(pr["value"]))

    def test_tier_only_in_payload_not_talk_reply(self):
        first = self._talk()
        self.assertNotIn("tier", first["conversation"])
        self.assertNotIn("player_relationship", first["conversation"])

    def test_relationship_tracking_is_session_scoped(self):
        self._talk(option="work")
        other = None
        for npc in self.sim.world.npcs:
            if npc.alive and npc.id != self.npc.id:
                other = npc
                break
        if other is None:
            self.skipTest("only one alive npc")
        self.session.handle_command(self.sim, {"type": "player_talk", "target_id": other.id, "option": "work"})
        self.assertIn(self.npc.id, self.session.relationships)
        self.assertIn(other.id, self.session.relationships)


if __name__ == "__main__":
    unittest.main()