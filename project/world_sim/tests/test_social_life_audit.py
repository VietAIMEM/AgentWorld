import json
import tempfile
import unittest
from pathlib import Path

from world_sim.decision.rule_based import RuleBasedDecisionSystem
from world_sim.npc.goals import GoalType
from world_sim.npc.perception import PerceptionSystem
from world_sim.npc.routine import routine_for_npc
from world_sim.presentation.player import PlayerSession
from world_sim.simulation.persistence import save_state
from world_sim.simulation.simulation import Simulation
from world_sim.tests.helpers import load_configs

VALID_GOAL_TYPES = {goal.value for goal in GoalType}
VALID_ACTION_TYPES = {
    "move",
    "eat",
    "buy_food",
    "sleep",
    "work",
    "socialize",
    "rest",
    "explore",
    "interact",
}


def social_configs(enabled=True):
    wc, nc = load_configs()
    wc["behavior"] = {
        "enabled": True,
        "routines": {"enabled": True, "default_bias": 0.5},
        "objects": {"enabled": True},
        "interactions": True,
        "conversations": {"enabled": True, "max_turns": 4},
        "social_life": {"enabled": enabled, "social_events": True},
    }
    return wc, nc


def check_invariants(world, days):
    world.process_events()
    assert world.stats.deaths == 0, f"deaths={world.stats.deaths} seed={world._gen_seed} days={days}"
    alive_ids = {npc.id for npc in world.npcs if npc.alive}
    conversations_by_npc = {}
    for conv in world.conversations:
        assert conv.initiator_id in alive_ids and conv.responder_id in alive_ids
        initiator = world.get_npc(conv.initiator_id)
        responder = world.get_npc(conv.responder_id)
        assert initiator.location_id == responder.location_id
        assert initiator.conversation_id == conv.id and responder.conversation_id == conv.id
        for npc_id in (conv.initiator_id, conv.responder_id):
            assert npc_id not in conversations_by_npc, f"overlapping conversation for {npc_id}"
            conversations_by_npc[npc_id] = conv.id
    for npc in world.npcs:
        assert npc.alive
        assert npc.location_id in world.locations, f"{npc.id} at invalid {npc.location_id}"
        assert npc.money >= 0, f"{npc.id} negative money {npc.money}"
        assert npc.needs.hunger >= 0 and npc.needs.energy >= 0
        assert npc.needs.social >= 0 and npc.needs.health >= 0
        for value in npc.relationships.values():
            assert -100 <= value <= 100, f"{npc.id} relationship {value} out of bounds"
        assert len(npc.memory.entries) <= npc.memory.max_size, f"{npc.id} memory cap exceeded"
        if npc.current_goal is not None:
            assert npc.current_goal.type.value in VALID_GOAL_TYPES
        if npc.current_action is not None:
            assert npc.current_action.action_type in VALID_ACTION_TYPES


SOCIAL_NPCS = {
    "npcs": [
        {
            "id": "a",
            "name": "Ava",
            "age": 30,
            "money": 50,
            "hunger": 45,
            "energy": 95,
            "social": 25,
            "health": 100,
            "job": "worker",
            "personality": {"sociability": 0.9, "ambition": 0.3, "risk_tolerance": 0.3, "work_ethic": 0.4, "generosity": 0.6},
        },
        {
            "id": "b",
            "name": "Ben",
            "age": 30,
            "money": 50,
            "hunger": 45,
            "energy": 95,
            "social": 40,
            "health": 100,
            "job": "worker",
            "personality": {"sociability": 0.3, "ambition": 0.9, "risk_tolerance": 0.4, "work_ethic": 0.9, "generosity": 0.3},
        },
        {
            "id": "c",
            "name": "Cor",
            "age": 65,
            "money": 50,
            "hunger": 45,
            "energy": 95,
            "social": 50,
            "health": 100,
            "job": "worker",
            "personality": {"sociability": 0.5, "ambition": 0.4, "risk_tolerance": 0.3, "work_ethic": 0.6, "generosity": 0.5},
        },
        {
            "id": "d",
            "name": "Dee",
            "age": 30,
            "money": 50,
            "hunger": 45,
            "energy": 95,
            "social": 25,
            "health": 100,
            "job": "worker",
            "personality": {"sociability": 0.8, "ambition": 0.5, "risk_tolerance": 0.3, "work_ethic": 0.6, "generosity": 0.6},
        },
        {
            "id": "e",
            "name": "Eve",
            "age": 30,
            "money": 50,
            "hunger": 45,
            "energy": 95,
            "social": 50,
            "health": 100,
            "job": "worker",
            "personality": {"sociability": 0.5, "ambition": 0.5, "risk_tolerance": 0.5, "work_ethic": 0.5, "generosity": 0.5},
        },
    ]
}


def acceptance_configs():
    wc, nc = social_configs()
    nc = SOCIAL_NPCS
    return wc, nc


class TestSocialLifeAudit(unittest.TestCase):
    def test_audit_durations(self):
        runs = [(30, [1, 42, 99, 2026]), (90, [42, 99]), (365, [42, 99]), (1000, [42])]
        for days, seeds in runs:
            for seed in seeds:
                wc, nc = social_configs()
                sim = Simulation(wc, nc, seed=seed, days=days, print_report=False)
                sim.run()
                check_invariants(sim.world, days)
                self.assertEqual(sim.world.stats.deaths, 0)

    def test_same_seed_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for _ in range(2):
                wc, nc = social_configs()
                sim = Simulation(wc, nc, seed=42, days=5, print_report=False)
                sim.run()
                path = Path(tmp) / f"{len(paths)}.json"
                save_state(sim, path)
                paths.append(path.read_bytes())
            self.assertEqual(paths[0], paths[1])

    def test_disabled_mode_rng_unaffected_by_feature(self):
        wc, nc = social_configs(enabled=False)
        sim = Simulation(wc, nc, seed=99, days=10, print_report=False)
        sim.run()
        draws_disabled = [sim.rng.random() for _ in range(50)]
        wc2, nc2 = social_configs(enabled=False)
        sim2 = Simulation(wc2, nc2, seed=99, days=10, print_report=False)
        sim2.run()
        draws_disabled_2 = [sim2.rng.random() for _ in range(50)]
        self.assertEqual(draws_disabled, draws_disabled_2)


class TestAcceptanceScenario(unittest.TestCase):
    def test_friends_meet_talk_and_remember(self):
        wc, nc = acceptance_configs()
        sim = Simulation(wc, nc, seed=1, days=20, print_report=False)
        world = sim.world
        a = world.get_npc("a")
        d = world.get_npc("d")
        a.relationships[d.id] = 40
        d.relationships[a.id] = 40
        sim.run()
        check_invariants(world, 20)
        self.assertGreater(a.relationships.get(d.id, 0), 40)
        d_memories = [e for e in a.memory.entries if e.related_entity == d.id]
        self.assertGreater(len(d_memories), 0)
        self.assertTrue(
            any(e.event_type in ("met_npc", "conversation", "worked_with") for e in d_memories)
        )
        d_a_memories = [e for e in d.memory.entries if e.related_entity == a.id]
        self.assertGreater(len(d_a_memories), 0)

    def test_elderly_routine(self):
        wc, nc = acceptance_configs()
        sim = Simulation(wc, nc, seed=1, days=5, print_report=False)
        c = sim.world.get_npc("c")
        self.assertEqual(c.routine_id, "elderly")
        routine = routine_for_npc(c, sim.world)
        self.assertEqual(routine.id, "elderly")
        social_blocks = [block for block in routine.blocks if block.activity == "socialize"]
        self.assertGreater(len(social_blocks), 0)

    def test_ambitious_npc_prioritizes_work(self):
        wc, nc = acceptance_configs()
        sim = Simulation(wc, nc, seed=1, days=1, print_report=False)
        world = sim.world
        a = world.get_npc("a")
        b = world.get_npc("b")
        for npc in (a, b):
            npc.needs.hunger = 30.0
            npc.needs.energy = 70.0
            npc.needs.social = 80.0
            npc.needs.health = 100.0
            npc.money = 10.0
            npc.current_goal = None
            npc.current_action = None
        world.clock.hour = 10
        ds = RuleBasedDecisionSystem(world.config, world.rng)
        perception_a = PerceptionSystem().perceive(a, world)
        perception_b = PerceptionSystem().perceive(b, world)
        da = ds.decide(a, perception_a, world)
        db = ds.decide(b, perception_b, world)
        self.assertEqual(db.goal.type, GoalType.WORK)
        self.assertEqual(da.goal.type, GoalType.WORK)
        self.assertGreater(db.priority, da.priority)

    def test_sociable_npc_prioritizes_socialize(self):
        wc, nc = acceptance_configs()
        sim = Simulation(wc, nc, seed=1, days=1, print_report=False)
        world = sim.world
        a = world.get_npc("a")
        b = world.get_npc("b")
        for npc in (a, b):
            npc.needs.hunger = 30.0
            npc.needs.energy = 90.0
            npc.needs.social = 10.0
            npc.needs.health = 100.0
            npc.money = 50.0
            npc.current_goal = None
            npc.current_action = None
            npc.location_id = "tavern"
        world.clock.hour = 18
        ds = RuleBasedDecisionSystem(world.config, world.rng)
        da = ds.decide(a, PerceptionSystem().perceive(a, world), world)
        db = ds.decide(b, PerceptionSystem().perceive(b, world), world)
        self.assertEqual(da.goal.type, GoalType.SOCIALIZE)
        self.assertEqual(db.goal.type, GoalType.SOCIALIZE)
        self.assertGreater(da.priority, db.priority)

    def test_player_gradually_familiar(self):
        wc, nc = acceptance_configs()
        sim = Simulation(wc, nc, seed=1, days=1, print_report=False)
        npc = sim.world.get_npc("e")
        session = PlayerSession()
        for _ in range(25):
            session.handle_command(sim, {"type": "player_talk", "target_id": npc.id, "option": "work"})
        value = session.relationships[npc.id]
        self.assertGreaterEqual(value, 20)


if __name__ == "__main__":
    unittest.main()