import unittest

from world_sim.npc.conversation import (
    ConversationSystem,
    TOPIC_POOL,
    threshold_ok,
)
from world_sim.npc.relationships import (
    DEFAULT_TIER_THRESHOLDS,
    TIER_RANK,
    relationship_tier,
    relationship_tiers_config,
    select_social_partner,
    social_event_label,
    social_familiarity,
    player_tier,
)
from world_sim.simulation.events import WorldEvent
from world_sim.tests.helpers import build_world, load_configs


def social_world(seed=1, enabled=True):
    wc, nc = load_configs()
    wc["behavior"] = {
        "enabled": True,
        "conversations": {"enabled": True, "max_turns": 4},
        "social_life": {"enabled": enabled, "social_events": True},
    }
    return build_world(seed, wc, nc)


def _init_key(a, b, day, hour):
    return f"init|{a.id}|{b.id}|{day}|{hour}"


def _accept_key(a, b, day, hour):
    return f"accept|{b.id}|{a.id}|{day}|{hour}"


def _hour_ok(a, b, day, hour):
    return threshold_ok(_init_key(a, b, day, hour), 0.5) and threshold_ok(
        _accept_key(a, b, day, hour), 0.5
    )


def _find_hour(world, a, b):
    for day in range(1, 8):
        for hour in range(24):
            if _hour_ok(a, b, day, hour):
                world.clock.day = day
                world.clock.hour = hour
                return
    raise AssertionError("no suitable deterministic hour found")


class TestRelationshipTier(unittest.TestCase):
    def test_default_thresholds(self):
        self.assertEqual(DEFAULT_TIER_THRESHOLDS["friend"], 20)
        self.assertEqual(DEFAULT_TIER_THRESHOLDS["close_friend"], 60)
        self.assertEqual(DEFAULT_TIER_THRESHOLDS["acquaintance"], 1)
        self.assertEqual(DEFAULT_TIER_THRESHOLDS["disliked"], -20)
        self.assertEqual(DEFAULT_TIER_THRESHOLDS["rival"], -60)

    def test_rival_boundary(self):
        self.assertEqual(relationship_tier(-60), "rival")
        self.assertEqual(relationship_tier(-100), "rival")
        self.assertEqual(relationship_tier(-61), "rival")

    def test_disliked_band(self):
        self.assertEqual(relationship_tier(-59), "disliked")
        self.assertEqual(relationship_tier(-20), "disliked")

    def test_stranger_band(self):
        self.assertEqual(relationship_tier(-19), "stranger")
        self.assertEqual(relationship_tier(0), "stranger")

    def test_acquaintance_band(self):
        self.assertEqual(relationship_tier(1), "acquaintance")
        self.assertEqual(relationship_tier(19), "acquaintance")

    def test_friend_band(self):
        self.assertEqual(relationship_tier(20), "friend")
        self.assertEqual(relationship_tier(59), "friend")

    def test_close_friend_band(self):
        self.assertEqual(relationship_tier(60), "close_friend")
        self.assertEqual(relationship_tier(100), "close_friend")

    def test_custom_thresholds(self):
        cfg = {
            "friend": 30,
            "close_friend": 70,
            "acquaintance": 5,
            "disliked": -10,
            "rival": -40,
        }
        self.assertEqual(relationship_tier(25, cfg), "acquaintance")
        self.assertEqual(relationship_tier(5, cfg), "acquaintance")
        self.assertEqual(relationship_tier(30, cfg), "friend")
        self.assertEqual(relationship_tier(70, cfg), "close_friend")
        self.assertEqual(relationship_tier(-11, cfg), "disliked")
        self.assertEqual(relationship_tier(-40, cfg), "rival")

    def test_rank_order(self):
        order = ["rival", "disliked", "stranger", "acquaintance", "friend", "close_friend"]
        ranks = [TIER_RANK[tier] for tier in order]
        self.assertEqual(ranks, sorted(ranks))
        self.assertGreater(TIER_RANK["close_friend"], TIER_RANK["friend"])
        self.assertGreater(TIER_RANK["friend"], TIER_RANK["stranger"])


class TestTierConfig(unittest.TestCase):
    def test_defaults_when_missing(self):
        self.assertEqual(relationship_tiers_config({}), DEFAULT_TIER_THRESHOLDS)

    def test_defaults_when_behavior_missing(self):
        self.assertEqual(relationship_tiers_config({"routines": {}}), DEFAULT_TIER_THRESHOLDS)

    def test_custom_merge(self):
        cfg = relationship_tiers_config(
            {"social_life": {"enabled": True, "relationship_tiers": {"friend": 10, "rival": -50}}}
        )
        self.assertEqual(cfg["friend"], 10)
        self.assertEqual(cfg["rival"], -50)
        self.assertEqual(cfg["close_friend"], 60)
        self.assertEqual(cfg["acquaintance"], 1)
        self.assertEqual(cfg["disliked"], -20)

    def test_non_dict_social_life_uses_defaults(self):
        self.assertEqual(relationship_tiers_config({"social_life": True}), DEFAULT_TIER_THRESHOLDS)


class TestPlayerTier(unittest.TestCase):
    def test_stranger(self):
        self.assertEqual(player_tier(0), "stranger")
        self.assertEqual(player_tier(-10), "stranger")

    def test_acquaintance(self):
        self.assertEqual(player_tier(1), "acquaintance")
        self.assertEqual(player_tier(19), "acquaintance")

    def test_friend(self):
        self.assertEqual(player_tier(20), "friend")
        self.assertEqual(player_tier(100), "friend")


class TestSocialFamiliarity(unittest.TestCase):
    def test_familiarity_from_relationships_and_memories(self):
        world = build_world()
        a, b = world.npcs[0], world.npcs[1]
        a.relationships[b.id] = 7
        a.add_memory("t1", "met_npc", "met", 3.0, b.id)
        a.add_memory("t2", "conversation", "talked", 3.0, b.id)
        a.add_memory("t3", "worked_with", "worked", 2.0, "someone_else")
        value, count = social_familiarity(a, b)
        self.assertEqual(value, 7)
        self.assertEqual(count, 2)

    def test_familiarity_never_mutates(self):
        world = build_world()
        a, b = world.npcs[0], world.npcs[1]
        before = (dict(a.relationships), len(a.memory.entries))
        social_familiarity(a, b)
        self.assertEqual(dict(a.relationships), before[0])
        self.assertEqual(len(a.memory.entries), before[1])


class TestSocialEventLabel(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def event(self, event_type, location_id=None):
        return WorldEvent(
            id="e",
            type=event_type,
            description="d",
            start_tick=0,
            duration_ticks=1,
            location_id=location_id,
        )

    def test_festival_is_festival(self):
        self.assertEqual(social_event_label(self.event("festival", "market"), self.world), "festival")

    def test_rain_is_not_social(self):
        self.assertIsNone(social_event_label(self.event("rain", "forest"), self.world))

    def test_social_location(self):
        self.assertEqual(social_event_label(self.event("gathering", "tavern"), self.world), "tavern_gathering")

    def test_commercial_location(self):
        self.assertEqual(
            social_event_label(self.event("gathering", "market"), self.world), "market_gathering"
        )

    def test_workplace_location(self):
        self.assertEqual(social_event_label(self.event("gathering", "farm"), self.world), "work_gathering")

    def test_residence_location(self):
        self.assertEqual(social_event_label(self.event("gathering", "home"), self.world), "communal_meal")

    def test_unknown_location(self):
        self.assertIsNone(social_event_label(self.event("gathering", "nowhere"), self.world))


class TestSelectSocialPartner(unittest.TestCase):
    def setUp(self):
        self.world = build_world()
        self.npc = self.world.npcs[0]
        self.others = self.world.npcs[1:]

    def test_empty_returns_none(self):
        self.assertIsNone(select_social_partner(self.npc, [], None))

    def test_friend_preferred_over_stranger(self):
        friend = self.others[0]
        stranger = self.others[1]
        self.npc.relationships[friend.id] = 30
        chosen = select_social_partner(self.npc, [stranger, friend], None)
        self.assertEqual(chosen.id, friend.id)

    def test_close_friend_preferred_over_friend(self):
        close = self.others[0]
        friend = self.others[1]
        self.npc.relationships[close.id] = 70
        self.npc.relationships[friend.id] = 30
        chosen = select_social_partner(self.npc, [friend, close], None)
        self.assertEqual(chosen.id, close.id)

    def test_acquaintance_preferred_over_stranger(self):
        acquaintance = self.others[0]
        stranger = self.others[1]
        self.npc.relationships[acquaintance.id] = 5
        chosen = select_social_partner(self.npc, [stranger, acquaintance], None)
        self.assertEqual(chosen.id, acquaintance.id)

    def test_stranger_preferred_over_disliked(self):
        stranger = self.others[0]
        disliked = self.others[1]
        self.npc.relationships[disliked.id] = -30
        chosen = select_social_partner(self.npc, [disliked, stranger], None)
        self.assertEqual(chosen.id, stranger.id)

    def test_tie_broken_by_lowest_id(self):
        self.npc.relationships = {}
        chosen = select_social_partner(self.npc, self.others, None)
        self.assertEqual(chosen.id, min(other.id for other in self.others))

    def test_deterministic(self):
        self.npc.relationships[self.others[0].id] = 40
        self.npc.relationships[self.others[1].id] = 10
        first = select_social_partner(self.npc, self.others, None)
        second = select_social_partner(self.npc, self.others, None)
        self.assertEqual(first.id, second.id)

    def test_respects_custom_thresholds(self):
        cfg = relationship_tiers_config(
            {"social_life": {"enabled": True, "relationship_tiers": {"friend": 5}}}
        )
        mild = self.others[0]
        stranger = self.others[1]
        self.npc.relationships[mild.id] = 6
        chosen = select_social_partner(self.npc, [stranger, mild], cfg)
        self.assertEqual(chosen.id, mild.id)


class TestTierTopics(unittest.TestCase):
    def setUp(self):
        self.world = social_world()
        self.a, self.b = self.world.npcs[0], self.world.npcs[1]
        self.a.location_id = "market"
        self.b.location_id = "market"
        self.system = ConversationSystem(self.world.config)

    def _candidates(self):
        _find_hour(self.world, self.a, self.b)
        conv = self.world.start_conversation(self.a, self.b.id)
        self.assertIsNotNone(conv)
        return self.system._candidate_topics(conv, self.world)

    def test_stranger_topics_are_shallow(self):
        self.a.relationships = {}
        candidates = self._candidates()
        self.assertNotIn("relationship", candidates)
        self.assertNotIn("family", candidates)
        self.assertTrue(set(candidates).issubset({"weather", "work", "food", "market", "recent_event"}))

    def test_friend_topics_include_family_and_relationship(self):
        self.a.relationships[self.b.id] = 30
        self.a.add_memory("t", "family", "family memory", 3.0)
        candidates = self._candidates()
        self.assertIn("relationship", candidates)
        self.assertIn("family", candidates)

    def test_close_friend_topics_allow_relationship(self):
        self.a.relationships[self.b.id] = 70
        candidates = self._candidates()
        self.assertIn("relationship", candidates)

    def test_rival_topics_are_minimal(self):
        self.a.relationships[self.b.id] = -70
        candidates = self._candidates()
        self.assertTrue(set(candidates).issubset({"weather", "work"}))

    def test_topics_stay_in_pool(self):
        self.a.relationships[self.b.id] = 70
        candidates = self._candidates()
        self.assertTrue(set(candidates).issubset(set(TOPIC_POOL)))

    def test_selection_is_deterministic(self):
        self.a.relationships[self.b.id] = 30
        _find_hour(self.world, self.a, self.b)
        conv = self.world.start_conversation(self.a, self.b.id)
        self.assertIsNotNone(conv)
        first = self.system._select_topic(conv, self.world)
        second = self.system._select_topic(conv, self.world)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()