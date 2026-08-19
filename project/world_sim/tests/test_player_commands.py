import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from world_sim.presentation.player import (
    PlayerCommandError,
    PlayerSession,
)
from world_sim.presentation.transport import ManagedSimulation, start_snapshot_server
from world_sim.simulation.persistence import save_state
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


def _some_object(sim):
    if not sim.world.objects:
        raise AssertionError("no objects in world")
    return sim.world.objects[0]


class TestPlayerCommands(unittest.TestCase):
    def setUp(self):
        wc, nc = feature_configs(gen_seed=42)
        self.sim = Simulation(wc, nc, seed=99, days=30, print_report=False)
        self.sim.run(days=2)
        self.session = PlayerSession()

    def _cmd(self, ctype, **extra):
        body = {"type": ctype}
        body.update(extra)
        return self.session.handle_command(self.sim, body)

    def test_player_update_finds_nearest_location(self):
        loc = next(iter(self.sim.world.locations.values()))
        if loc.position is None:
            self.skipTest("no location positions in this world")
        x, z = loc.position
        result = self._cmd("player_update", x=x, z=z)
        self.assertTrue(result["ok"])
        self.assertEqual(result["position"], {"x": x, "z": z})
        self.assertEqual(result["location_id"], loc.id)

    def test_player_update_requires_coordinates(self):
        with self.assertRaises(PlayerCommandError):
            self._cmd("player_update")

    def test_talk_with_valid_npc(self):
        npc = _alive_npc(self.sim)
        result = self._cmd("player_talk", target_id=npc.id)
        self.assertTrue(result["ok"])
        self.assertTrue(result["conversation"]["active"])
        self.assertEqual(result["conversation"]["npc_id"], npc.id)
        self.assertIn(result["conversation"]["reply"]["category"], (
            "greeting", "working", "eating", "shopping", "resting", "socializing", "busy",
        ))
        self.assertTrue(result["conversation"]["reply"]["text"])

    def test_talk_with_unknown_npc_rejected(self):
        with self.assertRaises(PlayerCommandError):
            self._cmd("player_talk", target_id="ghost")

    def test_talk_with_dead_npc_rejected(self):
        npc = _alive_npc(self.sim)
        npc.alive = False
        with self.assertRaises(PlayerCommandError):
            self._cmd("player_talk", target_id=npc.id)

    def test_inspect_npc_returns_public_info(self):
        npc = _alive_npc(self.sim)
        result = self._cmd("player_inspect", target_id=npc.id)
        self.assertTrue(result["ok"])
        info = result["target"]
        for key in ("npc_id", "name", "job", "settlement_id", "location_id", "alive",
                    "behavior_state", "pose", "emotion", "intent", "goal", "action",
                    "money", "needs", "relationships"):
            self.assertIn(key, info)
        self.assertEqual(info["npc_id"], npc.id)
        self.assertEqual(info["needs"]["hunger"], round(npc.needs.hunger, 1))

    def test_inspect_object_returns_object_info(self):
        obj = _some_object(self.sim)
        result = self._cmd("player_inspect", target_id=obj.id)
        self.assertTrue(result["ok"])
        for key in ("object_id", "name", "object_type", "state", "location_id", "interactions"):
            self.assertIn(key, result["object"])

    def test_inspect_unknown_target_rejected(self):
        with self.assertRaises(PlayerCommandError):
            self._cmd("player_inspect", target_id="nowhere_thing")

    def test_observe_npc_describes_state(self):
        npc = _alive_npc(self.sim)
        result = self._cmd("player_observe", target_id=npc.id)
        self.assertTrue(result["ok"])
        obs = result["observe"]
        self.assertEqual(obs["npc_id"], npc.id)
        self.assertTrue(obs["description"].startswith(npc.name))

    def test_interact_with_object(self):
        obj = _some_object(self.sim)
        result = self._cmd("player_interact", target_id=obj.id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["object"]["object_id"], obj.id)

    def test_interact_with_unknown_object_rejected(self):
        with self.assertRaises(PlayerCommandError):
            self._cmd("player_interact", target_id="nope")

    def test_unknown_command_type_rejected(self):
        with self.assertRaises(PlayerCommandError):
            self._cmd("teleport")

    def test_same_command_is_deterministic(self):
        npc = _alive_npc(self.sim)
        a = self._cmd("player_talk", target_id=npc.id)
        b = self._cmd("player_talk", target_id=npc.id)
        self.assertEqual(a, b)

    def test_commands_consume_no_sim_rng(self):
        rng_before = self.sim.rng.getstate()
        npc = _alive_npc(self.sim)
        self._cmd("player_update", x=1.0, z=2.0)
        self._cmd("player_talk", target_id=npc.id, option="work")
        self._cmd("player_observe", target_id=npc.id)
        self._cmd("player_inspect", target_id=npc.id)
        self.assertEqual(self.sim.rng.getstate(), rng_before)

    def test_commands_do_not_mutate_sim_state(self):
        npc = _alive_npc(self.sim)
        before = (npc.money, npc.needs.hunger, npc.needs.energy, npc.location_id, npc.current_goal)
        self._cmd("player_talk", target_id=npc.id, option="place")
        self._cmd("player_inspect", target_id=npc.id)
        after = (npc.money, npc.needs.hunger, npc.needs.energy, npc.location_id, npc.current_goal)
        self.assertEqual(after, before)


class TestPlayerCommandEndpoint(unittest.TestCase):
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

    def test_command_endpoint_valid(self):
        sim = self.runner.simulation
        npc = _alive_npc(sim)
        status, body = self._post("/command", {"type": "player_talk", "target_id": npc.id})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_command_endpoint_domain_rejection_is_200_ok_false(self):
        status, body = self._post("/command", {"type": "player_talk", "target_id": "ghost"})
        self.assertEqual(status, 200)
        self.assertFalse(body["ok"])
        self.assertIn("error", body)

    def test_command_endpoint_unknown_type_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/command", {"type": "nope"})
        self.assertEqual(ctx.exception.code, 400)

    def test_command_endpoint_bad_body_is_400(self):
        req = urllib.request.Request(
            self.base + "/command", data=b"{not json", method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 400)

    def test_client_commands_keep_save_byte_identical_to_plain_run(self):
        wc, nc = feature_configs(gen_seed=42)
        plain = Simulation(wc, nc, seed=11, days=2, print_report=False)
        plain.run()

        sim = self.runner.simulation
        npc = _alive_npc(sim)
        obj = sim.world.objects[0] if sim.world.objects else None
        self._post("/command", {"type": "player_update", "x": 0.0, "z": 0.0})
        self._post("/command", {"type": "player_talk", "target_id": npc.id, "option": "work"})
        if obj is not None:
            self._post("/command", {"type": "player_interact", "target_id": obj.id})
        self._post("/command", {"type": "player_talk", "target_id": npc.id, "option": "farewell"})
        self.thread.join()

        pa = self.dir / "plain.json"
        pb = self.dir / "managed.json"
        save_state(plain, pa)
        save_state(sim, pb)
        self.assertEqual(pa.read_bytes(), pb.read_bytes())
        self.assertEqual(plain.rng.getstate(), sim.rng.getstate())


if __name__ == "__main__":
    unittest.main()