import unittest

from world_sim.actions.movement import MoveAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.goals import Goal, GoalType
from world_sim.npc.memory import Memory, MemoryEntry

from world_sim.tests.helpers import build_world, first_npc


class TestMemory(unittest.TestCase):
    def test_adds_and_retrieves_entries(self):
        memory = Memory(max_size=10)
        memory.add(MemoryEntry("Day 1 06:00", "ate", "Ate food", 3.0, "food"))
        memory.add(MemoryEntry("Day 1 07:00", "worked", "Worked hard", 4.0, "farm"))
        self.assertEqual(len(memory), 2)
        self.assertEqual(len(memory.recent("worked")), 1)

    def test_prunes_low_importance_entries(self):
        memory = Memory(max_size=3)
        memory.add(MemoryEntry("Day 1", "met_npc", "low", 1.0, "bob"))
        memory.add(MemoryEntry("Day 2", "worked", "high", 9.0, "farm"))
        memory.add(MemoryEntry("Day 3", "ate", "mid", 5.0, "food"))
        memory.add(MemoryEntry("Day 4", "slept", "mid2", 6.0, "home"))
        self.assertEqual(len(memory), 3)
        importances = {entry.importance for entry in memory}
        self.assertNotIn(1.0, importances)
        self.assertIn(9.0, importances)


class TestInventory(unittest.TestCase):
    def setUp(self):
        self.npc = first_npc(build_world())

    def test_add_and_consume_resource(self):
        self.assertFalse(self.npc.has_resource("food"))
        self.npc.add_resource("food", 2)
        self.assertTrue(self.npc.has_resource("food"))
        self.assertTrue(self.npc.consume_resource("food", 1))
        self.assertEqual(self.npc.inventory["food"], 1)
        self.assertTrue(self.npc.consume_resource("food", 1))
        self.assertFalse(self.npc.has_resource("food"))

    def test_cannot_consume_more_than_owned(self):
        self.npc.add_resource("food", 1)
        self.assertFalse(self.npc.consume_resource("food", 2))
        self.assertEqual(self.npc.inventory["food"], 1)


class TestPersonality(unittest.TestCase):
    def test_values_are_clamped_to_unit_range(self):
        from world_sim.npc.personality import Personality

        p = Personality(sociability=1.5, ambition=-1.0)
        self.assertEqual(p.sociability, 1.0)
        self.assertEqual(p.ambition, 0.0)


class TestMoveAction(unittest.TestCase):
    def test_moves_along_connected_path(self):
        world = build_world()
        npc = first_npc(world)
        npc.location_id = "home"
        decision = Decision(Goal(GoalType.MOVE, 10.0, "tavern"), "move", 10.0, target_location_id="tavern")
        action = MoveAction(world.rng, world.config, decision)
        self.assertTrue(action.can_execute(npc, world))
        action.start(npc, world)
        action.tick(npc, world)
        self.assertEqual(npc.location_id, "market")
        action.tick(npc, world)
        self.assertEqual(npc.location_id, "tavern")
        self.assertTrue(action.is_complete(npc, world))

    def test_path_found_via_graph_traversal(self):
        world = build_world()
        npc = first_npc(world)
        npc.location_id = "home"
        decision = Decision(Goal(GoalType.MOVE, 10.0, "forest"), "move", 10.0, target_location_id="forest")
        action = MoveAction(world.rng, world.config, decision)
        self.assertTrue(action.can_execute(npc, world))
        action.start(npc, world)
        self.assertEqual(action.path, ["market", "farm", "forest"])

    def test_unknown_target_cannot_execute(self):
        world = build_world()
        npc = first_npc(world)
        decision = Decision(Goal(GoalType.MOVE, 10.0, "nowhere"), "move", 10.0, target_location_id="nowhere")
        action = MoveAction(world.rng, world.config, decision)
        self.assertFalse(action.can_execute(npc, world))


class TestPerception(unittest.TestCase):
    def test_perceives_nearby_npcs_resources_and_connections(self):
        from world_sim.npc.perception import PerceptionSystem

        world = build_world()
        npc = first_npc(world)
        npc.location_id = "market"
        other = world.npcs[1]
        other.location_id = "market"
        perception = PerceptionSystem().perceive(npc, world)
        self.assertEqual(len(perception.nearby_npcs), 1)
        self.assertEqual(perception.nearby_npcs[0].id, other.id)
        resource_ids = {resource.id for resource in perception.available_resources}
        self.assertIn("food", resource_ids)
        connected_ids = {location.id for location in perception.connected_locations}
        self.assertTrue({"home", "farm", "tavern"}.issubset(connected_ids))

    def test_does_not_perceive_others_elsewhere(self):
        from world_sim.npc.perception import PerceptionSystem

        world = build_world(
            npcs_config={
                "npcs": [
                    {
                        "id": "npc_001",
                        "name": "Alice",
                        "age": 29,
                        "money": 60,
                        "job": "farmer",
                    },
                    {
                        "id": "npc_002",
                        "name": "Bob",
                        "age": 41,
                        "money": 45,
                        "job": "merchant",
                    },
                ]
            }
        )
        npc = world.npcs[0]
        npc.location_id = "home"
        other = world.npcs[1]
        other.location_id = "farm"
        perception = PerceptionSystem().perceive(npc, world)
        self.assertEqual(perception.nearby_npcs, [])


class TestEconomy(unittest.TestCase):
    def test_can_buy_food_when_money_and_stock_available(self):
        world = build_world()
        npc = first_npc(world)
        npc.location_id = "market"
        npc.money = 50.0
        world.economy.food_stock = 10
        world.economy.open_hour = 6
        world.clock.hour = 10
        self.assertTrue(world.economy.can_buy_food(npc, world))

    def test_cannot_buy_without_money_or_stock(self):
        world = build_world()
        npc = first_npc(world)
        npc.money = 1.0
        world.economy.food_stock = 5
        self.assertFalse(world.economy.can_buy_food(npc, world))
        npc.money = 50.0
        world.economy.food_stock = 0
        self.assertFalse(world.economy.can_buy_food(npc, world))

    def test_buy_food_deducts_money_and_stock(self):
        world = build_world()
        npc = first_npc(world)
        npc.money = 20.0
        stock = world.economy.food_stock = 7
        self.assertTrue(world.economy.buy_food(npc, world))
        self.assertEqual(npc.money, 20.0 - world.resources["food"].price)
        self.assertEqual(world.economy.food_stock, stock - 1)

    def test_shop_hours_control_open_state(self):
        world = build_world()
        world.clock.hour = 3
        self.assertFalse(world.is_shop_open())
        world.clock.hour = 12
        self.assertTrue(world.is_shop_open())


if __name__ == "__main__":
    unittest.main()