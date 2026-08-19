import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.npc.routine import routine_for_npc, routine_id_for_job
from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import load_configs


def full_configs(gen_seed=42):
    """Generated world + settlement economy + every v0.5 behavior feature."""
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
        "idle": False,
        "objects": {"enabled": True},
        "interactions": True,
        "conversations": {
            "enabled": True,
            "max_turns": 4,
            "initiation_threshold": 0.5,
            "acceptance_threshold": 0.5,
        },
    }
    return wc, nc


V05_NPC_KEYS = (
    "facing",
    "intent",
    "routine_id",
    "conversation_id",
    "idle_state",
    "last_interact_tick",
)


class TestPersistencePhase6(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, wc, nc, seed, days):
        sim = Simulation(wc, nc, seed=seed, days=days, print_report=False)
        sim.run()
        return sim

    def test_old_v04_save_loads_with_defaults(self):
        """A v0.4-style save (all v0.5 keys stripped) loads without behavior enabled."""
        wc, nc = load_configs()
        sim = self._run(wc, nc, seed=1, days=5)
        # Capture pre-save NPC state for semantic comparison.
        needs_before = [asdict(npc.needs) for npc in sim.world.npcs]
        money_before = [npc.money for npc in sim.world.npcs]
        path = self.dir / "old.json"
        save_state(sim, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("objects", None)
        data.pop("conversations", None)
        for npc in data["npcs"]:
            for key in V05_NPC_KEYS:
                npc.pop(key, None)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        loaded = load_state(path, wc, nc, continue_days=2)
        world = loaded.world
        self.assertEqual(world.objects, [])
        self.assertEqual(world.conversations, [])
        self.assertFalse(world.behavior_enabled)
        self.assertEqual(len(world.npcs), len(data["npcs"]))
        for i, npc in enumerate(world.npcs):
            self.assertIsNone(npc.facing)
            self.assertIsNone(npc.intent)
            self.assertIsNone(npc.routine_id)
            self.assertIsNone(npc.conversation_id)
            self.assertIsNone(npc.idle_state)
            self.assertIsNone(npc.last_interact_tick)
            derived = routine_id_for_job(npc.job.id, npc.age)
            self.assertEqual(routine_for_npc(npc, world).id, derived)
            self.assertEqual(asdict(npc.needs), needs_before[i])
            self.assertEqual(npc.money, money_before[i])
        loaded.run()
        self.assertEqual(loaded.world.clock.day, 8)

    def test_old_v04_save_loads_without_behavior_required(self):
        """Even a fully-stripped v0.4 save with an explicit behavior-disabled config loads."""
        wc, nc = load_configs()
        wc["behavior"] = {"enabled": False}
        sim = self._run(wc, nc, seed=7, days=4)
        path = self.dir / "old2.json"
        save_state(sim, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("objects", None)
        data.pop("conversations", None)
        for npc in data["npcs"]:
            for key in V05_NPC_KEYS:
                npc.pop(key, None)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        loaded = load_state(path, wc, nc)
        self.assertEqual(loaded.world.objects, [])
        self.assertEqual(loaded.world.conversations, [])
        for npc in loaded.world.npcs:
            self.assertIsNone(npc.intent)
            self.assertIsNone(npc.conversation_id)

    def test_full_feature_roundtrip_byte_identical(self):
        """save -> load -> save is byte-identical with every v0.5 feature on (seeds 42, 99)."""
        for seed in (42, 99):
            wc, nc = full_configs(gen_seed=seed)
            sim = self._run(wc, nc, seed=seed, days=30)
            self.assertTrue(sim.world.objects)
            self.assertTrue(sim.world.settlement_economies)
            pa = self.dir / f"a{seed}.json"
            pb = self.dir / f"b{seed}.json"
            save_state(sim, pa)
            loaded = load_state(pa, wc, nc, continue_days=0)
            save_state(loaded, pb)
            self.assertEqual(pa.read_bytes(), pb.read_bytes())
            self.assertEqual(
                [o.id for o in loaded.world.objects], [o.id for o in sim.world.objects]
            )
            self.assertEqual(loaded.world.conversations, sim.world.conversations)
            self.assertEqual(
                {sid: asdict(e) for sid, e in loaded.world.settlement_economies.items()},
                {sid: asdict(e) for sid, e in sim.world.settlement_economies.items()},
            )
            for before, after in zip(sim.world.npcs, loaded.world.npcs):
                self.assertEqual(before.facing, after.facing)
                self.assertEqual(before.intent, after.intent)
                self.assertEqual(before.routine_id, after.routine_id)
                self.assertEqual(before.conversation_id, after.conversation_id)
                self.assertEqual(before.idle_state, after.idle_state)
                self.assertEqual(before.last_interact_tick, after.last_interact_tick)

    def test_90d_persistence_invariant_and_rng_continuity(self):
        """Continuous 90d == split 45d+45d, byte-identical final save + identical 100 RNG draws."""
        for seed in (42, 99):
            wc, nc = full_configs(gen_seed=seed)
            sim_a = self._run(wc, nc, seed=seed, days=90)
            p_cont = self.dir / f"cont{seed}.json"
            save_state(sim_a, p_cont)

            sim_b = Simulation(wc, nc, seed=seed, days=90, print_report=False)
            sim_b.run(days=45)
            p_split = self.dir / f"split{seed}.json"
            save_state(sim_b, p_split)
            loaded = load_state(p_split, wc, nc, continue_days=45)
            loaded.run()
            p_joined = self.dir / f"joined{seed}.json"
            save_state(loaded, p_joined)

            self.assertEqual(p_cont.read_bytes(), p_joined.read_bytes())
            rng_a = [sim_a.rng.random() for _ in range(100)]
            rng_b = [loaded.rng.random() for _ in range(100)]
            self.assertEqual(rng_a, rng_b)

    def test_same_seed_determinism_byte_identical(self):
        """Same config + seed twice -> byte-identical final save (seeds 1, 42)."""
        for seed in (1, 42):
            wc, nc = full_configs(gen_seed=42)
            s1 = self._run(wc, nc, seed=seed, days=30)
            s2 = self._run(wc, nc, seed=seed, days=30)
            p1 = self.dir / f"d1_{seed}.json"
            p2 = self.dir / f"d2_{seed}.json"
            save_state(s1, p1)
            save_state(s2, p2)
            self.assertEqual(p1.read_bytes(), p2.read_bytes())

    def test_disabled_parity_byte_identical(self):
        """behavior block present (disabled) vs absent -> byte-identical save (seed 1)."""
        with_block = load_configs()
        with_block[0]["behavior"] = {"enabled": False}
        no_block = load_configs()
        no_block[0].pop("behavior", None)
        pa = self.dir / "wb.json"
        pb = self.dir / "nb.json"
        save_state(self._run(with_block[0], with_block[1], seed=1, days=30), pa)
        save_state(self._run(no_block[0], no_block[1], seed=1, days=30), pb)
        self.assertEqual(pa.read_bytes(), pb.read_bytes())


if __name__ == "__main__":
    unittest.main()