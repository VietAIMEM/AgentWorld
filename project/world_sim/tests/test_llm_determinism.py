import tempfile
import unittest
from pathlib import Path

from world_sim.npc.llm import LLMLayer, StaticProvider, build_llm_layer, llm_config
from world_sim.presentation.snapshot import build_payload
from world_sim.presentation.transport import ManagedSimulation
from world_sim.simulation.persistence import save_state
from world_sim.tests.helpers import load_configs


def base_configs(gen_seed=42):
    wc, nc = load_configs()
    gen = dict(wc["world_generation"])
    gen["enabled"] = True
    gen["seed"] = gen_seed
    wc["world_generation"] = gen
    se = dict(wc["settlement_economy"])
    se["enabled"] = True
    wc["settlement_economy"] = se
    wc["behavior"] = {
        "enabled": True,
        "routines": {"enabled": True, "default_bias": 0.5},
        "objects": {"enabled": True},
        "interactions": True,
        "conversations": {"enabled": True, "max_turns": 4},
    }
    return wc, nc


def run_ticks(runner, n):
    for _ in range(n):
        runner._one_tick()


def save_bytes(sim):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        save_state(sim, path)
        return path.read_bytes()


class TestLLMDeterminism(unittest.TestCase):
    TICKS = 60

    def _runner(self, variant):
        wc, nc = base_configs()
        llm = None
        if variant == "disabled":
            wc["behavior"]["llm"] = {"enabled": False}
        elif variant == "enabled":
            wc["behavior"]["llm"] = {"enabled": True, "provider": "static"}
            llm = LLMLayer(llm_config(wc["behavior"]), provider=StaticProvider())
        return ManagedSimulation(wc, nc, seed=5, days=30, store=None, llm=llm)

    def _snapshot_without_thought(self, payload):
        cleaned = []
        for entry in payload["npcs"]:
            e = dict(entry)
            e.pop("thought", None)
            cleaned.append(e)
        return cleaned

    def test_enabled_matches_disabled_sim_state(self):
        base = self._runner("baseline")
        dis = self._runner("disabled")
        ena = self._runner("enabled")
        try:
            run_ticks(base, self.TICKS)
            run_ticks(dis, self.TICKS)
            run_ticks(ena, self.TICKS)
            self.assertEqual(save_bytes(base.simulation), save_bytes(dis.simulation))
            self.assertEqual(save_bytes(base.simulation), save_bytes(ena.simulation))
            self.assertEqual(base.simulation.rng.getstate(), ena.simulation.rng.getstate())
            draws = [ena.simulation.rng.random() for _ in range(100)]
            self.assertEqual(draws, [base.simulation.rng.random() for _ in range(100)])
        finally:
            base.stop()
            dis.stop()
            ena.stop()

    def test_llm_active_in_enabled_variant(self):
        ena = self._runner("enabled")
        try:
            run_ticks(ena, self.TICKS)
            ena.llm.poll()
            any_thought = any(n.thought for n in ena.simulation.world.npcs)
            self.assertTrue(any_thought)
        finally:
            ena.stop()

    def test_disabled_payload_has_no_thought_keys(self):
        dis = self._runner("disabled")
        base = self._runner("baseline")
        try:
            run_ticks(dis, self.TICKS)
            run_ticks(base, self.TICKS)
            base_payload = build_payload(base.simulation)
            dis_payload = build_payload(dis.simulation)
            self.assertEqual(len(base_payload["npcs"]), len(dis_payload["npcs"]))
            for entry in dis_payload["npcs"]:
                self.assertNotIn("thought", entry)
            self.assertEqual(self._snapshot_without_thought(dis_payload),
                             self._snapshot_without_thought(base_payload))
        finally:
            dis.stop()
            base.stop()

    def test_enabled_payload_only_adds_thought(self):
        base = self._runner("baseline")
        ena = self._runner("enabled")
        try:
            run_ticks(base, self.TICKS)
            run_ticks(ena, self.TICKS)
            ena.llm.poll()
            base_payload = build_payload(base.simulation)
            ena_payload = build_payload(ena.simulation)
            self.assertEqual(self._snapshot_without_thought(ena_payload),
                             self._snapshot_without_thought(base_payload))
            thought_keys = [e.get("thought") for e in ena_payload["npcs"] if "thought" in e]
            self.assertTrue(any(thought_keys))
        finally:
            base.stop()
            ena.stop()


if __name__ == "__main__":
    unittest.main()