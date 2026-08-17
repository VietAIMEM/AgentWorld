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


def _advance_days(world, days):
    for _ in range(days * 24 * (60 // world.clock.tick_minutes)):
        world.update_time()


class TestAging(unittest.TestCase):
    def test_age_progresses_with_simulation_time(self):
        world = build_world()
        initial = {npc.id: npc.age for npc in world.npcs}
        _advance_days(world, 366)
        for npc in world.npcs:
            self.assertEqual(npc.age, initial[npc.id] + 1)

    def test_no_age_increase_before_a_full_year(self):
        world = build_world()
        initial = {npc.id: npc.age for npc in world.npcs}
        _advance_days(world, 364)
        for npc in world.npcs:
            self.assertEqual(npc.age, initial[npc.id])
        _advance_days(world, 1)
        for npc in world.npcs:
            self.assertEqual(npc.age, initial[npc.id] + 1)

    def test_age_increases_once_per_year_across_many_days(self):
        world = build_world(world_config={"aging": {"days_per_year": 100}})
        initial = {npc.id: npc.age for npc in world.npcs}
        _advance_days(world, 250)
        for npc in world.npcs:
            self.assertEqual(npc.age, initial[npc.id] + 2)

    def test_deterministic_aging_with_same_seed(self):
        def ages(seed):
            world_config, _ = load_configs()
            world_config["aging"] = {"days_per_year": 30}
            sim = Simulation(world_config, SMALL_NPCS, seed=seed, days=60, print_report=False)
            sim.run()
            return [npc.age for npc in sim.world.npcs]

        self.assertEqual(ages(42), ages(42))
        self.assertEqual(ages(42), [31, 43, 36])

    def test_aging_is_independent_of_seed(self):
        def ages(seed):
            world_config, _ = load_configs()
            world_config["aging"] = {"days_per_year": 30}
            sim = Simulation(world_config, SMALL_NPCS, seed=seed, days=60, print_report=False)
            sim.run()
            return [npc.age for npc in sim.world.npcs]

        self.assertEqual(ages(1), ages(99))

    def test_aging_integrates_with_full_simulation(self):
        world_config, _ = load_configs()
        world_config["aging"] = {"days_per_year": 30}
        sim = Simulation(world_config, SMALL_NPCS, seed=42, days=60, print_report=False)
        sim.run()
        self.assertEqual([npc.age for npc in sim.world.npcs], [31, 43, 36])

    def test_different_npcs_age_consistently(self):
        world = build_world()
        initial = {npc.id: npc.age for npc in world.npcs}
        self.assertGreater(len({initial[npc.id] for npc in world.npcs}), 1)
        _advance_days(world, 366)
        for npc in world.npcs:
            self.assertEqual(npc.age, initial[npc.id] + 1)

    def test_aging_does_not_alter_needs(self):
        world = build_world(world_config={"aging": {"days_per_year": 1}})
        needs_before = [
            (npc.needs.hunger, npc.needs.energy, npc.needs.social, npc.needs.health) for npc in world.npcs
        ]
        _advance_days(world, 5)
        needs_after = [(npc.needs.hunger, npc.needs.energy, npc.needs.social, npc.needs.health) for npc in world.npcs]
        self.assertEqual(needs_before, needs_after)
        for npc in world.npcs:
            self.assertGreater(npc.age, 0)

    def test_dead_npcs_do_not_age(self):
        world = build_world(world_config={"aging": {"days_per_year": 10}})
        initial = {npc.id: npc.age for npc in world.npcs}
        dead = world.npcs[0]
        dead.alive = False
        _advance_days(world, 25)
        self.assertEqual(dead.age, initial[dead.id])
        for npc in world.npcs[1:]:
            self.assertEqual(npc.age, initial[npc.id] + 2)

    def test_age_is_monotonic(self):
        world = build_world(world_config={"aging": {"days_per_year": 7}})
        previous = {npc.id: npc.age for npc in world.npcs}
        for _ in range(5):
            _advance_days(world, 7)
            for npc in world.npcs:
                self.assertGreaterEqual(npc.age, previous[npc.id])
                previous[npc.id] = npc.age


if __name__ == "__main__":
    unittest.main()
