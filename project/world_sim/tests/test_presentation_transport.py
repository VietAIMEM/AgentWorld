import json
import tempfile
import threading
import time
import unittest
import urllib.request
from dataclasses import asdict
from pathlib import Path

from world_sim.presentation.animation import animate
from world_sim.presentation.snapshot import (
    KNOWN_POSES,
    VERSION,
    build_payload,
    coerce_payload,
    serialize_payload,
)
from world_sim.presentation.transport import (
    ManagedSimulation,
    SnapshotStore,
    start_snapshot_server,
)
from world_sim.simulation.persistence import save_state
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import load_configs

ANIMATION_FIELDS = (
    "npc_id",
    "pose",
    "moving",
    "behavior_state",
    "facing_location_id",
    "facing_object_id",
    "facing_npc_id",
    "target_location_id",
    "target_npc_id",
    "target_object_id",
    "emotion",
    "in_conversation",
    "intent",
    "pose_progress",
)


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


def _snapshot_sim(sim):
    world = sim.world
    return (
        sim.rng.getstate(),
        world.clock.tick,
        [
            (
                n.id,
                n.location_id,
                n.money,
                n.alive,
                n.facing,
                n.conversation_id,
                n.current_action.action_type if n.current_action else None,
                asdict(n.needs),
            )
            for n in world.npcs
        ],
        [(o.id, o.state, o.in_use_by) for o in world.objects],
        [(c.id, c.stage, c.turns_left) for c in world.conversations],
        asdict(world.stats),
    )


class TestSnapshotPayload(unittest.TestCase):
    def setUp(self):
        wc, nc = feature_configs(gen_seed=42)
        self.sim = Simulation(wc, nc, seed=99, days=30, print_report=False)
        self.sim.run(days=5)
        self.payload = build_payload(self.sim)

    def test_build_payload_matches_animate(self):
        world = self.sim.world
        self.assertEqual(self.payload["version"], VERSION)
        self.assertEqual(self.payload["tick"], world.clock.tick)
        self.assertEqual(len(self.payload["npcs"]), len(world.npcs))
        for entry, npc in zip(self.payload["npcs"], world.npcs):
            state = animate(npc, world)
            for field in ANIMATION_FIELDS:
                self.assertIn(field, entry)
                self.assertEqual(entry[field], getattr(state, field))
            self.assertEqual(entry["name"], npc.name)

    def test_payload_includes_objects_and_locations(self):
        self.assertTrue(self.payload["objects"])
        self.assertTrue(self.payload["locations"])
        for obj in self.payload["objects"]:
            for key in ("object_id", "name", "location_id", "object_type", "state"):
                self.assertIn(key, obj)
        for loc in self.payload["locations"]:
            for key in ("location_id", "name", "type", "x", "z"):
                self.assertIn(key, loc)

    def test_serialization_is_deterministic(self):
        a = serialize_payload(self.payload)
        b = serialize_payload(build_payload(self.sim))
        self.assertEqual(a, b)
        self.assertEqual(json.loads(a), json.loads(b))

    def test_no_simulation_state_mutation(self):
        before = _snapshot_sim(self.sim)
        build_payload(self.sim)
        serialize_payload(self.payload)
        self.assertEqual(_snapshot_sim(self.sim), before)

    def test_no_rng_consumption(self):
        rng_before = self.sim.rng.getstate()
        build_payload(self.sim)
        self.assertEqual(self.sim.rng.getstate(), rng_before)

    def test_coerce_fills_missing_optional_fields(self):
        raw = {
            "version": 1,
            "tick": 10,
            "npcs": [
                {
                    "npc_id": "npc_1",
                    "pose": "walk",
                    "moving": True,
                    "behavior_state": "moving",
                    "facing_location_id": "tavern",
                }
            ],
            "locations": [{"location_id": "tavern", "name": "Tavern", "type": "social"}],
        }
        coerced = coerce_payload(raw)
        npc = coerced["npcs"][0]
        self.assertEqual(npc["npc_id"], "npc_1")
        self.assertIsNone(npc["facing_npc_id"])
        self.assertIsNone(npc["facing_object_id"])
        self.assertIsNone(npc["target_location_id"])
        self.assertIsNone(npc["target_npc_id"])
        self.assertIsNone(npc["target_object_id"])
        self.assertEqual(npc["emotion"], "content")
        self.assertFalse(npc["in_conversation"])
        self.assertIsNone(npc["intent"])
        self.assertEqual(npc["pose_progress"], 0.0)
        self.assertEqual(coerced["tick"], 10)

    def test_coerce_unknown_pose_falls_back_to_idle(self):
        raw = {
            "npcs": [{"npc_id": "x", "pose": "moonwalk", "behavior_state": "idle"}]
        }
        npc = coerce_payload(raw)["npcs"][0]
        self.assertEqual(npc["pose"], "idle")
        self.assertNotIn("moonwalk", KNOWN_POSES)

    def test_coerce_unknown_targets_are_nulled(self):
        raw = {
            "npcs": [
                {
                    "npc_id": "a",
                    "pose": "talk",
                    "facing_npc_id": "ghost",
                    "target_npc_id": "ghost",
                    "facing_location_id": "nowhere",
                    "facing_object_id": "no_object",
                }
            ],
            "locations": [],
            "objects": [],
        }
        npc = coerce_payload(raw)["npcs"][0]
        self.assertIsNone(npc["facing_npc_id"])
        self.assertIsNone(npc["target_npc_id"])
        self.assertIsNone(npc["facing_location_id"])
        self.assertIsNone(npc["facing_object_id"])

    def test_coerce_keeps_known_targets(self):
        raw = {
            "npcs": [
                {"npc_id": "a", "pose": "talk", "facing_npc_id": "b"},
                {"npc_id": "b", "pose": "listen"},
            ]
        }
        npc = coerce_payload(raw)["npcs"][0]
        self.assertEqual(npc["facing_npc_id"], "b")


class TestSnapshotTransport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _request(self, method, url, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_healthz_and_snapshot_endpoints(self):
        store = SnapshotStore()
        server = start_snapshot_server(store, port=0)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            status, body = self._request("GET", f"{base}/healthz")
            self.assertEqual(status, 200)
            self.assertTrue(body["ok"])
            with self.assertRaises(urllib.error.HTTPError):
                self._request("GET", f"{base}/snapshot")
            store.publish({"version": 1, "tick": 3, "npcs": []})
            status, body = self._request("GET", f"{base}/snapshot")
            self.assertEqual(status, 200)
            self.assertEqual(body["tick"], 3)
        finally:
            server.shutdown()
            server.server_close()

    def test_control_endpoint(self):
        store = SnapshotStore()
        wc, nc = feature_configs(gen_seed=42)
        runner = ManagedSimulation(wc, nc, seed=1, days=2, store=store)
        server = start_snapshot_server(store, runner, port=0)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for action in ("play", "pause", "step", "reset"):
                status, body = self._request("POST", f"{base}/control", {"action": action})
                self.assertEqual(status, 200)
                self.assertTrue(body["ok"])
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._request("POST", f"{base}/control", {"action": "explode"})
            self.assertEqual(ctx.exception.code, 400)
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._request("POST", f"{base}/control", {"action": 42})
            self.assertEqual(ctx.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()

    def test_disconnected_server_does_not_affect_simulation(self):
        """Server active + store publishing but no client == plain simulation."""
        wc, nc = feature_configs(gen_seed=42)
        plain = Simulation(wc, nc, seed=7, days=10, print_report=False)
        plain.run()

        store = SnapshotStore()
        runner = ManagedSimulation(wc, nc, seed=7, days=10, store=store)
        server = start_snapshot_server(store, runner, port=0)
        thread = runner.run()
        try:
            thread.join()
        finally:
            server.shutdown()
            server.server_close()

        pa = self.dir / "plain.json"
        pb = self.dir / "managed.json"
        save_state(plain, pa)
        save_state(runner.simulation, pb)
        self.assertEqual(pa.read_bytes(), pb.read_bytes())
        self.assertEqual(plain.rng.getstate(), runner.simulation.rng.getstate())

    def test_connected_and_disconnected_runs_are_byte_identical(self):
        """30d with a live polling client is identical to a plain 30d run."""
        wc, nc = feature_configs(gen_seed=42)
        plain = Simulation(wc, nc, seed=99, days=30, print_report=False)
        plain.run()

        store = SnapshotStore()
        runner = ManagedSimulation(wc, nc, seed=99, days=30, store=store)
        server = start_snapshot_server(store, runner, port=0)
        thread = runner.run()
        base = f"http://127.0.0.1:{server.server_port}"
        fetched = []
        stop = threading.Event()

        def poll():
            while not stop.is_set() and (thread is None or thread.is_alive()):
                try:
                    with urllib.request.urlopen(f"{base}/snapshot", timeout=1) as resp:
                        fetched.append(json.loads(resp.read().decode("utf-8")))
                except Exception:
                    pass
                time.sleep(0.02)

        poller = threading.Thread(target=poll, daemon=True)
        poller.start()
        thread.join()
        stop.set()
        poller.join()
        server.shutdown()
        server.server_close()

        self.assertGreater(len(fetched), 10)
        self.assertEqual(fetched[-1]["version"], VERSION)

        pa = self.dir / "plain.json"
        pb = self.dir / "managed.json"
        save_state(plain, pa)
        save_state(runner.simulation, pb)
        self.assertEqual(pa.read_bytes(), pb.read_bytes())
        self.assertEqual(plain.rng.getstate(), runner.simulation.rng.getstate())
        draws_a = [plain.rng.random() for _ in range(100)]
        draws_b = [runner.simulation.rng.random() for _ in range(100)]
        self.assertEqual(draws_a, draws_b)


if __name__ == "__main__":
    unittest.main()