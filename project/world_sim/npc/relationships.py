from __future__ import annotations

from typing import Optional

RELATIONSHIP_TIERS = ("rival", "disliked", "stranger", "acquaintance", "friend", "close_friend")

TIER_RANK = {tier: i for i, tier in enumerate(RELATIONSHIP_TIERS)}

PLAYER_TIERS = ("stranger", "acquaintance", "friend")

DEFAULT_TIER_THRESHOLDS = {
    "friend": 20,
    "close_friend": 60,
    "acquaintance": 1,
    "disliked": -20,
    "rival": -60,
}

DEFAULT_PLAYER_THRESHOLDS = {
    "friend": 20,
    "acquaintance": 1,
}


def relationship_tiers_config(behavior_cfg: dict) -> dict:
    """Resolve the configured relationship tier thresholds (additive defaults)."""
    tiers = dict(DEFAULT_TIER_THRESHOLDS)
    social_life = behavior_cfg.get("social_life", False)
    if isinstance(social_life, dict):
        configured = social_life.get("relationship_tiers", {})
        if isinstance(configured, dict):
            for key, value in configured.items():
                if key in tiers:
                    tiers[key] = int(value)
    return tiers


def relationship_tier(value: int, tiers_cfg: Optional[dict] = None) -> str:
    """Map a relationship value to a deterministic tier (pure, no RNG)."""
    cfg = tiers_cfg if tiers_cfg is not None else DEFAULT_TIER_THRESHOLDS
    value = int(round(value))
    if value <= int(cfg.get("rival", DEFAULT_TIER_THRESHOLDS["rival"])):
        return "rival"
    if value <= int(cfg.get("disliked", DEFAULT_TIER_THRESHOLDS["disliked"])):
        return "disliked"
    if value >= int(cfg.get("close_friend", DEFAULT_TIER_THRESHOLDS["close_friend"])):
        return "close_friend"
    if value >= int(cfg.get("friend", DEFAULT_TIER_THRESHOLDS["friend"])):
        return "friend"
    if value >= int(cfg.get("acquaintance", DEFAULT_TIER_THRESHOLDS["acquaintance"])):
        return "acquaintance"
    return "stranger"


def player_tier(value: int) -> str:
    """Map the player's relationship value to a player-facing tier.

    The player side deliberately uses only stranger / acquaintance / friend.
    """
    if value >= DEFAULT_PLAYER_THRESHOLDS["friend"]:
        return "friend"
    if value >= DEFAULT_PLAYER_THRESHOLDS["acquaintance"]:
        return "acquaintance"
    return "stranger"


def social_familiarity(npc, other) -> tuple:
    """Deterministic familiarity measure derived from existing state.

    Returns (relationship_value, partner_memory_count). Never consumes RNG
    and never mutates anything.
    """
    value = npc.relationships.get(other.id, 0)
    memory_count = sum(1 for entry in npc.memory.entries if entry.related_entity == other.id)
    return value, memory_count


def select_social_partner(npc, nearby, tiers_cfg: Optional[dict] = None) -> Optional[object]:
    """Deterministic friend-based social targeting.

    Prefers close friends > friends > acquaintances > strangers > disliked >
    rivals, breaking ties by NPC id ordering. Consumes zero simulation RNG.
    """
    if not nearby:
        return None
    cfg = tiers_cfg if tiers_cfg is not None else DEFAULT_TIER_THRESHOLDS

    def key(other):
        tier = relationship_tier(npc.relationships.get(other.id, 0), cfg)
        return (-TIER_RANK[tier], other.id)

    return min(nearby, key=key)


def social_event_label(event, world) -> Optional[str]:
    """Deterministic social-event classification for an existing WorldEvent.

    Pure derivation from (event.type, location.type); never consumes RNG and
    never mutates state. Returns None when the event has no social character.
    """
    if event.type == "rain":
        return None
    if event.type == "festival":
        return "festival"
    location = world.get_location(event.location_id) if event.location_id else None
    location_type = location.type if location is not None else None
    if location_type == "social":
        return "tavern_gathering"
    if location_type == "commercial":
        return "market_gathering"
    if location_type in ("workplace", "farm"):
        return "work_gathering"
    if location_type == "residence":
        return "communal_meal"
    return None