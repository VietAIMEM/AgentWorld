from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Optional

from .relationships import relationship_tier

STAGES = ("greeting", "exchange", "farewell")
TOPIC_POOL = ("weather", "work", "food", "market", "family", "recent_event", "relationship")
RELATIONSHIP_TOPIC_THRESHOLD = 1
_EVENT_TOPIC_MEMORY_TYPES = ("recent_event", "festival", "rain")

_TIER_TOPICS = {
    "rival": ("weather", "work"),
    "disliked": ("weather", "work"),
    "stranger": ("weather", "work", "food", "market", "recent_event"),
    "acquaintance": ("weather", "work", "food", "market", "recent_event"),
    "friend": ("weather", "work", "food", "market", "family", "recent_event", "relationship"),
    "close_friend": TOPIC_POOL,
}


def crc32(text: str) -> int:
    """Stable deterministic mixer (never Python's built-in hash())."""
    return zlib.crc32(text.encode("utf-8"))


def threshold_ok(key: str, threshold: float) -> bool:
    """Deterministic threshold test over the stable CRC32 of key."""
    if threshold <= 0.0:
        return False
    if threshold >= 1.0:
        return True
    return (crc32(key) % 100) < int(threshold * 100)


def conversation_config(behavior_cfg: dict) -> dict:
    conv = behavior_cfg.get("conversations", False)
    if isinstance(conv, dict):
        return conv
    return {}


def conversation_settings(behavior_cfg: dict, actions_cfg: dict) -> dict:
    conv = conversation_config(behavior_cfg)
    return {
        "max_turns": max(1, int(conv.get("max_turns", 4))),
        "initiation_threshold": float(conv.get("initiation_threshold", 0.5)),
        "acceptance_threshold": float(conv.get("acceptance_threshold", 0.5)),
        "social_restore_override": float(conv.get("social_restore", 0.0)),
        "relationship_delta_override": int(conv.get("relationship_delta", 0)),
        "social_restore": float(actions_cfg.get("social_restore", 8.0)),
        "relationship_delta": int(actions_cfg.get("relationship_delta", 1)),
    }


@dataclass
class Conversation:
    id: str
    initiator_id: str
    responder_id: str
    topic: Optional[str] = None
    stage: str = "greeting"
    turns_left: int = 4
    started_tick: int = 0
    last_turn_tick: int = 0
    open_slots: int = 2
    started_day: int = 1
    effects_applied: bool = False


class ConversationSystem:
    """Drives the multi-tick conversation lifecycle.

    Pure state machine over Conversation objects. Consumes zero simulation
    RNG. Never imports presentation/rendering modules.
    """

    def __init__(self, config: dict):
        settings = conversation_settings(config.get("behavior", {}), config.get("actions", {}))
        self.max_turns = settings["max_turns"]
        self.social_restore_override = settings["social_restore_override"]
        self.relationship_delta_override = settings["relationship_delta_override"]
        self.social_restore = settings["social_restore"]
        self.relationship_delta = settings["relationship_delta"]

    def tick(self, world) -> None:
        if not getattr(world, "behavior_conversations_enabled", False):
            return
        if not world.conversations:
            return
        for conv in sorted(world.conversations, key=lambda c: c.id):
            if world.clock.tick <= conv.last_turn_tick:
                continue
            if self._must_force_end(conv, world):
                world.force_end_conversation(conv)
                continue
            self._advance(conv, world)

    def _must_force_end(self, conv, world) -> bool:
        if world.clock.tick - conv.started_tick >= self.max_turns + 3:
            return True
        if world.clock.day != conv.started_day:
            return True
        initiator = world.get_npc(conv.initiator_id)
        responder = world.get_npc(conv.responder_id)
        if initiator is None or responder is None or not initiator.alive or not responder.alive:
            return True
        if initiator.location_id != responder.location_id:
            return True
        if initiator.conversation_id != conv.id or responder.conversation_id != conv.id:
            return True
        return False

    def _advance(self, conv, world) -> None:
        if conv.stage == "greeting":
            conv.stage = "exchange"
            conv.topic = self._select_topic(conv, world)
        elif conv.stage == "exchange":
            conv.turns_left -= 1
            if conv.turns_left <= 0:
                conv.stage = "farewell"
        elif conv.stage == "farewell":
            self._apply_farewell(conv, world)
            self._write_memories(conv, world)
            world.end_conversation(conv)
            return
        conv.last_turn_tick = world.clock.tick

    def _apply_farewell(self, conv, world) -> None:
        initiator = world.get_npc(conv.initiator_id)
        responder = world.get_npc(conv.responder_id)
        if initiator is None or responder is None or not initiator.alive or not responder.alive:
            return
        if conv.effects_applied:
            return
        conv.effects_applied = True
        restore = self.social_restore if self.social_restore_override <= 0 else self.social_restore_override
        initiator.needs.social = min(100.0, initiator.needs.social + restore)
        responder.needs.social = min(100.0, responder.needs.social + restore * 0.5)
        delta = self.relationship_delta if self.relationship_delta_override == 0 else self.relationship_delta_override
        compat = (
            initiator.personality.sociability * responder.personality.sociability
            + initiator.personality.generosity * responder.personality.generosity
        ) / 2.0
        before_i2r = initiator.relationships.get(responder.id, 0)
        before_r2i = responder.relationships.get(initiator.id, 0)
        if delta > 0:
            mod_delta = max(0, int(round(delta * compat)))
        else:
            mod_delta = min(0, int(round(delta * compat)))
        initiator.adjust_relationship(responder.id, mod_delta)
        responder.adjust_relationship(initiator.id, mod_delta)
        if getattr(world, "behavior_social_life_enabled", False):
            self._apply_social_life_effects(
                world,
                initiator,
                responder,
                before_i2r,
                before_r2i,
            )
        world.stats.social_interactions += 1

    def _apply_social_life_effects(self, world, initiator, responder, before_i2r, before_r2i) -> None:
        tiers = getattr(world, "_relationship_tiers", None)
        stamp = world.clock.stamp()
        location_name = initiator.location_name(world)
        after_i2r = initiator.relationships.get(responder.id, 0)
        after_r2i = responder.relationships.get(initiator.id, 0)
        tense = relationship_tier(before_i2r, tiers) in ("rival", "disliked") or relationship_tier(
            before_r2i, tiers
        ) in ("rival", "disliked")
        if tense:
            initiator.add_memory(
                stamp,
                "argument",
                f"{initiator.name} had a tense exchange with {responder.name} at {location_name}.",
                3.0,
                responder.id,
            )
            responder.add_memory(
                stamp,
                "argument",
                f"{responder.name} had a tense exchange with {initiator.name} at {location_name}.",
                3.0,
                initiator.id,
            )
        if (
            relationship_tier(before_i2r, tiers) in ("stranger", "acquaintance")
            and relationship_tier(after_i2r, tiers) in ("friend", "close_friend")
        ):
            initiator.add_memory(
                stamp,
                "friendship_milestone",
                f"{initiator.name} became closer friends with {responder.name} at {location_name}.",
                4.0,
                responder.id,
            )
        if (
            relationship_tier(before_r2i, tiers) in ("stranger", "acquaintance")
            and relationship_tier(after_r2i, tiers) in ("friend", "close_friend")
        ):
            responder.add_memory(
                stamp,
                "friendship_milestone",
                f"{responder.name} became closer friends with {initiator.name} at {location_name}.",
                4.0,
                initiator.id,
            )

    def _write_memories(self, conv, world) -> None:
        initiator = world.get_npc(conv.initiator_id)
        responder = world.get_npc(conv.responder_id)
        if initiator is None or responder is None:
            return
        stamp = world.clock.stamp()
        topic = conv.topic or "weather"
        location_name = initiator.location_name(world)
        initiator.add_memory(
            stamp, "met_npc", f"{initiator.name} talked to {responder.name} at {location_name}.", 3.0, responder.id
        )
        responder.add_memory(
            stamp, "met_npc", f"{responder.name} talked to {initiator.name} at {location_name}.", 3.0, initiator.id
        )
        initiator.add_memory(
            stamp,
            "conversation",
            f"{initiator.name} and {responder.name} discussed {topic} at {location_name}.",
            3.0,
            responder.id,
        )
        responder.add_memory(
            stamp,
            "conversation",
            f"{responder.name} and {initiator.name} discussed {topic} at {location_name}.",
            3.0,
            initiator.id,
        )

    def _candidate_topics(self, conv, world) -> list[str]:
        initiator = world.get_npc(conv.initiator_id)
        responder = world.get_npc(conv.responder_id)
        candidates = ["weather"]
        if initiator.job is not None and responder.job is not None:
            candidates.append("work")
        if self._food_context(initiator) or self._food_context(responder):
            candidates.append("food")
        if self._market_context(initiator, world) or self._market_context(responder, world):
            candidates.append("market")
        if self._has_memory(initiator, "family") or self._has_memory(responder, "family"):
            candidates.append("family")
        if self._recent_event_available(initiator, responder, world):
            candidates.append("recent_event")
        if self._relationship_above_threshold(initiator, responder) or self._relationship_above_threshold(
            responder, initiator
        ):
            candidates.append("relationship")
        if getattr(world, "behavior_social_life_enabled", False):
            candidates = self._tier_filtered_topics(
                initiator, responder, candidates, getattr(world, "_relationship_tiers", None)
            )
        return sorted(candidates)

    def _tier_filtered_topics(self, initiator, responder, candidates: list[str], tiers_cfg) -> list[str]:
        tier = relationship_tier(initiator.relationships.get(responder.id, 0), tiers_cfg)
        allowed = _TIER_TOPICS.get(tier, TOPIC_POOL)
        filtered = [topic for topic in candidates if topic in allowed]
        if not filtered:
            return ["weather"]
        return filtered

    def _select_topic(self, conv, world) -> str:
        candidates = self._candidate_topics(conv, world)
        return min(
            candidates,
            key=lambda topic: crc32(f"{conv.id}|{conv.turns_left}|{topic}"),
        )

    @staticmethod
    def _food_context(npc) -> bool:
        return npc.inventory.get("food", 0) > 0 or npc.needs.hunger > 50.0

    @staticmethod
    def _market_context(npc, world) -> bool:
        location = world.get_location(npc.location_id)
        if location is not None and location.type == "commercial":
            return True
        return any(entry.event_type in ("buy_food", "shopping") for entry in npc.memory.entries)

    @staticmethod
    def _has_memory(npc, event_type: str) -> bool:
        return any(entry.event_type == event_type for entry in npc.memory.entries)

    def _recent_event_available(self, initiator, responder, world) -> bool:
        if any(entry.event_type in _EVENT_TOPIC_MEMORY_TYPES for entry in initiator.memory.entries):
            return True
        if any(entry.event_type in _EVENT_TOPIC_MEMORY_TYPES for entry in responder.memory.entries):
            return True
        return bool(world.active_events())

    @staticmethod
    def _relationship_above_threshold(npc, other) -> bool:
        return npc.relationships.get(other.id, 0) >= RELATIONSHIP_TOPIC_THRESHOLD