import ast
import random
import unittest
from dataclasses import asdict
from pathlib import Path

from world_sim.actions.eating import BuyFoodAction, EatAction
from world_sim.actions.idle import IdleAction
from world_sim.actions.interacting import InteractAction
from world_sim.actions.movement import MoveAction
from world_sim.actions.resting import RestAction
from world_sim.actions.sleeping import SleepAction
from world_sim.actions.social import SocializeAction
from world_sim.actions.working import WorkAction
from world_sim.decision.decision_system import Decision
from world_sim.npc.conversation import Conversation
from world_sim.npc.goals import Goal, GoalType
from world_sim.npc.intent import Intent
from world_sim.presentation.animation import AnimationState, animate
from world_sim.tests.helpers import build_world

_RENDERING_MODULES = (
    "pygame",
    "turtle",
    "PIL",
    "matplotlib",
    "opengl",
    "OpenGL",
    "three",
    "godot",
    "unity",
    "bpy",
    "manim",
    "plotly",
    "graphics",
    "glfw",
    "vulkan",
)


def _world(behavior=True, conversations=False):
    behavior_cfg = {"enabled": behavior}
    if conversations:
        behavior_cfg["conversations"] = {"enabled": True}
    return build_world(seed=1, world_config={"behavior": behavior_cfg})


def _npc(world):
    return world.npcs[0]


def _decision(action_type, **candidates):
    return Decision(
        goal=Goal(GoalType.REST, 10.0),
        action_type=action_type,
        priority=10.0,
        candidates=candidates,
    )


def _attach(world, action_cls, action_type, **candidates):
    action = action_cls(random.Random(1), world.config, _decision(action_type, **candidates))
    npc = _npc(world)
    npc.current_action = action
    return npc, action


def _start_conversation(world, npc_a, npc_b, stage="greeting", started_tick=None):
    conv = Conversation(
        id=f"conv_{world.clock.tick}_{npc_a.id}_{npc_b.id}",
        initiator_id=npc_a.id,
        responder_id=npc_b.id,
        stage=stage,
        turns_left=4,
        started_tick=started_tick if started_tick is not None else world.clock.tick,
        last_turn_tick=world.clock.tick,
        started_day=world.clock.day,
    )
    npc_a.conversation_id = conv.id
    npc_b.conversation_id = conv.id
    world.conversations.append(conv)
    return conv


def _npc_snapshot(npc):
    return (
        npc.id,
        npc.alive,
        npc.location_id,
        npc.facing,
        npc.conversation_id,
        npc.idle_state,
        npc.current_action,
        npc.current_goal,
        npc.intent,
        dict(npc.inventory),
        dict(npc.relationships),
        npc.money,
        npc.needs.hunger,
        npc.needs.energy,
        npc.needs.social,
        npc.needs.health,
        len(npc.memory.entries),
        npc.last_wake_day,
        npc.last_socialize_day,
    )


def _world_snapshot(world):
    return (
        world.clock.tick,
        len(world.npcs),
        len(world.conversations),
        tuple((o.id, o.state, o.in_use_by) for o in world.objects),
        getattr(world, "farm_stock", None),
        getattr(getattr(world, "economy", None), "food_stock", None),
        tuple((e.id, e.state.value) for e in world.events),
        asdict(world.stats),
    )


class TestAnimationStateBasics(unittest.TestCase):
    def test_default_construction(self):
        state = AnimationState(npc_id="npc_001", pose="idle", moving=False, behavior_state="idle")
        self.assertEqual(state.npc_id, "npc_001")
        self.assertEqual(state.pose, "idle")
        self.assertFalse(state.moving)
        self.assertEqual(state.behavior_state, "idle")
        self.assertIsNone(state.facing_location_id)
        self.assertIsNone(state.facing_object_id)
        self.assertIsNone(state.facing_npc_id)
        self.assertIsNone(state.target_location_id)
        self.assertIsNone(state.target_npc_id)
        self.assertIsNone(state.target_object_id)
        self.assertEqual(state.emotion, "content")
        self.assertFalse(state.in_conversation)
        self.assertIsNone(state.intent)
        self.assertEqual(state.pose_progress, 0.0)

    def test_animate_idle_npc(self):
        world = _world()
        npc = _npc(world)
        npc.current_action = None
        npc.intent = None
        state = animate(npc, world)
        self.assertEqual(state.npc_id, npc.id)
        self.assertEqual(state.behavior_state, "idle")
        self.assertEqual(state.pose, "idle")
        self.assertFalse(state.moving)
        self.assertFalse(state.in_conversation)


class TestPoseMapping(unittest.TestCase):
    def setUp(self):
        self.world = _world()

    def test_move_is_walk(self):
        npc, action = _attach(self.world, MoveAction, "move")
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "walk")

    def test_work_is_work(self):
        npc, _ = _attach(self.world, WorkAction, "work")
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "work")

    def test_eat_is_eat(self):
        npc, _ = _attach(self.world, EatAction, "eat")
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "eat")

    def test_buy_food_is_buy(self):
        npc, _ = _attach(self.world, BuyFoodAction, "buy_food")
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "buy")

    def test_sleep_is_sleep(self):
        npc, _ = _attach(self.world, SleepAction, "sleep")
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "sleep")

    def test_rest_is_idle(self):
        npc, _ = _attach(self.world, RestAction, "rest")
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "idle")

    def test_no_action_is_idle(self):
        npc = _npc(self.world)
        npc.current_action = None
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "idle")

    def test_socialize_is_talk(self):
        npc, _ = _attach(self.world, SocializeAction, "socialize", target_npc_id="npc_002")
        state = animate(npc, self.world)
        self.assertEqual(state.pose, "talk")


class TestIdlePoses(unittest.TestCase):
    def setUp(self):
        self.world = _world()

    def _idle(self, idle_state):
        npc, action = _attach(self.world, IdleAction, "idle")
        action.idle_state = idle_state
        npc.idle_state = idle_state
        return npc

    def test_idle_sit(self):
        self.assertEqual(animate(self._idle("sit"), self.world).pose, "sit")

    def test_idle_stretch(self):
        self.assertEqual(animate(self._idle("stretch"), self.world).pose, "stretch")

    def test_idle_inspect_nearby(self):
        self.assertEqual(animate(self._idle("inspect_nearby"), self.world).pose, "inspect")

    def test_idle_look_around(self):
        self.assertEqual(animate(self._idle("look_around"), self.world).pose, "idle")

    def test_rest_with_idle_state_sit(self):
        npc, _ = _attach(self.world, RestAction, "rest")
        npc.idle_state = "sit"
        self.assertEqual(animate(npc, self.world).pose, "sit")


class TestInteractPoses(unittest.TestCase):
    def setUp(self):
        self.world = _world()

    def test_interact_sit(self):
        npc, _ = _attach(self.world, InteractAction, "interact", interaction="sit", target_object_id="o1")
        self.assertEqual(animate(npc, self.world).pose, "sit")

    def test_interact_use(self):
        npc, _ = _attach(self.world, InteractAction, "interact", interaction="use", target_object_id="o1")
        self.assertEqual(animate(npc, self.world).pose, "interact")

    def test_interact_inspect(self):
        npc, _ = _attach(self.world, InteractAction, "interact", interaction="inspect", target_object_id="o1")
        self.assertEqual(animate(npc, self.world).pose, "inspect")

    def test_interact_tend(self):
        npc, _ = _attach(self.world, InteractAction, "interact", interaction="tend", target_object_id="o1")
        self.assertEqual(animate(npc, self.world).pose, "work")


class TestConversationPoses(unittest.TestCase):
    def setUp(self):
        self.world = _world(behavior=True, conversations=True)
        self.a = self.world.npcs[0]
        self.b = self.world.npcs[1]
        self.a.current_action = None
        self.b.current_action = None

    def test_greeting_is_wave(self):
        _start_conversation(self.world, self.a, self.b, stage="greeting")
        self.assertEqual(animate(self.a, self.world).pose, "wave")
        self.assertEqual(animate(self.b, self.world).pose, "wave")

    def test_exchange_initiator_speaks(self):
        _start_conversation(self.world, self.a, self.b, stage="exchange", started_tick=self.world.clock.tick - 1)
        self.assertEqual(animate(self.a, self.world).pose, "talk")
        self.assertEqual(animate(self.b, self.world).pose, "listen")

    def test_exchange_responder_speaks(self):
        _start_conversation(self.world, self.a, self.b, stage="exchange", started_tick=self.world.clock.tick - 2)
        self.assertEqual(animate(self.a, self.world).pose, "listen")
        self.assertEqual(animate(self.b, self.world).pose, "talk")

    def test_farewell_is_wave(self):
        _start_conversation(self.world, self.a, self.b, stage="farewell")
        self.assertEqual(animate(self.a, self.world).pose, "wave")
        self.assertEqual(animate(self.b, self.world).pose, "wave")


class TestDead(unittest.TestCase):
    def test_dead_pose_and_moving(self):
        world = _world()
        npc = _npc(world)
        npc.alive = False
        npc.current_action = MoveAction(random.Random(1), world.config, _decision("move"))
        state = animate(npc, world)
        self.assertEqual(state.pose, "dead")
        self.assertFalse(state.moving)
        self.assertEqual(state.behavior_state, "dead")
        self.assertEqual(state.emotion, "stressed")


class TestMovingFlag(unittest.TestCase):
    def setUp(self):
        self.world = _world()

    def test_moving_true_only_for_move(self):
        npc, _ = _attach(self.world, MoveAction, "move")
        self.assertTrue(animate(npc, self.world).moving)
        npc2, _ = _attach(self.world, WorkAction, "work")
        self.assertFalse(animate(npc2, self.world).moving)
        npc3, _ = _attach(self.world, EatAction, "eat")
        self.assertFalse(animate(npc3, self.world).moving)
        npc4, _ = _attach(self.world, RestAction, "rest")
        self.assertFalse(animate(npc4, self.world).moving)
        npc5, _ = _attach(self.world, SleepAction, "sleep")
        self.assertFalse(animate(npc5, self.world).moving)

    def test_conversing_npc_not_moving(self):
        world = _world(conversations=True)
        a, b = world.npcs[0], world.npcs[1]
        _start_conversation(world, a, b)
        a.current_action = MoveAction(random.Random(1), world.config, _decision("move"))
        state = animate(a, world)
        self.assertFalse(state.moving)
        self.assertEqual(state.behavior_state, "conversing")


class TestFacing(unittest.TestCase):
    def setUp(self):
        self.world = _world()

    def test_facing_npc_during_conversation(self):
        world = _world(conversations=True)
        a, b = world.npcs[0], world.npcs[1]
        _start_conversation(world, a, b)
        self.assertEqual(animate(a, world).facing_npc_id, b.id)
        self.assertEqual(animate(b, world).facing_npc_id, a.id)
        self.assertIsNone(animate(a, world).facing_object_id)
        self.assertIsNone(animate(a, world).facing_location_id)

    def test_facing_object_during_interaction(self):
        npc, _ = _attach(self.world, InteractAction, "interact", interaction="inspect", target_object_id="bench_1")
        state = animate(npc, self.world)
        self.assertEqual(state.facing_object_id, "bench_1")
        self.assertIsNone(state.facing_npc_id)
        self.assertIsNone(state.facing_location_id)

    def test_facing_location_during_movement(self):
        npc, action = _attach(self.world, MoveAction, "move")
        action.target = "market"
        state = animate(npc, self.world)
        self.assertEqual(state.facing_location_id, "market")
        self.assertIsNone(state.facing_npc_id)
        self.assertIsNone(state.facing_object_id)


class TestTargets(unittest.TestCase):
    def test_target_location_during_movement(self):
        world = _world()
        npc, action = _attach(world, MoveAction, "move")
        action.target = "market"
        state = animate(npc, world)
        self.assertEqual(state.target_location_id, "market")

    def test_target_object_during_interaction(self):
        world = _world()
        npc, _ = _attach(world, InteractAction, "interact", interaction="sit", target_object_id="bench_1")
        state = animate(npc, world)
        self.assertEqual(state.target_object_id, "bench_1")

    def test_target_npc_during_conversation(self):
        world = _world(conversations=True)
        a, b = world.npcs[0], world.npcs[1]
        _start_conversation(world, a, b)
        self.assertEqual(animate(a, world).target_npc_id, b.id)
        self.assertEqual(animate(b, world).target_npc_id, a.id)

    def test_target_from_intent(self):
        world = _world()
        npc = _npc(world)
        npc.intent = Intent(kind="working", started_tick=0, target_location_id="workshop")
        state = animate(npc, world)
        self.assertEqual(state.target_location_id, "workshop")


class TestEmotion(unittest.TestCase):
    def setUp(self):
        self.world = _world()
        self.npc = _npc(self.world)
        self.npc.current_action = None

    def test_hungry_emotion(self):
        self.npc.needs.hunger = 85.0
        self.npc.needs.energy = 90.0
        self.npc.needs.social = 60.0
        self.assertEqual(animate(self.npc, self.world).emotion, "hungry")

    def test_tired_emotion(self):
        self.npc.needs.hunger = 30.0
        self.npc.needs.energy = 10.0
        self.npc.needs.social = 60.0
        self.assertEqual(animate(self.npc, self.world).emotion, "tired")

    def test_lonely_emotion(self):
        self.npc.needs.hunger = 30.0
        self.npc.needs.energy = 90.0
        self.npc.needs.social = 5.0
        self.assertEqual(animate(self.npc, self.world).emotion, "lonely")

    def test_content_emotion(self):
        self.npc.needs.hunger = 30.0
        self.npc.needs.energy = 90.0
        self.npc.needs.social = 60.0
        self.assertEqual(animate(self.npc, self.world).emotion, "content")

    def test_dead_is_stressed(self):
        self.npc.alive = False
        self.npc.needs.hunger = 85.0
        self.assertEqual(animate(self.npc, self.world).emotion, "stressed")


class TestIntentPropagation(unittest.TestCase):
    def test_intent_kind_exposed(self):
        world = _world()
        npc = _npc(world)
        npc.intent = Intent(kind="eating", started_tick=0)
        self.assertEqual(animate(npc, world).intent, "eating")

    def test_no_intent_is_none(self):
        world = _world()
        npc = _npc(world)
        npc.intent = None
        self.assertIsNone(animate(npc, world).intent)


class TestPoseProgress(unittest.TestCase):
    def setUp(self):
        self.world = _world()

    def test_no_action_is_zero(self):
        npc = _npc(self.world)
        npc.current_action = None
        self.assertEqual(animate(npc, self.world).pose_progress, 0.0)

    def test_eat_progress(self):
        npc, action = _attach(self.world, EatAction, "eat")
        action.ticks_elapsed = 0
        self.assertEqual(animate(npc, self.world).pose_progress, 0.0)
        action.ticks_elapsed = 1
        self.assertEqual(animate(npc, self.world).pose_progress, 1.0)

    def test_rest_progress(self):
        npc, action = _attach(self.world, RestAction, "rest")
        action.ticks_elapsed = 6
        self.assertAlmostEqual(animate(npc, self.world).pose_progress, 0.5)

    def test_work_progress(self):
        npc, action = _attach(self.world, WorkAction, "work")
        action.shift_ticks = 8
        action.ticks_elapsed = 2
        self.assertAlmostEqual(animate(npc, self.world).pose_progress, 0.25)

    def test_progress_clamped_to_one(self):
        npc, action = _attach(self.world, RestAction, "rest")
        action.ticks_elapsed = 999
        self.assertEqual(animate(npc, self.world).pose_progress, 1.0)

    def test_progress_within_bounds_across_actions(self):
        for cls, atype, extra in (
            (MoveAction, "move", {"target_location_id": "market"}),
            (WorkAction, "work", {}),
            (EatAction, "eat", {}),
            (SleepAction, "sleep", {}),
            (RestAction, "rest", {}),
            (InteractAction, "interact", {"interaction": "sit", "target_object_id": "o1"}),
            (SocializeAction, "socialize", {"target_npc_id": "npc_002"}),
        ):
            decision = _decision(atype, **extra)
            action = cls(random.Random(1), self.world.config, decision)
            npc = _npc(self.world)
            npc.current_action = action
            for elapsed in (0, 1, 5, 50):
                action.ticks_elapsed = elapsed
                progress = animate(npc, self.world).pose_progress
                self.assertTrue(0.0 <= progress <= 1.0, (cls.__name__, elapsed, progress))


class TestDeterminismAndPurity(unittest.TestCase):
    def setUp(self):
        self.world = _world()
        self.npc, self.action = _attach(self.world, MoveAction, "move")
        self.action.target = "market"
        self.npc.intent = Intent(kind="traveling", started_tick=0, target_location_id="market")

    def test_deterministic_repeated_calls(self):
        first = animate(self.npc, self.world)
        second = animate(self.npc, self.world)
        self.assertEqual(asdict(first), asdict(second))

    def test_deterministic_across_identical_instances(self):
        world_b = _world()
        npc_b, action_b = _attach(world_b, MoveAction, "move")
        action_b.target = "market"
        npc_b.intent = Intent(kind="traveling", started_tick=0, target_location_id="market")
        self.assertEqual(asdict(animate(self.npc, self.world)), asdict(animate(npc_b, world_b)))

    def test_no_mutation_of_npc(self):
        before = _npc_snapshot(self.npc)
        animate(self.npc, self.world)
        self.assertEqual(before, _npc_snapshot(self.npc))

    def test_no_mutation_of_world(self):
        before = _world_snapshot(self.world)
        animate(self.npc, self.world)
        self.assertEqual(before, _world_snapshot(self.world))

    def test_no_mutation_while_conversing(self):
        world = _world(conversations=True)
        a, b = world.npcs[0], world.npcs[1]
        _start_conversation(world, a, b)
        npc_before = _npc_snapshot(a)
        world_before = _world_snapshot(world)
        animate(a, world)
        animate(b, world)
        self.assertEqual(npc_before, _npc_snapshot(a))
        self.assertEqual(world_before, _world_snapshot(world))

    def test_no_sim_rng_consumed(self):
        before = self.world.rng.getstate()
        animate(self.npc, self.world)
        after = self.world.rng.getstate()
        self.assertEqual(before, after)


class TestNoRenderingDependency(unittest.TestCase):
    def test_module_has_no_rendering_imports(self):
        module_path = Path(__file__).resolve().parents[1] / "presentation" / "animation.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
                imports.extend(alias.name for alias in node.names)
        for name in imports:
            root = name.split(".")[0]
            self.assertNotIn(root, _RENDERING_MODULES, f"rendering dependency {name}")

    def test_importable(self):
        from world_sim.presentation import animation as module

        self.assertTrue(callable(module.animate))
        self.assertIs(module.AnimationState, AnimationState)


class TestDisabledBehavior(unittest.TestCase):
    def test_animate_works_when_behavior_disabled(self):
        world = build_world(seed=1)
        npc = world.npcs[0]
        npc.current_action = None
        state = animate(npc, world)
        self.assertEqual(state.npc_id, npc.id)
        self.assertEqual(state.behavior_state, "idle")
        self.assertEqual(state.pose, "idle")
        self.assertFalse(state.in_conversation)

    def test_disabled_movement_projection(self):
        world = build_world(seed=1)
        npc = world.npcs[0]
        npc.current_action = MoveAction(random.Random(1), world.config, _decision("move"))
        npc.current_action.target = "market"
        before = _npc_snapshot(npc)
        state = animate(npc, world)
        self.assertEqual(state.pose, "walk")
        self.assertTrue(state.moving)
        self.assertEqual(state.target_location_id, "market")
        self.assertEqual(before, _npc_snapshot(npc))

    def test_disabled_world_not_mutated(self):
        world = build_world(seed=1)
        npc = world.npcs[0]
        npc.current_action = WorkAction(random.Random(1), world.config, _decision("work"))
        world_before = _world_snapshot(world)
        animate(npc, world)
        self.assertEqual(world_before, _world_snapshot(world))


if __name__ == "__main__":
    unittest.main()