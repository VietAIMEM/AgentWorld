import random
import tempfile
import unittest
from collections import deque
from dataclasses import asdict
from pathlib import Path

from world_sim.simulation.persistence import load_state, save_state
from world_sim.simulation.simulation import Simulation
from world_sim.simulation.world import World
from world_sim.tests.helpers import load_configs


def generated_configs(seed=42, **overrides):
    wc, nc = load_configs()
    gen = dict(wc["world_generation"])
    gen["enabled"] = True
    gen["seed"] = seed
    gen.update(overrides)
    wc["world_generation"] = gen
    return wc, nc


def generated_world(gen_seed=42, sim_seed=1, run_days=30, **overrides):
    wc, nc = generated_configs(seed=gen_seed, **overrides)
    return World(wc, nc, random.Random(sim_seed), run_days=run_days, seed=sim_seed)


def generated_simulation(gen_seed=42, sim_seed=42, days=30, **overrides):
    wc, nc = generated_configs(seed=gen_seed, **overrides)
    return Simulation(wc, nc, seed=sim_seed, days=days, print_report=False)


def reachable(world, start):
    if start not in world.locations:
        return set()
    seen = {start}
    queue = deque(world.locations[start].connected)
    while queue:
        nid = queue.popleft()
        if nid in seen or nid not in world.locations:
            continue
        seen.add(nid)
        queue.extend(world.locations[nid].connected)
    return seen


def location_snapshot(world):
    return {
        lid: (
            loc.type,
            tuple(loc.connected),
            tuple(loc.resources),
            tuple(loc.activities),
            loc.region_id,
            loc.position,
        )
        for lid, loc in world.locations.items()
    }


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
            (npc.id, npc.money, npc.location_id, npc.home_id, npc.job.id, asdict(npc.needs))
            for npc in world.npcs
        ],
        "rng_state": sim.rng.getstate(),
    }


class TestWorldGeneration(unittest.TestCase):
    def test_generation_disabled_preserves_existing_behavior(self):
        wc, nc = load_configs()
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        self.assertFalse(world.generated_world)
        self.assertIsNone(world._gen_seed)
        self.assertEqual(sorted(world.locations), ["farm", "forest", "home", "market", "tavern"])
        self.assertEqual(world.market_id, "market")
        self.assertEqual(world.social_location, "tavern")
        self.assertEqual(len(world.npcs), 20)
        expected = {"farmer": "farm", "merchant": "market", "worker": "tavern"}
        for npc in world.npcs:
            self.assertEqual(npc.home_id, "home")
            self.assertEqual(npc.job.work_location, expected[npc.job.id])

    def test_same_seed_is_deterministic(self):
        a = generated_world(gen_seed=11)
        b = generated_world(gen_seed=11)
        self.assertEqual(location_snapshot(a), location_snapshot(b))
        self.assertEqual({r.id: (r.kind, tuple(r.location_ids)) for r in a.regions.values()},
                         {r.id: (r.kind, tuple(r.location_ids)) for r in b.regions.values()})
        self.assertEqual(list(a._jobs), list(b._jobs))
        self.assertEqual(
            [(n.id, n.home_id, n.job.id) for n in a.npcs],
            [(n.id, n.home_id, n.job.id) for n in b.npcs],
        )

    def test_different_seeds_can_differ(self):
        a = generated_world(gen_seed=1)
        b = generated_world(gen_seed=2)
        self.assertNotEqual(
            {lid: loc.position for lid, loc in a.locations.items()},
            {lid: loc.position for lid, loc in b.locations.items()},
        )

    def test_all_locations_connected(self):
        world = generated_world(gen_seed=7)
        self.assertEqual(len(reachable(world, world.market_id)), len(world.locations))

    def test_no_isolated_locations(self):
        world = generated_world(gen_seed=7)
        for lid, loc in world.locations.items():
            self.assertGreater(len(loc.connected), 0, f"{lid} is isolated")
            self.assertTrue(lid in reachable(world, world.market_id))

    def test_home_reaches_market(self):
        world = generated_world(gen_seed=7)
        for npc in world.npcs:
            self.assertIn(world.market_id, reachable(world, npc.home_id))

    def test_home_reaches_workplace(self):
        world = generated_world(gen_seed=7)
        for npc in world.npcs:
            self.assertIn(npc.job.work_location, reachable(world, npc.home_id))

    def test_home_reaches_farm(self):
        world = generated_world(gen_seed=7)
        farms = [lid for lid, loc in world.locations.items() if "farm" in lid]
        for npc in world.npcs:
            self.assertTrue(any(f in reachable(world, npc.home_id) for f in farms))

    def test_home_reaches_natural_food(self):
        world = generated_world(gen_seed=7)
        naturals = [
            lid for lid, loc in world.locations.items()
            if loc.type == "natural" and "food" in loc.resources
        ]
        for npc in world.npcs:
            self.assertTrue(any(n in reachable(world, npc.home_id) for n in naturals))

    def test_all_job_work_locations_valid(self):
        world = generated_world(gen_seed=7)
        for job in world._jobs.values():
            self.assertIn(job.work_location, world.locations)
        for npc in world.npcs:
            self.assertIn(npc.job.work_location, world.locations)

    def test_npcs_distributed_across_settlements(self):
        world = generated_world(gen_seed=7, settlements=2)
        settlements = {npc.home_id.split("_house_")[0] for npc in world.npcs}
        self.assertEqual(settlements, {"settlement_0", "settlement_1"})
        for npc in world.npcs:
            settlement = npc.home_id.split("_house_")[0]
            self.assertTrue(npc.home_id.startswith(f"{settlement}_house_"))
            self.assertTrue(npc.job.id.endswith(f"_{settlement}"))

    def test_market_id_valid(self):
        world = generated_world(gen_seed=7)
        self.assertIn(world.market_id, world.locations)
        self.assertEqual(world.locations[world.market_id].type, "commercial")

    def test_social_location_valid(self):
        world = generated_world(gen_seed=7)
        self.assertIn(world.social_location, world.locations)
        self.assertEqual(world.locations[world.social_location].type, "social")

    def test_newborn_gets_valid_residence(self):
        wc, nc = generated_configs(seed=7)
        wc["birth"] = {"enabled": True, "interval_days": 1, "max_population": 50, "money": 10}
        world = World(wc, nc, random.Random(1), run_days=30, seed=1)
        before = len(world.npcs)
        world._spawn_newborn()
        newborn = world.npcs[-1]
        self.assertEqual(len(world.npcs), before + 1)
        self.assertEqual(world.locations[newborn.home_id].type, "residence")
        self.assertEqual(newborn.location_id, newborn.home_id)
        self.assertIn(newborn.job.id, world._jobs)
        self.assertIn(newborn.job.work_location, world.locations)

    def test_generated_world_runs_simulation(self):
        sim = generated_simulation(gen_seed=5, sim_seed=5, days=5)
        sim.run(days=5)
        self.assertGreater(sim.world.clock.day, 1)

    def test_food_produced_and_foraged(self):
        sim = generated_simulation(gen_seed=42, sim_seed=42, days=30)
        sim.run(days=30)
        self.assertGreater(sim.world.stats.food_produced, 0)
        self.assertGreater(sim.world.stats.food_foraged, 0)
        self.assertGreater(sim.world.stats.food_consumed, 0)

    def test_core_safety_invariants(self):
        sim = generated_simulation(gen_seed=42, sim_seed=99, days=30)
        sim.run(days=30)
        world = sim.world
        self.assertEqual(world.stats.deaths, 0)
        for npc in world.npcs:
            self.assertTrue(npc.alive)
            self.assertIn(npc.location_id, world.locations)
            self.assertIn(npc.home_id, world.locations)
            self.assertIn(npc.job.work_location, world.locations)
            self.assertGreaterEqual(npc.money, 0.0)
        self.assertGreaterEqual(world.farm_stock, 0)
        self.assertGreaterEqual(world.economy.food_stock, 0)

    def test_same_seed_full_simulation_determinism(self):
        a = generated_simulation(gen_seed=42, sim_seed=99, days=10)
        b = generated_simulation(gen_seed=42, sim_seed=99, days=10)
        a.run(days=10)
        b.run(days=10)
        self.assertEqual(snapshot(a), snapshot(b))

    def test_save_load_continuation_matches_continuous(self):
        wc, nc = generated_configs(seed=42)
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

    def test_generation_does_not_consume_sim_rng(self):
        a = generated_world(gen_seed=42, sim_seed=7, run_days=30, houses_per_settlement=5)
        b = generated_world(gen_seed=42, sim_seed=7, run_days=30, houses_per_settlement=20)
        self.assertEqual(a.rng.getstate(), b.rng.getstate())


if __name__ == "__main__":
    unittest.main()