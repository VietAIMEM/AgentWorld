import unittest

from world_sim.npc.needs import Needs, NeedsSystem, clamp, money_need

from world_sim.tests.helpers import build_world, first_npc


class TestNeedsSystem(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_hunger_increases_with_time(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 50.0
        NeedsSystem(self.world.config).update(npc, self.world)
        self.assertGreater(npc.needs.hunger, 50.0)

    def test_energy_decreases_with_time(self):
        npc = first_npc(self.world)
        npc.needs.energy = 50.0
        NeedsSystem(self.world.config).update(npc, self.world)
        self.assertLess(npc.needs.energy, 50.0)

    def test_hunger_clamps_at_upper_bound(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 99.9
        for _ in range(100):
            NeedsSystem(self.world.config).update(npc, self.world)
        self.assertLessEqual(npc.needs.hunger, 100.0)

    def test_health_declines_when_starving(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 95.0
        npc.needs.health = 50.0
        NeedsSystem(self.world.config).update(npc, self.world)
        self.assertLess(npc.needs.health, 50.0)

    def test_health_recovers_when_safe(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 20.0
        npc.needs.energy = 80.0
        npc.needs.health = 50.0
        NeedsSystem(self.world.config).update(npc, self.world)
        self.assertGreater(npc.needs.health, 50.0)

    def test_clamp(self):
        self.assertEqual(clamp(150.0, 0.0, 100.0), 100.0)
        self.assertEqual(clamp(-5.0, 0.0, 100.0), 0.0)
        self.assertEqual(clamp(42.0, 0.0, 100.0), 42.0)

    def test_money_need_mapping(self):
        self.assertEqual(money_need(0.0), 100.0)
        self.assertEqual(money_need(50.0), 50.0)
        self.assertEqual(money_need(150.0), 0.0)


if __name__ == "__main__":
    unittest.main()