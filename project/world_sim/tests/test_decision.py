import random
import unittest

from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.goals import GoalType
from world_sim.npc.perception import PerceptionSystem

from world_sim.tests.helpers import build_world, first_npc, set_time


def _decide(world, npc):
    ds = RuleBasedDecisionSystem(world.config, random.Random(3))
    perception = PerceptionSystem().perceive(npc, world)
    return ds.decide(npc, perception, world)


class TestHighHungerRule(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_hungry_at_market_buys_food(self):
        npc = first_npc(self.world)
        npc.location_id = "market"
        npc.needs.hunger = 95.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "buy_food")

    def test_hungry_with_food_inventory_eats(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 95.0
        npc.add_resource("food", 2)
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "eat")

    def test_hungry_away_from_market_moves(self):
        npc = first_npc(self.world)
        npc.location_id = "farm"
        npc.needs.hunger = 95.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "market")

    def test_not_hungry_gives_no_eat_goal(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 30.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertNotEqual(decision.goal.type.value, "eat")


class TestLowEnergyRule(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_low_energy_at_home_sleeps(self):
        npc = first_npc(self.world)
        npc.needs.energy = 10.0
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "sleep")

    def test_low_energy_away_moves_home(self):
        npc = first_npc(self.world)
        npc.location_id = "farm"
        npc.needs.energy = 10.0
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "home")


class TestLowMoneyRule(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_low_money_at_work_location_works(self):
        npc = first_npc(self.world)
        npc.money = 5.0
        npc.location_id = npc.job.work_location
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "work")


class TestLowHealthRule(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_critical_health_moves_home(self):
        npc = first_npc(self.world)
        npc.needs.health = 10.0
        npc.location_id = "market"
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "home")

    def test_critical_health_at_home_rests(self):
        npc = first_npc(self.world)
        npc.needs.health = 10.0
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "rest")


class TestDefaultActivityRule(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_healthy_npc_works_during_work_hours(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.location_id = npc.job.work_location
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "work")

    def test_moderate_hunger_does_not_eat(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 75.0
        npc.needs.energy = 95.0
        npc.location_id = npc.job.work_location
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertNotEqual(decision.goal.type, GoalType.EAT)
        npc.location_id = npc.home_id
        set_time(self.world, 7)
        decision = _decide(self.world, npc)
        self.assertNotEqual(decision.goal.type, GoalType.EAT)

    def test_lazy_npc_rests_in_early_morning(self):
        npc = first_npc(self.world)
        npc.personality.sociability = 0.2
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.1
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        set_time(self.world, 7)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "rest")

    def test_industrious_npc_does_not_start_work_early(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        set_time(self.world, 7)
        decision = _decide(self.world, npc)
        self.assertNotEqual(decision.goal.type, GoalType.WORK)
        set_time(self.world, 8)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, npc.job.work_location)

    def test_sociable_npc_socializes_in_morning(self):
        npc = first_npc(self.world)
        npc.personality.sociability = 0.9
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.5
        npc.needs.hunger = 30.0
        npc.needs.energy = 95.0
        npc.needs.social = 20.0
        set_time(self.world, 7)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "socialize")
        self.assertIsNotNone(decision.target_npc_id)

    def test_personality_changes_morning_preference(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        npc.personality.sociability = 0.2
        npc.personality.ambition = 0.8
        npc.personality.work_ethic = 0.9
        npc.personality.risk_tolerance = 0.3
        set_time(self.world, 7)
        industrious = _decide(self.world, npc)
        self.assertNotEqual(industrious.goal.type, GoalType.WORK)
        self.assertEqual(industrious.goal.type, GoalType.EXPLORE)

        npc.personality.sociability = 0.9
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.5
        sociable = _decide(self.world, npc)
        self.assertEqual(sociable.goal.type, GoalType.SOCIALIZE)
        self.assertNotEqual(industrious.goal.type, sociable.goal.type)


class TestActionPersistence(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def _decision(self, npc):
        from world_sim.npc.perception import PerceptionSystem

        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        perception = PerceptionSystem().perceive(npc, self.world)
        return ds.decide(npc, perception, self.world)

    def test_current_action_kept_when_decision_unchanged(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        set_time(self.world, 10)
        decision = self._decision(npc)
        self.assertEqual(decision.action_type, "work")
        manager = ActionManager(random.Random(3), self.world.config)
        first = manager.update(npc, decision, self.world)
        second = manager.update(npc, decision, self.world)
        self.assertIs(first, second)

    def test_completed_action_is_not_restarted(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        set_time(self.world, 10)
        decision = self._decision(npc)
        manager = ActionManager(random.Random(3), self.world.config)
        action = manager.update(npc, decision, self.world)
        action.ticks_elapsed = action.shift_ticks
        self.assertTrue(action.is_complete(npc, self.world))
        next_action = manager.update(npc, decision, self.world)
        self.assertIsNot(action, next_action)

    def test_normal_decision_cannot_cancel_active_action(self):
        from world_sim.actions.action import ActionManager
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        set_time(self.world, 10)
        work_decision = self._decision(npc)
        self.assertEqual(work_decision.action_type, "work")
        manager = ActionManager(random.Random(3), self.world.config)
        manager.update(npc, work_decision, self.world)
        social = Decision(goal=Goal(GoalType.SOCIALIZE, 5.0), action_type="socialize", priority=5.0)
        action = manager.update(npc, social, self.world)
        self.assertEqual(action.action_type, "work")

    def test_urgent_decision_overrides_active_action(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        set_time(self.world, 10)
        work_decision = self._decision(npc)
        manager = ActionManager(random.Random(3), self.world.config)
        manager.update(npc, work_decision, self.world)
        npc.location_id = "farm"
        npc.needs.hunger = 96.0
        npc.money = 50.0
        urgent = self._decision(npc)
        self.assertTrue(urgent.urgent)
        self.assertEqual(urgent.goal.type, GoalType.EAT)
        action = manager.update(npc, urgent, self.world)
        self.assertEqual(action.action_type, "move")
        self.assertEqual(action.target, "market")


class TestCommitment(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_committed_goal_is_continued(self):
        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        npc.needs.social = 10.0
        npc.current_goal = None
        preferred = _decide(self.world, npc)
        self.assertNotEqual(preferred.goal.type, GoalType.WORK)
        npc.current_goal = decision.goal
        npc.current_goal.started_tick = self.world.clock.tick
        continued = _decide(self.world, npc)
        self.assertEqual(continued.goal.type, GoalType.WORK)
        self.assertEqual(npc.current_goal.type, GoalType.WORK)

    def test_emergency_overrides_commitment(self):
        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        npc.current_goal = decision.goal
        npc.current_goal.started_tick = self.world.clock.tick
        npc.needs.hunger = 96.0
        npc.location_id = "farm"
        emergency = _decide(self.world, npc)
        self.assertTrue(emergency.urgent)
        self.assertEqual(emergency.goal.type, GoalType.EAT)


class TestSocialNoBounce(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def _decision(self, npc):
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        perception = PerceptionSystem().perceive(npc, self.world)
        return ds.decide(npc, perception, self.world)

    def test_at_social_location_with_no_nearby_rests(self):
        npc = first_npc(self.world)
        npc.location_id = "tavern"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(self.world, 12)
        decision = self._decision(npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "rest")

    def test_not_at_social_location_moves_to_tavern_not_market(self):
        npc = first_npc(self.world)
        npc.location_id = "market"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(self.world, 12)
        decision = self._decision(npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "tavern")


class TestBuyFoodOnePerTick(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_buys_one_per_apply(self):
        from world_sim.actions.eating import BuyFoodAction

        npc = first_npc(self.world)
        npc.location_id = "market"
        npc.needs.hunger = 96.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "buy_food")
        action = BuyFoodAction(random.Random(3), self.world.config, decision)
        action.apply(npc, self.world)
        self.assertEqual(npc.inventory.get("food", 0), 1)
        action.apply(npc, self.world)
        self.assertEqual(npc.inventory.get("food", 0), 2)


class TestEatOnce(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_eat_action_executes_exactly_once(self):
        from world_sim.actions.eating import EatAction

        npc = first_npc(self.world)
        npc.needs.hunger = 100.0
        npc.add_resource("food", 3)
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "eat")
        action = EatAction(random.Random(3), self.world.config, decision)
        action.tick(npc, self.world)
        self.assertEqual(npc.inventory.get("food", 0), 2)
        self.assertEqual(npc.needs.hunger, 20.0)
        self.assertTrue(action.is_complete(npc, self.world))
        action.tick(npc, self.world)
        self.assertEqual(npc.inventory.get("food", 0), 2)
        self.assertEqual(npc.needs.hunger, 20.0)


class TestCommittedEatDoesNotRepeat(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_committed_eat_goal_does_not_force_second_meal(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 100.0
        npc.add_resource("food", 3)
        npc.money = 50.0
        set_time(self.world, 12)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        manager = ActionManager(random.Random(3), self.world.config)
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        action = manager.update(npc, decision, self.world)
        action.tick(npc, self.world)
        self.assertEqual(npc.inventory.get("food", 0), 2)
        self.assertIsNotNone(npc.current_goal.started_tick)
        for _ in range(4):
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            self.assertNotEqual(decision.goal.type, GoalType.EAT)
            manager.update(npc, decision, self.world)
            self.assertEqual(npc.inventory.get("food", 0), 2)


class TestEatGoalActionConsistency(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_eat_goal_never_uses_rest_action(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 100.0
        npc.money = 50.0
        set_time(self.world, 12)
        decisions = []
        npc.location_id = "home"
        npc.inventory.pop("food", None)
        decisions.append(_decide(self.world, npc))
        npc.add_resource("food", 2)
        decisions.append(_decide(self.world, npc))
        npc.inventory["food"] = 0
        npc.location_id = "market"
        decisions.append(_decide(self.world, npc))
        npc.location_id = "farm"
        npc.inventory.pop("food", None)
        decisions.append(_decide(self.world, npc))
        for decision in decisions:
            self.assertEqual(decision.goal.type, GoalType.EAT)
            self.assertIn(decision.action_type, ("eat", "move", "buy_food"))
            self.assertNotEqual(decision.action_type, "rest")

    def test_eat_goal_cannot_have_work_action(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 100.0
        npc.money = 50.0
        npc.inventory.pop("food", None)
        npc.location_id = npc.job.work_location
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        self.assertNotEqual(decision.action_type, "work")

    def test_stale_rest_action_under_eat_is_replaced(self):
        from world_sim.actions.action import ActionManager
        from world_sim.actions.resting import RestAction
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 96.0
        npc.money = 50.0
        npc.add_resource("food", 2)
        set_time(self.world, 12)
        eat_goal = Goal(GoalType.EAT, 50.0)
        eat_goal.started_tick = self.world.clock.tick
        npc.current_goal = eat_goal
        npc.current_action = RestAction(random.Random(3), self.world.config, None)
        manager = ActionManager(random.Random(3), self.world.config)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        action = manager.update(npc, decision, self.world)
        self.assertNotEqual(action.action_type, "rest")
        self.assertIn(action.action_type, ("eat", "move", "buy_food"))
        self.assertEqual(npc.current_goal.type, GoalType.EAT)


class TestHungerEmergencyFlow(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_hunger_emergency_resolves(self):
        from world_sim.actions.action import ActionManager
        from world_sim.npc.needs import NeedsSystem

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.money = 50.0
        npc.inventory.pop("food", None)
        npc.needs.hunger = 100.0
        set_time(self.world, 6)
        manager = ActionManager(random.Random(3), self.world.config)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        needs = NeedsSystem(self.world.config)
        saw_eat = False
        for _ in range(60):
            self.world.update_time()
            needs.update(npc, self.world)
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            action = manager.update(npc, decision, self.world)
            action.tick(npc, self.world)
            if action.action_type == "eat":
                saw_eat = True
                break
        self.assertTrue(saw_eat)
        self.assertLess(npc.needs.hunger, 50.0)


class TestCompletedEatActionNotPreserved(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_completed_eat_action_is_not_preserved(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 100.0
        npc.add_resource("food", 3)
        npc.money = 50.0
        set_time(self.world, 12)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        manager = ActionManager(random.Random(3), self.world.config)
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        self.assertEqual(decision.action_type, "eat")
        action = manager.update(npc, decision, self.world)
        action.tick(npc, self.world)
        self.assertTrue(action.is_complete(npc, self.world))
        perception = PerceptionSystem().perceive(npc, self.world)
        decision2 = ds.decide(npc, perception, self.world)
        action2 = manager.update(npc, decision2, self.world)
        self.assertIsNot(action, action2)
        self.assertEqual(npc.inventory.get("food", 0), 2)


class TestEatGoalReleasedAfterSatisfied(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_eat_goal_released_once_hunger_satisfied(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 100.0
        npc.add_resource("food", 3)
        set_time(self.world, 12)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        manager = ActionManager(random.Random(3), self.world.config)
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        action = manager.update(npc, decision, self.world)
        action.tick(npc, self.world)
        self.assertLessEqual(npc.needs.hunger, 80.0)
        self.assertTrue(action.is_complete(npc, self.world))
        perception = PerceptionSystem().perceive(npc, self.world)
        next_decision = ds.decide(npc, perception, self.world)
        self.assertNotEqual(next_decision.goal.type, GoalType.EAT)


class TestFinalStateInvariants(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_eat_goal_forbids_non_food_actions(self):
        forbidden = ("rest", "work", "socialize", "explore", "sleep")
        npc = first_npc(self.world)
        npc.needs.hunger = 100.0
        npc.money = 50.0
        set_time(self.world, 12)
        cases = (("home", True), ("home", False), ("market", False), ("farm", False))
        for location, has_food in cases:
            npc.location_id = location
            if has_food:
                npc.add_resource("food", 2)
            else:
                npc.inventory.pop("food", None)
            decision = _decide(self.world, npc)
            self.assertEqual(decision.goal.type, GoalType.EAT)
            self.assertNotIn(decision.action_type, forbidden)
            self.assertIn(decision.action_type, ("eat", "move", "buy_food"))

    def test_above_threshold_eventually_obtains_food(self):
        from world_sim.actions.action import ActionManager
        from world_sim.npc.needs import NeedsSystem

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.money = 50.0
        npc.inventory.pop("food", None)
        npc.needs.hunger = 85.0
        set_time(self.world, 6)
        manager = ActionManager(random.Random(3), self.world.config)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        needs = NeedsSystem(self.world.config)
        saw_eat = False
        for _ in range(60):
            self.world.update_time()
            needs.update(npc, self.world)
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            action = manager.update(npc, decision, self.world)
            action.tick(npc, self.world)
            if action.action_type == "eat":
                saw_eat = True
                break
            if decision.goal.type is GoalType.EAT:
                self.assertIn(action.action_type, ("eat", "move", "buy_food"))
        self.assertTrue(saw_eat)


class TestWorkSchedule(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_work_does_not_start_outside_window(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        for hour in (6, 7, 17, 20, 21, 22):
            set_time(self.world, hour)
            npc.location_id = "home"
            decision = _decide(self.world, npc)
            self.assertNotEqual(
                decision.goal.type,
                GoalType.WORK,
                f"WORK must not start at hour {hour}",
            )

    def test_work_preferred_inside_window(self):
        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        self.assertEqual(decision.action_type, "work")

    def test_active_work_not_cancelled_at_window_boundary(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "work")
        manager = ActionManager(random.Random(3), self.world.config)
        manager.update(npc, decision, self.world)
        set_time(self.world, 17)
        decision = _decide(self.world, npc)
        action = manager.update(npc, decision, self.world)
        self.assertEqual(action.action_type, "work")

    def test_urgent_hunger_interrupts_work(self):
        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 96.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertTrue(decision.urgent)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        self.assertNotEqual(decision.action_type, "work")


class TestNightSleep(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_night_high_energy_sleeps_not_rests(self):
        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 30.0
        npc.needs.energy = 95.0
        npc.needs.social = 60.0
        set_time(self.world, 23)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.SLEEP)
        self.assertEqual(decision.action_type, "sleep")

    def test_night_low_energy_sleeps(self):
        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 30.0
        npc.needs.energy = 50.0
        npc.needs.social = 60.0
        set_time(self.world, 23)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.SLEEP)
        self.assertEqual(decision.action_type, "sleep")

    def test_daytime_rest_beats_sleep(self):
        npc = first_npc(self.world)
        npc.personality.sociability = 0.2
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.1
        npc.location_id = "home"
        npc.needs.hunger = 30.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        set_time(self.world, 7)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "rest")
        self.assertNotEqual(decision.action_type, "sleep")

    def test_urgent_hunger_overrides_sleep(self):
        npc = first_npc(self.world)
        npc.location_id = "farm"
        npc.needs.hunger = 96.0
        npc.needs.energy = 95.0
        npc.money = 50.0
        set_time(self.world, 22)
        decision = _decide(self.world, npc)
        self.assertTrue(decision.urgent)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "market")

    def test_sleep_goal_released_when_energy_satisfied(self):
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.personality.sociability = 0.2
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.1
        npc.location_id = "home"
        npc.needs.hunger = 30.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        set_time(self.world, 6)
        sleep_goal = Goal(GoalType.SLEEP, 20.0)
        sleep_goal.started_tick = self.world.clock.tick
        npc.current_goal = sleep_goal
        decision = _decide(self.world, npc)
        self.assertNotEqual(decision.goal.type, GoalType.SLEEP)

    def test_sleep_does_not_thrash_at_night(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.needs.social = 60.0
        set_time(self.world, 23)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        manager = ActionManager(random.Random(3), self.world.config)
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        self.assertEqual(decision.goal.type, GoalType.SLEEP)
        action = manager.update(npc, decision, self.world)
        self.assertEqual(action.action_type, "sleep")
        for _ in range(10):
            self.world.update_time()
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            action = manager.update(npc, decision, self.world)
            self.assertEqual(action.action_type, "sleep")


class TestLowFoodStockRule(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_night_eats_from_inventory_without_market_trip(self):
        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 90.0
        npc.add_resource("food", 2)
        set_time(self.world, 23)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.action_type, "eat")
        self.assertNotEqual(decision.target_location_id, "market")

    def test_closed_shop_no_food_no_repeated_market_travel(self):
        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 70.0
        npc.money = 50.0
        set_time(self.world, 23)
        decision = _decide(self.world, npc)
        self.assertNotEqual(decision.action_type, "move")
        self.assertNotEqual(decision.goal.type, GoalType.BUY_FOOD)

    def test_replenishes_reserve_when_shop_open(self):
        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.hunger = 65.0
        npc.money = 50.0
        set_time(self.world, 21)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.BUY_FOOD)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "market")

    def test_at_market_buys_when_stock_low(self):
        npc = first_npc(self.world)
        npc.location_id = "market"
        npc.needs.hunger = 65.0
        npc.money = 50.0
        set_time(self.world, 21)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.BUY_FOOD)
        self.assertEqual(decision.action_type, "buy_food")

    def test_urgent_hunger_overrides_low_food_stock(self):
        npc = first_npc(self.world)
        npc.location_id = "farm"
        npc.needs.hunger = 96.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertTrue(decision.urgent)
        self.assertEqual(decision.goal.type, GoalType.EAT)
        self.assertNotEqual(decision.goal.type, GoalType.BUY_FOOD)


class TestExploreReachesForest(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def _explore_decision(self, npc):
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        npc.personality.sociability = 0.2
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.9
        set_time(self.world, 7)
        return _decide(self.world, npc)

    def test_home_explore_moves_to_forest(self):
        npc = first_npc(self.world)
        npc.location_id = "home"
        decision = self._explore_decision(npc)
        self.assertEqual(decision.goal.type, GoalType.EXPLORE)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "forest")

    def test_market_explore_moves_to_forest(self):
        npc = first_npc(self.world)
        npc.location_id = "market"
        decision = self._explore_decision(npc)
        self.assertEqual(decision.goal.type, GoalType.EXPLORE)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "forest")

    def test_tavern_explore_moves_toward_nature(self):
        npc = first_npc(self.world)
        npc.location_id = "tavern"
        decision = self._explore_decision(npc)
        self.assertEqual(decision.goal.type, GoalType.EXPLORE)
        self.assertEqual(decision.action_type, "move")

    def test_forest_explore_forages_in_place(self):
        npc = first_npc(self.world)
        npc.location_id = "forest"
        decision = self._explore_decision(npc)
        self.assertEqual(decision.goal.type, GoalType.EXPLORE)
        self.assertEqual(decision.action_type, "explore")

    def test_explore_does_not_cancel_active_work(self):
        from world_sim.actions.action import ActionManager
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        set_time(self.world, 10)
        work_decision = _decide(self.world, npc)
        self.assertEqual(work_decision.action_type, "work")
        manager = ActionManager(random.Random(3), self.world.config)
        manager.update(npc, work_decision, self.world)
        explore_decision = Decision(
            goal=Goal(GoalType.EXPLORE, 20.0),
            action_type="explore",
            priority=20.0,
        )
        action = manager.update(npc, explore_decision, self.world)
        self.assertEqual(action.action_type, "work")

    def _explore_sim(self, npc):
        from world_sim.actions.action import ActionManager

        npc.needs.hunger = 10.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        npc.personality.sociability = 0.2
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.9
        set_time(self.world, 7)
        return (
            RuleBasedDecisionSystem(self.world.config, random.Random(3)),
            ActionManager(random.Random(3), self.world.config),
        )

    def test_npc_reaches_forest_from_market_through_graph(self):
        npc = first_npc(self.world)
        npc.location_id = "market"
        ds, manager = self._explore_sim(npc)
        arrived = False
        for _ in range(20):
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            self.assertEqual(decision.goal.type, GoalType.EXPLORE)
            action = manager.update(npc, decision, self.world)
            action.tick(npc, self.world)
            if npc.location_id == "forest":
                arrived = True
                break
        self.assertTrue(arrived)

    def test_npc_reaches_forest_from_home_through_graph(self):
        npc = first_npc(self.world)
        npc.location_id = "home"
        ds, manager = self._explore_sim(npc)
        arrived = False
        for _ in range(20):
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            self.assertEqual(decision.goal.type, GoalType.EXPLORE)
            action = manager.update(npc, decision, self.world)
            action.tick(npc, self.world)
            if npc.location_id == "forest":
                arrived = True
                break
        self.assertTrue(arrived)

    def test_explore_move_not_restarted_while_transiting(self):
        npc = first_npc(self.world)
        npc.location_id = "market"
        ds, manager = self._explore_sim(npc)
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        first = manager.update(npc, decision, self.world)
        self.assertEqual(first.action_type, "move")
        while npc.location_id != "forest":
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            self.assertEqual(decision.goal.type, GoalType.EXPLORE)
            action = manager.update(npc, decision, self.world)
            self.assertIs(action, first)
            action.tick(npc, self.world)


class TestEveningSocialTavern(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def _social(self, npc):
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        return _decide(self.world, npc)

    def test_evening_at_home_alone_moves_toward_tavern(self):
        npcs = {
            "npcs": [
                {"id": "npc_001", "name": "Alice", "age": 29, "money": 60, "job": "farmer",
                 "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5}},
                {"id": "npc_002", "name": "Bob", "age": 41, "money": 45, "job": "farmer",
                 "personality": {"sociability": 0.4, "ambition": 0.5, "risk_tolerance": 0.4, "work_ethic": 0.7, "generosity": 0.6}},
            ]
        }
        world = build_world(npcs_config=npcs)
        npc = world.npcs[0]
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        world.npcs[1].location_id = "farm"
        set_time(world, 19)
        decision = _decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "market")

    def test_evening_at_tavern_with_partner_socializes(self):
        npcs = {
            "npcs": [
                {"id": "npc_001", "name": "Alice", "age": 29, "money": 60, "job": "farmer",
                 "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5}},
                {"id": "npc_002", "name": "Bob", "age": 41, "money": 45, "job": "farmer",
                 "personality": {"sociability": 0.4, "ambition": 0.5, "risk_tolerance": 0.4, "work_ethic": 0.7, "generosity": 0.6}},
            ]
        }
        world = build_world(npcs_config=npcs)
        npc = world.npcs[0]
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        world.npcs[0].location_id = "tavern"
        world.npcs[1].location_id = "tavern"
        set_time(world, 19)
        decision = _decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "socialize")
        self.assertIsNotNone(decision.target_npc_id)

    def test_evening_at_home_with_partner_socializes_at_home(self):
        npcs = {
            "npcs": [
                {"id": "npc_001", "name": "Alice", "age": 29, "money": 60, "job": "farmer",
                 "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5}},
                {"id": "npc_002", "name": "Bob", "age": 41, "money": 45, "job": "farmer",
                 "personality": {"sociability": 0.4, "ambition": 0.5, "risk_tolerance": 0.4, "work_ethic": 0.7, "generosity": 0.6}},
            ]
        }
        world = build_world(npcs_config=npcs)
        npc = world.npcs[0]
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(world, 19)
        decision = _decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "socialize")
        self.assertIsNotNone(decision.target_npc_id)

    def test_evening_at_market_moves_to_tavern(self):
        npc = first_npc(self.world)
        npc.location_id = "market"
        set_time(self.world, 19)
        decision = self._social(npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "move")
        self.assertEqual(decision.target_location_id, "tavern")

    def test_evening_at_tavern_no_partners_waits(self):
        npc = first_npc(self.world)
        npc.location_id = "tavern"
        set_time(self.world, 19)
        decision = self._social(npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "rest")

    def test_non_evening_home_socialize_possible(self):
        npcs = {
            "npcs": [
                {"id": "npc_001", "name": "Alice", "age": 29, "money": 60, "job": "farmer",
                 "personality": {"sociability": 0.7, "ambition": 0.8, "risk_tolerance": 0.3, "work_ethic": 0.9, "generosity": 0.5}},
                {"id": "npc_002", "name": "Bob", "age": 41, "money": 45, "job": "farmer",
                 "personality": {"sociability": 0.4, "ambition": 0.5, "risk_tolerance": 0.4, "work_ethic": 0.7, "generosity": 0.6}},
            ]
        }
        world = build_world(npcs_config=npcs)
        npc = world.npcs[0]
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(world, 12)
        decision = _decide(world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(decision.action_type, "socialize")
        self.assertIsNotNone(decision.target_npc_id)


class TestNeedRulesFire(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_low_social_rule_fires(self):
        npc = first_npc(self.world)
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        self.assertFalse(decision.urgent)

    def test_low_money_rule_fires(self):
        npc = first_npc(self.world)
        npc.money = 5.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.needs.social = 90.0
        npc.location_id = npc.job.work_location
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)
        self.assertEqual(decision.action_type, "work")

    def test_low_health_rule_fires_urgent(self):
        npc = first_npc(self.world)
        npc.needs.health = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.needs.social = 90.0
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertTrue(decision.urgent)
        self.assertEqual(decision.goal.type, GoalType.SEEK_HEALTH)

    def test_low_energy_rule_fires_urgent(self):
        npc = first_npc(self.world)
        npc.needs.energy = 10.0
        npc.needs.hunger = 30.0
        npc.needs.social = 90.0
        set_time(self.world, 12)
        decision = _decide(self.world, npc)
        self.assertTrue(decision.urgent)
        self.assertEqual(decision.goal.type, GoalType.SLEEP)

    def test_low_social_overrides_expired_commitment(self):
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(self.world, 12)
        rest_goal = Goal(GoalType.REST, 5.0, "home")
        rest_goal.started_tick = self.world.clock.tick
        npc.current_goal = rest_goal
        for _ in range(4):
            self.world.update_time()
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)

    def test_low_money_overrides_expired_commitment(self):
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.money = 5.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.needs.social = 90.0
        set_time(self.world, 19)
        rest_goal = Goal(GoalType.REST, 5.0, "home")
        rest_goal.started_tick = self.world.clock.tick
        npc.current_goal = rest_goal
        for _ in range(4):
            self.world.update_time()
        decision = _decide(self.world, npc)
        self.assertEqual(decision.goal.type, GoalType.WORK)

    def test_low_health_overrides_active_commitment(self):
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.health = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.needs.social = 90.0
        set_time(self.world, 10)
        work_goal = Goal(GoalType.WORK, 15.0, npc.job.work_location)
        work_goal.started_tick = self.world.clock.tick
        npc.current_goal = work_goal
        decision = _decide(self.world, npc)
        self.assertTrue(decision.urgent)
        self.assertEqual(decision.goal.type, GoalType.SEEK_HEALTH)

    def test_low_energy_rest_during_work_window_not_urgent(self):
        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        npc.needs.energy = 30.0
        npc.needs.hunger = 30.0
        npc.needs.social = 90.0
        npc.money = 50.0
        set_time(self.world, 10)
        decision = _decide(self.world, npc)
        self.assertFalse(decision.urgent)
        self.assertEqual(decision.action_type, "rest")
        self.assertNotEqual(decision.goal.type, GoalType.WORK)

    def test_nonurgent_need_does_not_thrash(self):
        from world_sim.actions.action import ActionManager
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.social = 10.0
        npc.needs.hunger = 30.0
        npc.needs.energy = 90.0
        npc.money = 50.0
        set_time(self.world, 12)
        manager = ActionManager(random.Random(3), self.world.config)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        social_goal = Goal(GoalType.SOCIALIZE, 20.0)
        npc.current_goal = social_goal
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        self.assertEqual(decision.goal.type, GoalType.SOCIALIZE)
        action = manager.update(npc, decision, self.world)
        self.assertEqual(action.action_type, "socialize")
        for _ in range(6):
            self.world.update_time()
            perception = PerceptionSystem().perceive(npc, self.world)
            decision = ds.decide(npc, perception, self.world)
            action = manager.update(npc, decision, self.world)
            self.assertEqual(action.action_type, "socialize")


class TestCommitmentStartedTick(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def _manager(self):
        from world_sim.actions.action import ActionManager

        return ActionManager(random.Random(3), self.world.config)

    def test_started_tick_carried_for_same_goal(self):
        from world_sim.actions.action import ActionManager
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        set_time(self.world, 10)
        manager = self._manager()
        tick0 = self.world.clock.tick
        goal1 = Goal(GoalType.WORK, 20.0, npc.job.work_location)
        action = manager.update(npc, Decision(goal=goal1, action_type="work", priority=20.0), self.world)
        self.assertEqual(action.action_type, "work")
        self.assertEqual(npc.current_goal.started_tick, tick0)
        action.ticks_elapsed = action.shift_ticks
        goal2 = Goal(GoalType.WORK, 20.0, npc.job.work_location)
        action2 = manager.update(npc, Decision(goal=goal2, action_type="work", priority=20.0), self.world)
        self.assertIsNot(action, action2)
        self.assertEqual(npc.current_goal.started_tick, tick0)

    def test_started_tick_carried_across_rest_redecision(self):
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = "home"
        set_time(self.world, 12)
        manager = self._manager()
        tick0 = self.world.clock.tick
        goal1 = Goal(GoalType.REST, 20.0, "home")
        rest_action = manager.update(npc, Decision(goal=goal1, action_type="rest", priority=20.0), self.world)
        self.assertEqual(npc.current_goal.started_tick, tick0)
        rest_action.ticks_elapsed = rest_action.ticks
        goal2 = Goal(GoalType.REST, 20.0, "home")
        manager.update(npc, Decision(goal=goal2, action_type="rest", priority=20.0), self.world)
        self.assertEqual(npc.current_goal.started_tick, tick0)

    def test_new_goal_resets_started_tick(self):
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        set_time(self.world, 10)
        manager = self._manager()
        tick0 = self.world.clock.tick
        goal1 = Goal(GoalType.WORK, 20.0, npc.job.work_location)
        work_action = manager.update(npc, Decision(goal=goal1, action_type="work", priority=20.0), self.world)
        self.assertEqual(npc.current_goal.started_tick, tick0)
        work_action.ticks_elapsed = work_action.shift_ticks
        goal2 = Goal(GoalType.REST, 20.0, npc.location_id)
        manager.update(npc, Decision(goal=goal2, action_type="rest", priority=20.0), self.world)
        self.assertEqual(npc.current_goal.type, GoalType.REST)
        self.assertEqual(npc.current_goal.started_tick, tick0)

    def test_urgent_overrides_commitment_with_fresh_tick(self):
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        set_time(self.world, 10)
        manager = self._manager()
        tick0 = self.world.clock.tick
        goal1 = Goal(GoalType.WORK, 20.0, npc.job.work_location)
        manager.update(npc, Decision(goal=goal1, action_type="work", priority=20.0), self.world)
        npc.location_id = "home"
        npc.add_resource("food", 2)
        urgent = Decision(goal=Goal(GoalType.EAT, 50.0), action_type="eat", priority=50.0, urgent=True)
        action = manager.update(npc, urgent, self.world)
        self.assertEqual(action.action_type, "eat")
        self.assertEqual(npc.current_goal.type, GoalType.EAT)
        self.assertEqual(npc.current_goal.started_tick, tick0)

    def test_work_commitment_survives_move_to_work_transition(self):
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = "home"
        set_time(self.world, 8)
        manager = self._manager()
        tick0 = self.world.clock.tick
        goal1 = Goal(GoalType.WORK, 15.0, npc.job.work_location)
        goal1.started_tick = tick0
        move_action = manager.update(
            npc,
            Decision(
                goal=goal1,
                action_type="move",
                priority=15.0,
                target_location_id=npc.job.work_location,
            ),
            self.world,
        )
        self.assertEqual(move_action.action_type, "move")
        self.assertEqual(npc.current_goal.started_tick, tick0)
        while npc.location_id != npc.job.work_location:
            move_action.tick(npc, self.world)
        self.assertTrue(move_action.is_complete(npc, self.world))
        self.world.update_time()
        goal2 = Goal(GoalType.WORK, 15.0, npc.job.work_location)
        work_action = manager.update(
            npc,
            Decision(goal=goal2, action_type="work", priority=15.0),
            self.world,
        )
        self.assertEqual(work_action.action_type, "work")
        self.assertEqual(npc.current_goal.started_tick, tick0)

    def test_rest_commitment_survives_action_transition(self):
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = "home"
        set_time(self.world, 12)
        manager = self._manager()
        tick0 = self.world.clock.tick
        goal1 = Goal(GoalType.REST, 10.0, "home")
        goal1.started_tick = tick0
        rest1 = manager.update(npc, Decision(goal=goal1, action_type="rest", priority=10.0), self.world)
        self.assertEqual(npc.current_goal.started_tick, tick0)
        self.world.update_time()
        self.world.update_time()
        goal2 = Goal(GoalType.REST, 10.0, "home")
        rest2 = manager.update(npc, Decision(goal=goal2, action_type="rest", priority=10.0), self.world)
        self.assertIs(rest1, rest2)
        self.assertEqual(npc.current_goal.started_tick, tick0)

    def test_new_goal_resets_commitment_timer(self):
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        set_time(self.world, 10)
        manager = self._manager()
        goal1 = Goal(GoalType.WORK, 15.0, npc.job.work_location)
        work_action = manager.update(npc, Decision(goal=goal1, action_type="work", priority=15.0), self.world)
        self.assertEqual(npc.current_goal.started_tick, 0)
        work_action.ticks_elapsed = work_action.shift_ticks
        self.world.update_time()
        goal2 = Goal(GoalType.REST, 10.0, npc.location_id)
        manager.update(npc, Decision(goal=goal2, action_type="rest", priority=10.0), self.world)
        self.assertEqual(npc.current_goal.type, GoalType.REST)
        self.assertEqual(npc.current_goal.started_tick, 1)

    def test_urgent_decision_resets_commitment_with_fresh_tick(self):
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc = first_npc(self.world)
        npc.location_id = npc.job.work_location
        set_time(self.world, 10)
        manager = self._manager()
        goal1 = Goal(GoalType.WORK, 15.0, npc.job.work_location)
        manager.update(npc, Decision(goal=goal1, action_type="work", priority=15.0), self.world)
        self.assertEqual(npc.current_goal.started_tick, 0)
        self.world.update_time()
        npc.add_resource("food", 2)
        urgent = Decision(goal=Goal(GoalType.EAT, 50.0), action_type="eat", priority=50.0, urgent=True)
        action = manager.update(npc, urgent, self.world)
        self.assertEqual(action.action_type, "eat")
        self.assertEqual(npc.current_goal.type, GoalType.EAT)
        self.assertEqual(npc.current_goal.started_tick, 1)


class TestFoodEconomy(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def _explore_action(self, npc):
        from world_sim.actions.exploring import ExploreAction
        from world_sim.decision.decision_system import Decision
        from world_sim.npc.goals import Goal

        npc.location_id = "forest"
        decision = Decision(goal=Goal(GoalType.EXPLORE, 10.0), action_type="explore", priority=10.0)
        return ExploreAction(random.Random(1), self.world.config, decision)

    def test_explore_does_not_forage_beyond_cap(self):
        npc = first_npc(self.world)
        cap = int(self.world.config.get("actions", {}).get("food_cap", 6))
        npc.add_resource("food", cap)
        action = self._explore_action(npc)
        for _ in range(100):
            action.apply(npc, self.world)
        self.assertEqual(npc.inventory.get("food", 0), cap)

    def test_low_food_npc_forages_at_forest(self):
        npc = first_npc(self.world)
        npc.inventory.pop("food", None)
        action = self._explore_action(npc)
        foraged = 0
        for _ in range(100):
            before = npc.inventory.get("food", 0)
            action.apply(npc, self.world)
            if npc.inventory.get("food", 0) > before:
                foraged += 1
        self.assertGreater(foraged, 0)

    def test_fed_npc_prefers_not_exploring_in_free_time(self):
        npc = first_npc(self.world)
        npc.needs.hunger = 30.0
        npc.needs.energy = 95.0
        npc.needs.social = 90.0
        npc.personality.sociability = 0.2
        npc.personality.ambition = 0.2
        npc.personality.work_ethic = 0.3
        npc.personality.risk_tolerance = 0.9
        npc.add_resource("food", 5)
        set_time(self.world, 7)
        fed = _decide(self.world, npc)
        self.assertNotEqual(fed.goal.type, GoalType.EXPLORE)
        npc.inventory.pop("food", None)
        hungry = _decide(self.world, npc)
        self.assertEqual(hungry.goal.type, GoalType.EXPLORE)


class TestWakeEvents(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_single_wake_up_event_for_morning_transition(self):
        from world_sim.actions.action import ActionManager

        npc = first_npc(self.world)
        npc.location_id = "home"
        npc.needs.energy = 30.0
        npc.needs.hunger = 30.0
        npc.needs.social = 60.0
        set_time(self.world, 4)
        ds = RuleBasedDecisionSystem(self.world.config, random.Random(3))
        manager = ActionManager(random.Random(3), self.world.config)
        perception = PerceptionSystem().perceive(npc, self.world)
        decision = ds.decide(npc, perception, self.world)
        self.assertEqual(decision.goal.type, GoalType.SLEEP)
        action = manager.update(npc, decision, self.world)
        self.assertEqual(action.action_type, "sleep")
        with self.assertLogs("world_sim", level="INFO") as cm:
            for _ in range(28):
                self.world.update_time()
                decision = ds.decide(npc, perception, self.world)
                action = manager.update(npc, decision, self.world)
                action.tick(npc, self.world)
        woke = [line for line in cm.output if "woke up" in line]
        self.assertEqual(len(woke), 1)


if __name__ == "__main__":
    unittest.main()