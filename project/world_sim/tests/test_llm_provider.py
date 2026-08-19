import json
import time
import unittest

from world_sim.npc.llm import (
    LLMError,
    LLMExecutor,
    LLMRequest,
    OpenAICompatibleProvider,
    StaticProvider,
)


class TestProviders(unittest.TestCase):
    def test_openai_provider_unavailable_without_url(self):
        prov = OpenAICompatibleProvider(url="")
        self.assertFalse(prov.available())
        with self.assertRaises(LLMError):
            prov.generate(LLMRequest(system="s", user="u"))

    def test_openai_provider_uses_env(self, *_):
        import os

        old = {k: os.environ.get(k) for k in ("NPC_LLM_API_URL", "NPC_LLM_API_KEY", "NPC_LLM_MODEL")}
        try:
            os.environ["NPC_LLM_API_URL"] = "http://unused.local/chat"
            os.environ["NPC_LLM_API_KEY"] = "secret"
            os.environ["NPC_LLM_MODEL"] = "test-model"
            prov = OpenAICompatibleProvider()
            self.assertTrue(prov.available())
            self.assertEqual(prov.model, "test-model")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_static_provider_valid_json(self):
        prov = StaticProvider(json_text=json.dumps({"dialogue": "hi"}))
        req = LLMRequest(system="s", user="u", topic="work")
        out = prov.generate(req)
        self.assertEqual(json.loads(out)["dialogue"], "hi")

    def test_static_provider_default_json(self):
        prov = StaticProvider()
        req = LLMRequest(system="s", user="u", topic="market")
        data = json.loads(prov.generate(req))
        self.assertIn("topic", data)
        self.assertEqual(data["topic"], "market")

    def test_error_provider_unavailable_and_raises(self):
        prov = StaticProvider(error=LLMError("boom"))
        self.assertFalse(prov.available())
        with self.assertRaises(LLMError):
            prov.generate(LLMRequest(system="s", user="u"))

    def test_static_provider_delay(self):
        prov = StaticProvider(delay=0.05)
        start = time.time()
        prov.generate(LLMRequest(system="s", user="u"))
        self.assertGreaterEqual(time.time() - start, 0.04)


class TestExecutor(unittest.TestCase):
    def test_submit_forwards_args(self):
        captured = {}

        def worker(a, b):
            captured["sum"] = a + b
            return a + b

        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            fut = ex.submit(worker, 2, 3)
            self.assertEqual(fut.result(), 5)
            self.assertEqual(captured["sum"], 5)
        finally:
            ex.shutdown()

    def test_submit_error_surfaces_in_future(self):
        def worker():
            raise LLMError("fail")

        prov = StaticProvider()
        ex = LLMExecutor(prov)
        try:
            fut = ex.submit(worker)
            with self.assertRaises(LLMError):
                fut.result()
        finally:
            ex.shutdown()

    def test_shutdown_is_idempotent(self):
        ex = LLMExecutor(StaticProvider())
        ex.shutdown()
        ex.shutdown()


if __name__ == "__main__":
    unittest.main()