import random
import unittest

from world_sim.actions.eating import EatAction
from world_sim.actions.interacting import InteractAction
from world_sim.actions.movement import MoveAction
from world_sim.actions.resting import RestAction
from world_sim.actions.sleeping import SleepAction
from world_sim.actions.social import SocializeAction
from world_sim.actions.working import WorkAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.behavior import BehaviorState, behavior_state
from world_sim.npc.goals import Goal, GoalType
from world_sim.npc.intent import Intent
from world_sim.tests.helpers import build_world


def _decision(action_type):
    return Decision(goal=Goal(GoalType.REST, 10.0), action_type=action_type, priority=10.0)


def _npc(world):
    return world.npcs[0]


def _attach(world, action_cls, action_type):
    action = action_cls(random.Random(1), world.config, _decision(action_type))
    npc = _npc(world)
    npc.current_action = action
    return npc


class TestBehaviorStateFSM(unittest.TestCase):
    def setUp(self):
        self.world = build_world(seed=1)

    def test_dead_is_dead_state(self):
        npc = _npc(self.world)
        npc.alive = False
        npc.current_action = MoveAction(random.Random(1), self.world.config, _decision("move"))
        npc.conversation_id = "conversation_0"
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.DEAD)

    def test_dead_takes_precedence_over_everything(self):
        npc = _npc(self.world)
        npc.alive = False
        npc.current_action = WorkAction(random.Random(1), self.world.config, _decision("work"))
        npc.intent = Intent(kind="socializing", started_tick=0)
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.DEAD)

    def test_conversing_takes_precedence_over_moving(self):
        npc = _attach(self.world, MoveAction, "move")
        npc.conversation_id = "conversation_0"
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.CONVERSING)

    def test_conversing_state_when_idle(self):
        npc = _npc(self.world)
        npc.conversation_id = "conversation_0"
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.CONVERSING)

    def test_moving_state(self):
        npc = _attach(self.world, MoveAction, "move")
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.MOVING)

    def test_interacting_state(self):
        npc = _attach(self.world, InteractAction, "interact")
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.INTERACTING)

    def test_sleeping_state(self):
        npc = _attach(self.world, SleepAction, "sleep")
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.SLEEPING)

    def test_socializing_state_via_action(self):
        npc = _attach(self.world, SocializeAction, "socialize")
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.SOCIALIZING)

    def test_socializing_state_via_intent(self):
        npc = _attach(self.world, WorkAction, "work")
        npc.intent = Intent(kind="socializing", started_tick=0)
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.SOCIALIZING)

    def test_socializing_takes_precedence_over_acting(self):
        npc = _attach(self.world, WorkAction, "work")
        npc.intent = Intent(kind="socializing", started_tick=0)
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.SOCIALIZING)

    def test_acting_state_when_working(self):
        npc = _attach(self.world, WorkAction, "work")
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.ACTING)

    def test_acting_state_when_eating(self):
        npc = _attach(self.world, EatAction, "eat")
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.ACTING)

    def test_idle_default(self):
        npc = _npc(self.world)
        npc.current_action = None
        npc.intent = None
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.IDLE)

    def test_idle_while_resting(self):
        npc = _attach(self.world, RestAction, "rest")
        self.assertEqual(behavior_state(npc, self.world), BehaviorState.IDLE)

    def test_state_is_pure_projection(self):
        npc = _attach(self.world, MoveAction, "move")
        state = behavior_state(npc, self.world)
        before = (npc.current_action, npc.intent, npc.location_id)
        self.assertEqual(state, BehaviorState.MOVING)
        after = (npc.current_action, npc.intent, npc.location_id)
        self.assertEqual(before, after)

    def test_no_rng_consumed(self):
        npc = _attach(self.world, MoveAction, "move")
        before = self.world.rng.getstate()
        behavior_state(npc, self.world)
        after = self.world.rng.getstate()
        self.assertEqual(before, after)