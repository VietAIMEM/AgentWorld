import unittest

from world_sim.simulation.simulation import Simulation

from world_sim.tests.helpers import build_world, load_configs

SMALL_NPCS = {
    "npcs": [
        {
            "id": "npc_001",
            "name": "Alice",
            "age": 29,
            "money": 60,
            "job": "farmer",
            "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5},
        },
        {
            "id": "npc_002",
            "name": "Bob",
            "age": 41,
            "money": 45,
            "job": "merchant",
            "personality": {"sociability": 0.4, "ambition": 0.5, "risk_tolerance": 0.4, "work_ethic": 0.7, "generosity": 0.6},
        },
        {
            "id": "npc_003",
            "name": "Carla",
            "age": 34,
            "money": 55,
            "job": "worker",
            "personality": {"sociability": 0.6, "ambition": 0.6, "risk_tolerance": 0.2, "work_ethic": 0.8, "generosity": 0.7},
        },
    ]
}

VALID_GOAL_ACTION = {
    "eat": {"eat", "move", "buy_food"},
    "buy_food": {"buy_food", "move"},
    "sleep": {"sleep", "move"},
    "work": {"work", "move"},
    "earn_money": {"work", "move"},
    "socialize": {"socialize", "move", "rest"},
    "explore": {"explore", "move"},
    "rest": {"rest"},
    "seek_health": {"rest", "move"},
    "move": {"move"},
}


def _advance_days(world, days):
    for _ in range(days * 24 * (60 // world.clock.tick_minutes)):
        world.update_time()


def _birth_world(interval=10, max_pop=50, enabled=True, money=10.0):
    return build_world(
        world_config={
            "birth": {"enabled": enabled, "interval_days": interval, "max_population": max_pop, "money": money},
            "living_cost": {"enabled": False},
        }
    )


def _newborns(world):
    return [npc for npc in world.npcs if npc.age == 0]


def _run_birth_sim(seed, days=40, interval=10, max_pop=50):
    world_config, _ = load_configs()
    world_config["birth"] = {"enabled": True, "interval_days": interval, "max_population": max_pop}
    return Simulation(world_config, SMALL_NPCS, seed=seed, days=days, print_report=False)


class TestBirth(unittest.TestCase):
    def test_birth_occurs_at_configured_interval(self):
        world = _birth_world(interval=10)
        start = len(world.alive_npcs())
        _advance_days(world, 10)
        self.assertEqual(len(world.alive_npcs()), start + 1)
        self.assertEqual(world.stats.births, 1)
        _advance_days(world, 10)
        self.assertEqual(len(world.alive_npcs()), start + 2)
        self.assertEqual(world.stats.births, 2)

    def test_no_birth_before_configured_condition(self):
        world = _birth_world(interval=10)
        start = len(world.alive_npcs())
        _advance_days(world, 9)
        self.assertEqual(len(world.alive_npcs()), start)
        self.assertEqual(world.stats.births, 0)
        _advance_days(world, 1)
        self.assertEqual(len(world.alive_npcs()), start + 1)
        self.assertEqual(world.stats.births, 1)

    def test_births_disabled_by_default(self):
        world = build_world()
        start = len(world.alive_npcs())
        _advance_days(world, 200)
        self.assertEqual(len(world.alive_npcs()), start)
        self.assertEqual(world.stats.births, 0)

    def test_population_increases_correctly(self):
        world = _birth_world(interval=5)
        start = len(world.alive_npcs())
        _advance_days(world, 25)
        self.assertEqual(world.stats.births, 5)
        self.assertEqual(len(world.alive_npcs()), start + 5)

    def test_newborn_age_is_zero(self):
        world = _birth_world(interval=10)
        _advance_days(world, 20)
        self.assertEqual(len(_newborns(world)), 2)
        for baby in _newborns(world):
            self.assertEqual(baby.age, 0)

    def test_newborn_has_valid_state(self):
        world = _birth_world(interval=10)
        _advance_days(world, 10)
        baby = _newborns(world)[0]
        for value in (baby.needs.hunger, baby.needs.energy, baby.needs.social, baby.needs.health):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 100.0)
        self.assertGreaterEqual(baby.money, 0.0)
        self.assertIn(baby.location_id, world.locations)
        self.assertEqual(baby.location_id, baby.home_id)
        self.assertIn(baby.home_id, world.locations)
        self.assertIsNotNone(baby.job)
        self.assertIn(baby.job.id, {job["id"] for job in world.config["jobs"]})
        self.assertTrue(baby.alive)
        self.assertIn(baby, world.npcs)

    def test_newborn_has_unique_identity(self):
        world = _birth_world(interval=5)
        _advance_days(world, 40)
        ids = [npc.id for npc in world.npcs]
        names = [npc.name for npc in world.npcs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))

    def test_max_population_respected(self):
        initial_pop = len(build_world().alive_npcs())
        world = _birth_world(interval=10, max_pop=initial_pop + 2)
        max_observed = 0
        for _ in range(20):
            _advance_days(world, 10)
            max_observed = max(max_observed, len(world.alive_npcs()))
        self.assertLessEqual(max_observed, initial_pop + 2)
        self.assertEqual(len(world.alive_npcs()), initial_pop + 2)
        self.assertEqual(world.stats.births, 2)

    def test_existing_npcs_remain_unchanged(self):
        world = _birth_world(interval=10)
        existing = {
            npc.id: (npc.money, npc.age, tuple(npc.needs.__dict__.values())) for npc in world.npcs
        }
        _advance_days(world, 30)
        for npc in world.npcs:
            if npc.id in existing:
                self.assertEqual((npc.money, npc.age), (existing[npc.id][0], existing[npc.id][1]))
                self.assertEqual(tuple(npc.needs.__dict__.values()), existing[npc.id][2])

    def test_aging_continues_after_births(self):
        world = build_world(
            world_config={
                "aging": {"days_per_year": 30},
                "birth": {"enabled": True, "interval_days": 10, "max_population": 50},
            }
        )
        initial = {npc.id: npc.age for npc in world.npcs}
        _advance_days(world, 90)
        for npc in world.npcs:
            if npc.id in initial:
                self.assertEqual(npc.age, initial[npc.id] + 3)
        babies = [npc for npc in world.npcs if npc.id not in initial]
        self.assertEqual(len(babies), 9)
        self.assertEqual(babies[0].age, 3)
        self.assertEqual(babies[-1].age, 0)

    def test_deterministic_behavior_with_same_seed(self):
        first = _run_birth_sim(seed=42)
        first.run()
        second = _run_birth_sim(seed=42)
        second.run()
        self.assertEqual(first.world.stats.births, second.world.stats.births)
        self.assertEqual(first.world.stats.births, 4)
        self.assertEqual([npc.id for npc in first.world.npcs], [npc.id for npc in second.world.npcs])
        self.assertEqual([npc.name for npc in first.world.npcs], [npc.name for npc in second.world.npcs])

    def test_newborns_integrate_with_simulation(self):
        sim = _run_birth_sim(seed=42)
        sim.run()
        babies = _newborns(sim.world)
        self.assertGreaterEqual(len(babies), 4)
        for baby in babies:
            self.assertTrue(baby.alive)
            self.assertGreater(baby.needs.health, 0.0)
        self.assertEqual(sim.world.stats.deaths, 0)

    def test_different_seeds_keep_lifecycle_invariants(self):
        for seed in (1, 7, 99):
            sim = _run_birth_sim(seed=seed)
            sim.run()
            ids = [npc.id for npc in sim.world.npcs]
            names = [npc.name for npc in sim.world.npcs]
            self.assertEqual(len(ids), len(set(ids)), f"seed {seed} duplicate ids")
            self.assertEqual(len(names), len(set(names)), f"seed {seed} duplicate names")
            for npc in sim.world.npcs:
                self.assertGreaterEqual(npc.age, 0)
                for value in (npc.needs.hunger, npc.needs.energy, npc.needs.social, npc.needs.health):
                    self.assertGreaterEqual(value, 0.0, f"seed {seed} need below 0")
                    self.assertLessEqual(value, 100.0, f"seed {seed} need above 100")
            self.assertLessEqual(len(sim.world.alive_npcs()), 50)
            self.assertGreater(sim.world.stats.births, 0)
            for npc in sim.world.alive_npcs():
                if npc.current_goal is not None and npc.current_action is not None:
                    self.assertIn(
                        npc.current_action.action_type,
                        VALID_GOAL_ACTION.get(npc.current_goal.type.value, set()),
                        f"seed {seed} invalid goal/action combo",
                    )


if __name__ == "__main__":
    unittest.main()
