import unittest

from world_sim.npc.llm import LLMCache, LLMResponse


class TestLLMCache(unittest.TestCase):
    def test_put_get_roundtrip(self):
        cache = LLMCache(enabled=True, max_entries=8)
        resp = LLMResponse(dialogue="hello", emotion="happy", source="llm")
        cache.put("k1", resp)
        got = cache.get("k1")
        self.assertIs(got, resp)

    def test_miss_returns_none(self):
        cache = LLMCache(enabled=True, max_entries=8)
        self.assertIsNone(cache.get("missing"))

    def test_disabled_cache_never_stores(self):
        cache = LLMCache(enabled=False, max_entries=8)
        cache.put("k1", LLMResponse(dialogue="x", source="llm"))
        self.assertIsNone(cache.get("k1"))

    def test_fallback_responses_not_stored(self):
        cache = LLMCache(enabled=True, max_entries=8)
        cache.put("k1", LLMResponse(dialogue="x", source="fallback"))
        self.assertIsNone(cache.get("k1"))

    def test_fifo_eviction(self):
        cache = LLMCache(enabled=True, max_entries=2)
        a, b, c = LLMResponse("a", source="llm"), LLMResponse("b", source="llm"), LLMResponse("c", source="llm")
        cache.put("k1", a)
        cache.put("k2", b)
        self.assertIs(cache.get("k1"), a)
        cache.put("k3", c)
        self.assertIsNone(cache.get("k1"))
        self.assertIs(cache.get("k2"), b)
        self.assertIs(cache.get("k3"), c)

    def test_eviction_is_fifo_regardless_of_access(self):
        cache = LLMCache(enabled=True, max_entries=2)
        a, b, c = LLMResponse("a", source="llm"), LLMResponse("b", source="llm"), LLMResponse("c", source="llm")
        cache.put("k1", a)
        cache.put("k2", b)
        cache.get("k1")
        cache.put("k3", c)
        self.assertIsNone(cache.get("k1"))
        self.assertIs(cache.get("k2"), b)
        self.assertIs(cache.get("k3"), c)

    def test_size_bounded(self):
        cache = LLMCache(enabled=True, max_entries=16)
        for i in range(40):
            cache.put(f"k{i}", LLMResponse(f"x{i}", source="llm"))
        self.assertEqual(len(cache), 16)


if __name__ == "__main__":
    unittest.main()