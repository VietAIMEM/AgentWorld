import unittest

from world_sim.simulation.simulation import Simulation

from world_sim.tests.helpers import build_world, load_configs

SMALL_AGED = {
    "npcs": [
        {
            "id": "npc_001",
            "name": "Alice",
            "age": 28,
            "money": 60,
            "job": "farmer",
            "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5},
        },
        {
            "id": "npc_002",
            "name": "Bob",
            "age": 79,
            "money": 45,
            "job": "merchant",
            "personality": {"sociability": 0.4, "ambition": 0.5, "risk_tolerance": 0.4, "work_ethic": 0.7, "generosity": 0.6},
        },
        {
            "id": "npc_003",
            "name": "Carla",
            "age": 40,
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


def _old_age_world(max_age=80, enabled=True, aging=10):
    return build_world(
        world_config={"aging": {"days_per_year": aging}, "old_age": {"enabled": enabled, "max_age": max_age}},
        npcs_config=SMALL_AGED,
    )


def _sim(max_age, days=30, seed=42, aging=10, npcs=SMALL_AGED, extra=None):
    world_config, _ = load_configs()
    world_config["aging"] = {"days_per_year": aging}
    world_config["old_age"] = {"enabled": True, "max_age": max_age}
    if extra:
        world_config.update(extra)
    return Simulation(world_config, npcs, seed=seed, days=days, print_report=False)


class TestOldAgeDeath(unittest.TestCase):
    def test_disabled_by_default(self):
        world = build_world()
        self.assertFalse(world.old_age_enabled)
        _advance_days(world, 400)
        self.assertEqual(world.stats.deaths, 0)
        self.assertEqual(len(world.alive_npcs()), 20)

    def test_no_death_before_max_age(self):
        world = _old_age_world(max_age=80)
        bob = world.get_npc("npc_002")
        _advance_days(world, 9)
        self.assertEqual(bob.age, 79)
        self.assertTrue(bob.alive)
        self.assertEqual(world.stats.deaths, 0)

    def test_dies_exactly_at_threshold(self):
        world = _old_age_world(max_age=80)
        bob = world.get_npc("npc_002")
        _advance_days(world, 10)
        self.assertEqual(bob.age, 80)
        self.assertFalse(bob.alive)
        self.assertIn(bob, world.dead)
        self.assertEqual(world.stats.deaths, 1)
        self.assertEqual(world.stats.old_age_deaths, 1)

    def test_dead_npc_stops_aging(self):
        world = _old_age_world(max_age=80)
        bob = world.get_npc("npc_002")
        alice = world.get_npc("npc_001")
        _advance_days(world, 100)
        self.assertEqual(bob.age, 80)
        self.assertEqual(alice.age, 38)

    def test_dead_npc_stops_acting_earning_and_moving(self):
        sim = _sim(max_age=40)
        sim.run()
        dead = [npc for npc in sim.world.npcs if not npc.alive]
        self.assertGreaterEqual(len(dead), 2)
        alice = sim.world.get_npc("npc_001")
        for npc in dead:
            location, money, health, hunger = npc.location_id, npc.money, npc.needs.health, npc.needs.hunger
            food = npc.inventory.get("food", 0)
            for _ in range(24 * 6 * 5):
                sim.world.update_time()
                sim._tick()
            self.assertIsNone(npc.current_action)
            self.assertEqual(npc.location_id, location)
            self.assertEqual(npc.money, money)
            self.assertEqual(npc.needs.health, health)
            self.assertEqual(npc.needs.hunger, hunger)
            self.assertEqual(npc.inventory.get("food", 0), food)
        self.assertNotEqual(alice.money, 60)

    def test_dead_npc_does_not_consume_food(self):
        world = _old_age_world(max_age=40)
        _advance_days(world, 20)
        for npc in world.dead:
            self.assertEqual(npc.inventory.get("food", 0), 0)
            self.assertGreater(npc.needs.hunger, 0)

    def test_dead_npc_not_counted_in_alive_population(self):
        world = _old_age_world(max_age=40)
        _advance_days(world, 20)
        alive = world.alive_npcs()
        self.assertLess(len(alive), len(world.npcs))
        for npc in world.dead:
            self.assertNotIn(npc, alive)
        self.assertEqual(len(alive), len(world.npcs) - len(world.dead))

    def test_birth_replenishes_population_after_old_age_death(self):
        world_config, _ = load_configs()
        world_config["aging"] = {"days_per_year": 10}
        world_config["old_age"] = {"enabled": True, "max_age": 40}
        world_config["birth"] = {"enabled": True, "interval_days": 5, "max_population": 30}
        sim = Simulation(world_config, SMALL_AGED, seed=42, days=40, print_report=False)
        sim.run()
        self.assertGreater(sim.world.stats.deaths, 0)
        self.assertGreater(sim.world.stats.births, 0)
        self.assertEqual(
            len(sim.world.alive_npcs()),
            len(SMALL_AGED["npcs"]) - sim.world.stats.deaths + sim.world.stats.births,
        )
        for npc in sim.world.npcs:
            if npc.age == 0:
                self.assertTrue(npc.alive)

    def test_max_population_counts_alive_npcs(self):
        world_config, _ = load_configs()
        world_config["aging"] = {"days_per_year": 10}
        world_config["old_age"] = {"enabled": True, "max_age": 40}
        world_config["birth"] = {"enabled": True, "interval_days": 5, "max_population": 4}
        sim = Simulation(world_config, SMALL_AGED, seed=42, days=60, print_report=False)
        sim.run()
        self.assertLessEqual(len(sim.world.alive_npcs()), 4)
        self.assertEqual(len(sim.world.alive_npcs()), 4)

    def test_deterministic_old_age_death(self):
        def outcome(seed):
            sim = _sim(max_age=40, days=30, seed=seed)
            sim.run()
            return (
                sim.world.stats.deaths,
                sim.world.stats.old_age_deaths,
                sorted(npc.id for npc in sim.world.dead),
                sorted((npc.id, npc.age) for npc in sim.world.npcs),
            )

        self.assertEqual(outcome(42), outcome(42))
        self.assertEqual(outcome(1), outcome(99))

    def test_health_starvation_death_still_works(self):
        world_config, _ = load_configs()
        world_config["aging"] = {"days_per_year": 10}
        world_config["old_age"] = {"enabled": True, "max_age": 200}
        dying = {
            "npcs": [
                {"id": "npc_001", "name": "Alice", "age": 28, "money": 0, "hunger": 95, "health": 1.0, "job": "farmer"}
            ]
        }
        sim = Simulation(world_config, dying, seed=42, days=2, print_report=False)
        sim.run()
        dead = [npc for npc in sim.world.npcs if not npc.alive]
        self.assertEqual(len(dead), 1)
        self.assertLessEqual(dead[0].needs.health, 0.0)
        self.assertEqual(sim.world.stats.old_age_deaths, 0)
        self.assertEqual(sim.world.stats.deaths, 1)

    def test_no_invalid_goal_action_state_after_death(self):
        sim = _sim(max_age=40, days=30)
        sim.run()
        for npc in sim.world.npcs:
            if npc.alive:
                if npc.current_goal is not None and npc.current_action is not None:
                    self.assertIn(
                        npc.current_action.action_type,
                        VALID_GOAL_ACTION.get(npc.current_goal.type.value, set()),
                    )
            else:
                self.assertIsNone(npc.current_action)


if __name__ == "__main__":
    unittest.main()