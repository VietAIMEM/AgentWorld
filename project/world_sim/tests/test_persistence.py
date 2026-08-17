import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation

from world_sim.tests.helpers import load_configs

LIFECYCLE_NPCS = {
    "npcs": [
        {"id": "npc_001", "name": "Ada", "age": 1, "money": 60, "job": "farmer"},
        {"id": "npc_002", "name": "Bo", "age": 2, "money": 50, "job": "merchant"},
        {"id": "npc_003", "name": "Cy", "age": 3, "money": 55, "job": "worker"},
        {"id": "npc_004", "name": "Di", "age": 1, "money": 45, "job": "farmer"},
        {"id": "npc_005", "name": "El", "age": 2, "money": 40, "job": "merchant"},
    ]
}


def _snapshot(sim):
    world = sim.world
    return {
        "clock": (world.clock.day, world.clock.hour, world.clock.minute, world.clock.tick),
        "elapsed_days": world._elapsed_days,
        "farm_stock": world.farm_stock,
        "stats": asdict(world.stats),
        "economy": (
            world.economy.food_stock,
            world.economy.restock_amount,
            world.economy.open_hour,
            world.economy.close_hour,
        ),
        "events": [
            (e.id, e.type, e.location_id, e.start_tick, e.duration_ticks, e.state.value, e.started_tick)
            for e in world.events
        ],
        "dead_ids": [npc.id for npc in world.dead],
        "npcs": [
            {
                "id": npc.id,
                "age": npc.age,
                "money": npc.money,
                "location_id": npc.location_id,
                "home_id": npc.home_id,
                "job": npc.job.id,
                "needs": asdict(npc.needs),
                "personality": asdict(npc.personality),
                "relationships": dict(npc.relationships),
                "inventory": dict(npc.inventory),
                "alive": npc.alive,
                "last_wake_day": npc.last_wake_day,
                "last_socialize_day": npc.last_socialize_day,
                "hungry_logged": npc.hungry_logged,
                "goal": npc.current_goal.type.value if npc.current_goal else None,
                "goal_status": npc.current_goal.status.value if npc.current_goal else None,
                "goal_started": npc.current_goal.started_tick if npc.current_goal else None,
                "action": npc.current_action.action_type if npc.current_action else None,
                "memories": [(m.event_type, m.description) for m in npc.memory.entries],
            }
            for npc in world.npcs
        ],
        "rng_state": sim.rng.getstate(),
    }


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "save.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_creates_file(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=1, days=5, print_report=False)
        sim.run(days=3)
        save_state(sim, self.path)
        self.assertTrue(self.path.exists())
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "world_sim_save_v1")
        self.assertEqual(data["seed"], 1)
        self.assertEqual(data["total_days"], 5)
        self.assertIn("rng_state", data)
        self.assertEqual(len(data["npcs"]), len(nc["npcs"]))

    def test_load_restores_basic_state(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=9, days=30, print_report=False)
        sim.run(days=12)
        save_state(sim, self.path)
        loaded = load_state(self.path, wc, nc, continue_days=18)
        before, after = sim.world, loaded.world
        self.assertEqual(
            (before.clock.day, before.clock.hour, before.clock.minute, before.clock.tick),
            (after.clock.day, after.clock.hour, after.clock.minute, after.clock.tick),
        )
        self.assertEqual(before._elapsed_days, after._elapsed_days)
        self.assertEqual(before.farm_stock, after.farm_stock)
        self.assertEqual(before.stats, after.stats)
        self.assertEqual([event.id for event in before.events], [event.id for event in after.events])
        self.assertEqual([npc.id for npc in before.dead], [npc.id for npc in after.dead])
        self.assertEqual(loaded.days, 18)

    def test_load_restores_rng_state(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=7, days=30, print_report=False)
        sim.run(days=10)
        saved_state = sim.rng.getstate()
        save_state(sim, self.path)
        loaded = load_state(self.path, wc, nc, continue_days=20)
        self.assertEqual(loaded.rng.getstate(), saved_state)

    def test_continued_random_draws_match(self):
        wc, nc = load_configs()
        sim_a = Simulation(wc, nc, seed=5, days=40, print_report=False)
        sim_a.run(days=20)
        sim_b = Simulation(wc, nc, seed=5, days=40, print_report=False)
        sim_b.run(days=20)
        save_state(sim_b, self.path)
        sim_b_loaded = load_state(self.path, wc, nc, continue_days=20)
        draws_a = [sim_a.rng.random() for _ in range(100)]
        draws_b = [sim_b_loaded.rng.random() for _ in range(100)]
        self.assertEqual(draws_a, draws_b)

    def test_load_restores_npc_state(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=11, days=20, print_report=False)
        sim.run(days=10)
        save_state(sim, self.path)
        loaded = load_state(self.path, wc, nc, continue_days=10)
        for before, after in zip(sim.world.npcs, loaded.world.npcs):
            self.assertEqual(before.id, after.id)
            self.assertEqual(before.age, after.age)
            self.assertEqual(before.money, after.money)
            self.assertEqual(before.location_id, after.location_id)
            self.assertEqual(before.home_id, after.home_id)
            self.assertEqual(before.job.id, after.job.id)
            self.assertEqual(asdict(before.needs), asdict(after.needs))
            self.assertEqual(asdict(before.personality), asdict(after.personality))
            self.assertEqual(before.relationships, after.relationships)
            self.assertEqual(before.inventory, after.inventory)
            self.assertEqual(before.alive, after.alive)
            before_action = before.current_action.action_type if before.current_action else None
            after_action = after.current_action.action_type if after.current_action else None
            self.assertEqual(before_action, after_action)

    def test_load_restores_world_economy_state(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=3, days=20, print_report=False)
        sim.run(days=8)
        save_state(sim, self.path)
        loaded = load_state(self.path, wc, nc, continue_days=12)
        self.assertEqual(sim.world.economy.food_stock, loaded.world.economy.food_stock)
        self.assertEqual(sim.world.economy.restock_amount, loaded.world.economy.restock_amount)
        self.assertEqual(sim.world.economy.open_hour, loaded.world.economy.open_hour)
        self.assertEqual(sim.world.economy.close_hour, loaded.world.economy.close_hour)

    def test_load_restores_relationships_and_memories(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=2, days=30, print_report=False)
        sim.run(days=15)
        save_state(sim, self.path)
        loaded = load_state(self.path, wc, nc, continue_days=15)
        for before, after in zip(sim.world.npcs, loaded.world.npcs):
            self.assertEqual(before.relationships, after.relationships)
            self.assertEqual(len(before.memory.entries), len(after.memory.entries))
            self.assertEqual(
                [(m.event_type, m.description) for m in before.memory.entries],
                [(m.event_type, m.description) for m in after.memory.entries],
            )

    def test_lifecycle_state_preserved(self):
        wc, nc = load_configs()
        wc["aging"] = {"days_per_year": 10}
        wc["birth"] = {"enabled": True, "interval_days": 5, "max_population": 50, "money": 10}
        wc["old_age"] = {"enabled": True, "max_age": 2}
        sim_a = Simulation(wc, LIFECYCLE_NPCS, seed=42, days=40, print_report=False)
        sim_a.run()
        snap_a = _snapshot(sim_a)

        sim_b = Simulation(wc, LIFECYCLE_NPCS, seed=42, days=40, print_report=False)
        sim_b.run(days=20)
        save_state(sim_b, self.path)
        loaded = load_state(self.path, wc, LIFECYCLE_NPCS, continue_days=20)
        loaded.run()
        snap_b = _snapshot(loaded)

        self.assertEqual(snap_a, snap_b)
        self.assertGreater(sim_a.world.stats.births, 0)
        self.assertGreater(sim_a.world.stats.old_age_deaths, 0)

    def test_save_and_load_at_different_times(self):
        wc, nc = load_configs()
        sim = Simulation(wc, nc, seed=3, days=60, print_report=False)
        sim.run(days=30)
        save_state(sim, self.path)
        loaded = load_state(self.path, wc, nc, continue_days=20)
        self.assertEqual(loaded.days, 20)
        self.assertEqual(loaded._total_days, 60)
        loaded.run()
        self.assertEqual(loaded.world.clock.day, 51)
        self.assertEqual(loaded.world._elapsed_days, 50)
        resumed = load_state(self.path, wc, nc)
        self.assertEqual(resumed.days, 30)

    def test_invalid_or_corrupted_save_raises(self):
        wc, nc = load_configs()
        base = Path(self.tmp.name)
        bad = base / "bad.json"
        bad.write_text("not json{{{", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_state(bad, wc, nc)
        wrong_format = base / "wrong.json"
        wrong_format.write_text(json.dumps({"format": "bogus"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_state(wrong_format, wc, nc)
        incomplete = base / "incomplete.json"
        incomplete.write_text(json.dumps({"format": "world_sim_save_v1", "seed": 1}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_state(incomplete, wc, nc)

    def test_90day_continuous_equals_save_load_continuation(self):
        wc, nc = load_configs()
        sim_a = Simulation(wc, nc, seed=42, days=90, print_report=False)
        sim_a.run()
        snap_a = _snapshot(sim_a)

        sim_b = Simulation(wc, nc, seed=42, days=90, print_report=False)
        sim_b.run(days=45)
        save_state(sim_b, self.path)
        loaded = load_state(self.path, wc, nc, continue_days=45)
        loaded.run()
        snap_b = _snapshot(loaded)

        self.assertEqual(snap_a, snap_b)
        self.assertEqual(sim_a.world.clock.tick, loaded.world.clock.tick)


if __name__ == "__main__":
    unittest.main()