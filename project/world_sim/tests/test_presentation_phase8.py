import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from world_sim.presentation.player import PLAYER_INTERACTION_VERSION, PlayerSession
from world_sim.presentation.snapshot import serialize_payload
from world_sim.presentation.transport import ManagedSimulation, start_snapshot_server
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
    }
    return wc, nc


def _alive_npc(sim):
    for npc in sim.world.npcs:
        if npc.alive:
            return npc
    raise AssertionError("no alive npc found")


class TestInteractionPayload(unittest.TestCase):
    def setUp(self):
        wc, nc = feature_configs(gen_seed=42)
        self.sim = Simulation(wc, nc, seed=5, days=30, print_report=False)
        self.sim.run(days=2)
        self.session = PlayerSession()

    def _payload(self):
        return self.session.build_interaction_payload(self.sim)

    def test_initial_payload_structure(self):
        p = self._payload()
        self.assertEqual(p["version"], PLAYER_INTERACTION_VERSION)
        self.assertEqual(p["tick"], self.sim.world.clock.tick)
        self.assertEqual(p["day"], self.sim.world.clock.day)
        self.assertNotIn("player", p)
        self.assertIn("nearby", p)
        self.assertIn("conversation", p)
        self.assertFalse(p["conversation"]["active"])
        self.assertNotIn("location", p)
        self.assertNotIn("target", p)
        self.assertNotIn("object", p)

    def test_player_update_adds_location(self):
        loc = next((l for l in self.sim.world.locations.values() if l.position is not None), None)
        if loc is None:
            self.skipTest("no positioned locations")
        self.session.handle_command(
            self.sim, {"type": "player_update", "x": loc.position[0], "z": loc.position[1]}
        )
        p = self._payload()
        self.assertEqual(p["player"]["location_id"], loc.id)
        self.assertIn("location", p)
        info = p["location"]
        for key in ("location_id", "name", "type", "settlement_id", "npc_count",
                    "npc_ids", "objects", "activities"):
            self.assertIn(key, info)
        self.assertEqual(info["location_id"], loc.id)

    def test_nearby_lists_from_location(self):
        loc = next((l for l in self.sim.world.locations.values() if l.position is not None), None)
        if loc is None:
            self.skipTest("no positioned locations")
        self.session.handle_command(
            self.sim, {"type": "player_update", "x": loc.position[0], "z": loc.position[1]}
        )
        p = self._payload()
        alive_here = [n.id for n in self.sim.world.npcs if n.alive and n.location_id == loc.id]
        self.assertEqual(sorted(p["nearby"]["npc_ids"]), sorted(alive_here))

    def test_inspected_npc_appears_as_target(self):
        npc = _alive_npc(self.sim)
        self.session.handle_command(self.sim, {"type": "player_inspect", "target_id": npc.id})
        p = self._payload()
        self.assertEqual(p["target"]["npc_id"], npc.id)
        self.assertEqual(p["target"]["name"], npc.name)

    def test_inspected_object_appears_as_object(self):
        if not self.sim.world.objects:
            self.skipTest("no objects")
        obj = self.sim.world.objects[0]
        self.session.handle_command(self.sim, {"type": "player_inspect", "target_id": obj.id})
        p = self._payload()
        self.assertEqual(p["object"]["object_id"], obj.id)
        self.assertEqual(p["object"]["state"], obj.state)

    def test_dead_target_clears_from_payload(self):
        npc = _alive_npc(self.sim)
        self.session.handle_command(self.sim, {"type": "player_inspect", "target_id": npc.id})
        npc.alive = False
        p = self._payload()
        self.assertNotIn("target", p)
        self.assertNotIn("object", p)

    def test_conversation_reflected_in_payload(self):
        npc = _alive_npc(self.sim)
        self.session.handle_command(
            self.sim, {"type": "player_talk", "target_id": npc.id, "option": "work"}
        )
        p = self._payload()
        self.assertTrue(p["conversation"]["active"])
        self.assertEqual(p["conversation"]["npc_id"], npc.id)
        self.assertEqual(p["conversation"]["category"], "working")
        self.assertTrue(p["conversation"]["text"])
        self.assertEqual(len(p["conversation"]["options"]), 3)

    def test_closed_conversation_inactive(self):
        npc = _alive_npc(self.sim)
        self.session.handle_command(
            self.sim, {"type": "player_talk", "target_id": npc.id, "option": "farewell"}
        )
        p = self._payload()
        self.assertFalse(p["conversation"]["active"])

    def test_payload_serialization_is_deterministic(self):
        npc = _alive_npc(self.sim)
        self.session.handle_command(self.sim, {"type": "player_update", "x": 0.0, "z": 0.0})
        self.session.handle_command(
            self.sim, {"type": "player_talk", "target_id": npc.id, "option": "place"}
        )
        a = serialize_payload(self._payload())
        b = serialize_payload(self._payload())
        self.assertEqual(a, b)
        self.assertEqual(json.loads(a), json.loads(b))

    def test_payload_consumes_no_sim_rng(self):
        rng_before = self.sim.rng.getstate()
        npc = _alive_npc(self.sim)
        self.session.handle_command(
            self.sim, {"type": "player_talk", "target_id": npc.id, "option": "work"}
        )
        self._payload()
        self.assertEqual(self.sim.rng.getstate(), rng_before)


class TestInteractionEndpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        wc, nc = feature_configs(gen_seed=42)
        self.runner = ManagedSimulation(wc, nc, seed=11, days=2, store=None)
        self.server = start_snapshot_server(self.runner.store, self.runner, port=0)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = self.runner.run()

    def tearDown(self):
        self.runner.stop()
        if self.thread.is_alive():
            self.thread.join(timeout=5)
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _post(self, path, body):
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode("utf-8"), method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_interaction_endpoint_returns_payload(self):
        sim = self.runner.simulation
        npc = _alive_npc(sim)
        status, body = self._post("/command", {"type": "player_talk", "target_id": npc.id})
        self.assertEqual(status, 200)
        with urllib.request.urlopen(f"{self.base}/interaction", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(payload["version"], PLAYER_INTERACTION_VERSION)
        self.assertTrue(payload["conversation"]["active"])
        self.assertEqual(payload["conversation"]["npc_id"], npc.id)

    def test_interaction_endpoint_after_farewell(self):
        sim = self.runner.simulation
        npc = _alive_npc(sim)
        self._post("/command", {"type": "player_talk", "target_id": npc.id, "option": "farewell"})
        with urllib.request.urlopen(f"{self.base}/interaction", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertFalse(payload["conversation"]["active"])

    def test_reset_clears_session(self):
        sim = self.runner.simulation
        npc = _alive_npc(sim)
        self._post("/command", {"type": "player_talk", "target_id": npc.id})
        self._post("/control", {"action": "reset"})
        with urllib.request.urlopen(f"{self.base}/interaction", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertFalse(payload["conversation"]["active"])
        self.assertNotIn("target", payload)


if __name__ == "__main__":
    unittest.main()