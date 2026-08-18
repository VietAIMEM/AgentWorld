import json
import random
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
from world_sim.tests.helpers import load_configs

SETTLEMENT_ECONOMY_FIELDS = [
    "settlement_id",
    "market_id",
    "primary_farm_id",
    "food_stock",
    "restock_amount",
    "farm_stock",
    "farm_stock_cap",
    "open_hour",
    "close_hour",
    "price_multiplier",
]


def settlement_configs(gen_seed=42, se_overrides=None, **gen_overrides):
    wc, nc = load_configs()
    gen = dict(wc["world_generation"])
    gen["enabled"] = True
    gen["seed"] = gen_seed
    gen.update(gen_overrides)
    wc["world_generation"] = gen
    se = dict(wc["settlement_economy"])
    se["enabled"] = True
    if se_overrides:
        se.update(se_overrides)
    wc["settlement_economy"] = se
    return wc, nc


def snapshot(sim):
    world = sim.world
    return {
        "clock": (world.clock.day, world.clock.hour, world.clock.minute, world.clock.tick),
        "elapsed_days": world._elapsed_days,
        "farm_stock": world.farm_stock,
        "stats": asdict(world.stats),
        "economy": (world.economy.food_stock, world.economy.restock_amount),
        "events": [
            (e.type, e.location_id, e.start_tick, e.duration_ticks, e.state.value)
            for e in world.events
        ],
        "dead_ids": [npc.id for npc in world.dead],
        "npcs": [
            (npc.id, npc.money, npc.location_id, npc.home_id, npc.settlement_id, asdict(npc.needs))
            for npc in world.npcs
        ],
        "settlement_economies": {
            sid: asdict(econ) for sid, econ in world.settlement_economies.items()
        },
        "rng_state": sim.rng.getstate(),
    }


class TestSettlementPersistenceSave(unittest.TestCase):
    def test_save_includes_settlement_economies(self):
        wc, nc = settlement_configs(gen_seed=42, settlements=2)
        sim = Simulation(wc, nc, seed=42, days=5, print_report=False)
        sim.run(days=5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("settlement_economies", data)
        saved = {item["settlement_id"]: item for item in data["settlement_economies"]}
        self.assertEqual(set(saved), set(sim.world.settlement_economies))
        for sid, econ in sim.world.settlement_economies.items():
            for field in SETTLEMENT_ECONOMY_FIELDS:
                self.assertIn(field, saved[sid])
                self.assertEqual(saved[sid][field], getattr(econ, field))

    def test_save_includes_npc_settlement_id(self):
        wc, nc = settlement_configs(gen_seed=42, settlements=2)
        sim = Simulation(wc, nc, seed=42, days=5, print_report=False)
        sim.run(days=5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
        for npc_data in data["npcs"]:
            self.assertIn("settlement_id", npc_data)
        ids = {npc_data["settlement_id"] for npc_data in data["npcs"]}
        self.assertTrue(all(sid is not None for sid in ids))


class TestSettlementPersistenceLoad(unittest.TestCase):
    def test_load_restores_settlement_economies_and_settlement_ids(self):
        wc, nc = settlement_configs(gen_seed=42, settlements=2)
        sim = Simulation(wc, nc, seed=42, days=10, print_report=False)
        sim.run(days=10)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            loaded = load_state(path, wc, nc)
        self.assertEqual(
            {sid: asdict(econ) for sid, econ in loaded.world.settlement_economies.items()},
            {sid: asdict(econ) for sid, econ in sim.world.settlement_economies.items()},
        )
        self.assertEqual(
            {n.id: n.settlement_id for n in loaded.world.npcs},
            {n.id: n.settlement_id for n in sim.world.npcs},
        )

    def test_continuation_matches_continuous_seed_42(self):
        wc, nc = settlement_configs(gen_seed=42, settlements=2)
        sim_a = Simulation(wc, nc, seed=42, days=90, print_report=False)
        sim_a.run()
        snap_a = snapshot(sim_a)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            sim_b = Simulation(wc, nc, seed=42, days=90, print_report=False)
            sim_b.run(days=45)
            save_state(sim_b, path)
            loaded = load_state(path, wc, nc, continue_days=45)
            loaded.run()
            self.assertEqual(snap_a, snapshot(loaded))
            self.assertEqual(sim_a.world.clock.tick, loaded.world.clock.tick)

    def test_continuation_matches_continuous_seed_99(self):
        wc, nc = settlement_configs(gen_seed=99, settlements=2)
        sim_a = Simulation(wc, nc, seed=99, days=90, print_report=False)
        sim_a.run()
        snap_a = snapshot(sim_a)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            sim_b = Simulation(wc, nc, seed=99, days=90, print_report=False)
            sim_b.run(days=45)
            save_state(sim_b, path)
            loaded = load_state(path, wc, nc, continue_days=45)
            loaded.run()
            self.assertEqual(snap_a, snapshot(loaded))

    def test_new_stats_fields_persist(self):
        wc, nc = settlement_configs(gen_seed=42, settlements=2)
        sim = Simulation(wc, nc, seed=42, days=15, print_report=False)
        sim.run(days=15)
        world = sim.world
        self.assertTrue(any(world.stats.food_consumed_by_settlement.values()))
        self.assertTrue(any(world.stats.food_produced_by_settlement.values()))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            loaded = load_state(path, wc, nc)
        self.assertEqual(
            loaded.world.stats.food_consumed_by_settlement,
            world.stats.food_consumed_by_settlement,
        )
        self.assertEqual(
            loaded.world.stats.food_produced_by_settlement,
            world.stats.food_produced_by_settlement,
        )

    def test_old_save_without_new_keys_loads(self):
        wc, nc = load_configs()
        wc["world_generation"]["enabled"] = False
        sim = Simulation(wc, nc, seed=1, days=5, print_report=False)
        sim.run(days=5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "save.json"
            save_state(sim, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("settlement_economies", None)
            for npc_data in data["npcs"]:
                npc_data.pop("settlement_id", None)
            for stat in (
                "food_consumed_by_settlement",
                "food_produced_by_settlement",
                "food_bought_by_settlement",
                "food_foraged_by_settlement",
            ):
                data["stats"].pop(stat, None)
            data.pop("cross_settlement_travel", None)
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = load_state(path, wc, nc)
        world = loaded.world
        self.assertEqual(world.settlement_economies, {})
        self.assertFalse(world.settlement_economy_enabled)
        for npc in world.npcs:
            self.assertIsNone(npc.settlement_id)
        self.assertEqual(world.stats.cross_settlement_travel, 0)
        self.assertEqual(world.stats.food_consumed_by_settlement, {})


if __name__ == "__main__":
    unittest.main()