import json
import tempfile
import unittest
from pathlib import Path

from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import load_configs


def social_configs(gen_seed=42, enabled=True, social_events=True):
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
        "social_life": {"enabled": enabled, "social_events": social_events},
    }
    return wc, nc


class TestSocialLifePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_90d_continuous_equals_split_for_seeds(self):
        for seed in (42, 99):
            wc, nc = social_configs(gen_seed=seed)
            sim_a = Simulation(wc, nc, seed=seed, days=90, print_report=False)
            sim_a.run()
            path_a = self.dir / f"a_{seed}.json"
            save_state(sim_a, path_a)

            sim_b = Simulation(wc, nc, seed=seed, days=90, print_report=False)
            sim_b.run(days=45)
            path_b = self.dir / f"b_{seed}.json"
            save_state(sim_b, path_b)
            loaded = load_state(path_b, wc, nc, continue_days=45)
            loaded.run()
            path_c = self.dir / f"c_{seed}.json"
            save_state(loaded, path_c)

            self.assertEqual(path_a.read_bytes(), path_c.read_bytes())
            draws_a = [sim_a.rng.random() for _ in range(100)]
            draws_b = [loaded.rng.random() for _ in range(100)]
            self.assertEqual(draws_a, draws_b)
            self.assertEqual(sim_a.world.clock.tick, loaded.world.clock.tick)

    def test_relationships_and_memories_persist(self):
        wc, nc = social_configs(gen_seed=42)
        sim = Simulation(wc, nc, seed=1, days=20, print_report=False)
        sim.run(days=10)
        relationships = {npc.id: dict(npc.relationships) for npc in sim.world.npcs}
        memories = {
            npc.id: [(e.event_type, e.description, e.related_entity) for e in npc.memory.entries]
            for npc in sim.world.npcs
        }
        path = self.dir / "state.json"
        save_state(sim, path)
        loaded = load_state(path, wc, nc, continue_days=10)
        for npc in loaded.world.npcs:
            self.assertEqual(npc.relationships, relationships[npc.id])
            self.assertEqual(
                [(e.event_type, e.description, e.related_entity) for e in npc.memory.entries],
                memories[npc.id],
            )

    def test_social_events_persist_when_enabled(self):
        wc, nc = social_configs(gen_seed=42, enabled=True, social_events=True)
        sim = Simulation(wc, nc, seed=3, days=30, print_report=False)
        labeled = [e for e in sim.world.events if e.social_type is not None]
        if not labeled:
            self.skipTest("no social events scheduled for this seed")
        path = self.dir / "events.json"
        save_state(sim, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("social_type", data["events"][0])
        loaded = load_state(path, wc, nc, continue_days=20)
        loaded_by_id = {e.id: e for e in loaded.world.events}
        for event in sim.world.events:
            restored = loaded_by_id[event.id]
            self.assertEqual(restored.social_type, event.social_type)

    def test_old_save_without_social_fields_loads(self):
        wc, nc = social_configs(gen_seed=42, enabled=True, social_events=True)
        sim = Simulation(wc, nc, seed=5, days=10, print_report=False)
        sim.run(days=3)
        path = self.dir / "old.json"
        save_state(sim, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        for event in data["events"]:
            event.pop("social_type", None)
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_state(path, wc, nc, continue_days=7)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.world.npcs), len(sim.world.npcs))

    def test_disabled_mode_is_byte_identical(self):
        wc, nc = social_configs(gen_seed=42, enabled=False, social_events=False)
        sim_a = Simulation(wc, nc, seed=9, days=12, print_report=False)
        sim_a.run()
        sim_b = Simulation(wc, nc, seed=9, days=12, print_report=False)
        sim_b.run()
        path_a = self.dir / "disabled_a.json"
        path_b = self.dir / "disabled_b.json"
        save_state(sim_a, path_a)
        save_state(sim_b, path_b)
        self.assertEqual(path_a.read_bytes(), path_b.read_bytes())
        self.assertEqual(sim_a.rng.getstate(), sim_b.rng.getstate())

    def test_disabled_mode_matches_enabled_differences(self):
        wc, nc = social_configs(gen_seed=42, enabled=False, social_events=False)
        sim_off = Simulation(wc, nc, seed=9, days=12, print_report=False)
        sim_off.run()
        wc_on, nc_on = social_configs(gen_seed=42, enabled=True, social_events=True)
        sim_on = Simulation(wc_on, nc_on, seed=9, days=12, print_report=False)
        sim_on.run()
        path_off = self.dir / "off.json"
        path_on = self.dir / "on.json"
        save_state(sim_off, path_off)
        save_state(sim_on, path_on)
        self.assertNotEqual(path_off.read_bytes(), path_on.read_bytes())


if __name__ == "__main__":
    unittest.main()