import json
import unittest

from world_sim.npc.llm import LLMResponse, MAX_DIALOGUE_LENGTH, validate_llm_response


def _fallback():
    return LLMResponse(dialogue="fb", emotion="content", topic=None, source="fallback")


class TestValidation(unittest.TestCase):
    def _validate(self, raw):
        return validate_llm_response(raw, _fallback())

    def test_valid_payload(self):
        raw = json.dumps(
            {"dialogue": "Hello there!", "emotion": "happy", "topic": "work", "follow_up": "farewell"}
        )
        r = self._validate(raw)
        self.assertEqual(r.dialogue, "Hello there!")
        self.assertEqual(r.emotion, "happy")
        self.assertEqual(r.topic, "work")
        self.assertEqual(r.follow_up, "farewell")
        self.assertTrue(r.llm)

    def test_minimal_payload(self):
        r = self._validate(json.dumps({"dialogue": "Hi"}))
        self.assertEqual(r.dialogue, "Hi")
        self.assertTrue(r.llm)

    def test_non_string_returns_fallback(self):
        r = self._validate(42)
        self.assertFalse(r.llm)
        self.assertEqual(r.dialogue, "fb")

    def test_invalid_json_returns_fallback(self):
        r = self._validate("{not json")
        self.assertFalse(r.llm)
        self.assertEqual(r.dialogue, "fb")

    def test_non_dict_returns_fallback(self):
        r = self._validate("[1,2,3]")
        self.assertFalse(r.llm)

    def test_missing_or_non_string_dialogue(self):
        self.assertFalse(self._validate(json.dumps({"emotion": "happy"})).llm)
        self.assertFalse(self._validate(json.dumps({"dialogue": 12})).llm)

    def test_overlong_dialogue_returns_fallback(self):
        long = json.dumps({"dialogue": "x" * (MAX_DIALOGUE_LENGTH + 1)})
        r = self._validate(long)
        self.assertFalse(r.llm)

    def test_whitespace_only_dialogue_returns_fallback(self):
        r = self._validate(json.dumps({"dialogue": "   "}))
        self.assertFalse(r.llm)

    def test_unknown_emotion_falls_back_to_fallback_emotion(self):
        raw = json.dumps({"dialogue": "hi", "emotion": "euphoric", "topic": "work"})
        r = self._validate(raw)
        self.assertTrue(r.llm)
        self.assertEqual(r.emotion, "content")

    def test_known_emotions_allowed(self):
        for emotion in ("content", "happy", "calm", "worried", "hungry", "tired", "lonely", "stressed"):
            r = self._validate(json.dumps({"dialogue": "hi", "emotion": emotion}))
            self.assertTrue(r.llm)
            self.assertEqual(r.emotion, emotion)

    def test_unknown_topic_falls_back(self):
        raw = json.dumps({"dialogue": "hi", "topic": "bogus_topic"})
        r = self._validate(raw)
        self.assertTrue(r.llm)
        self.assertIsNone(r.topic)

    def test_known_topics_allowed(self):
        for topic in ("weather", "work", "food", "market", "family", "recent_event",
                      "relationship", "place", "greeting", "farewell"):
            r = self._validate(json.dumps({"dialogue": "hi", "topic": topic}))
            self.assertTrue(r.llm)
            self.assertEqual(r.topic, topic)

    def test_unknown_follow_up_cleared(self):
        raw = json.dumps({"dialogue": "hi", "follow_up": "attack"})
        r = self._validate(raw)
        self.assertTrue(r.llm)
        self.assertIsNone(r.follow_up)

    def test_code_fenced_json_accepted(self):
        raw = '```json\n{"dialogue": "fenced", "emotion": "calm"}\n```'
        r = self._validate(raw)
        self.assertTrue(r.llm)
        self.assertEqual(r.dialogue, "fenced")

    def test_control_characters_stripped(self):
        raw = json.dumps({"dialogue": "hi\x00\x07there\x1f"})
        r = self._validate(raw)
        self.assertTrue(r.llm)
        self.assertEqual(r.dialogue, "hithere")


if __name__ == "__main__":
    unittest.main()