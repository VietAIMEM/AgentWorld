"""Pure, deterministic context builder for the LLM layer.

``build_llm_context`` projects only *relevant* information about an NPC into a
JSON-able dict (character, location, time, relationship, a bounded slice of
memories, and the current conversation). It never dumps the world, never
exposes unrelated internal state, never consumes simulation RNG, and never
mutates anything.
"""

from __future__ import annotations

from ..relationships import relationship_tier


def build_llm_context(
    npc,
    world,
    partner=None,
    conversation=None,
    topic=None,
    player=False,
    max_memories=8,
) -> dict:
    location = world.get_location(npc.location_id) if npc.location_id else None
    act = npc.current_action
    goal = npc.current_goal

    relationship = None
    if partner is not None:
        value = npc.relationships.get(partner.id)
        relationship = {
            "npc_id": partner.id,
            "name": partner.name,
            "value": value if value is not None else 0,
            "tier": relationship_tier(value if value is not None else 0),
        }

    return {
        "npc": {
            "id": npc.id,
            "name": npc.name,
            "age": npc.age,
            "job": npc.job.id if npc.job is not None else None,
            "personality": {
                "sociability": npc.personality.sociability,
                "ambition": npc.personality.ambition,
                "risk_tolerance": npc.personality.risk_tolerance,
                "work_ethic": npc.personality.work_ethic,
                "generosity": npc.personality.generosity,
            },
            "emotion": _emotion(npc, world),
            "needs": {
                "hunger": round(npc.needs.hunger, 1),
                "energy": round(npc.needs.energy, 1),
                "social": round(npc.needs.social, 1),
            },
            "goal": goal.type.value if goal is not None else None,
            "action": act.action_type if act is not None else None,
            "intent": npc.intent.kind if npc.intent is not None else None,
        },
        "location": {
            "name": location.name if location is not None else None,
            "type": location.type if location is not None else None,
            "settlement": _settlement_for(world, npc, location),
        },
        "time": {
            "stamp": world.clock.stamp(),
            "day": world.clock.day,
            "hour": world.clock.hour,
            "minute": world.clock.minute,
            "tick": world.clock.tick,
        },
        "relationship": relationship,
        "memories": _selected_memories(npc, partner, max_memories),
        "conversation": {
            "id": conversation.id if conversation is not None else None,
            "stage": conversation.stage if conversation is not None else None,
            "topic": topic,
            "partner": (
                partner.name
                if partner is not None
                else ("the traveler" if player else None)
            ),
        },
        "player": {"present": bool(player), "name": "the traveler" if player else None},
    }


def _settlement_for(world, npc, location):
    if npc.settlement_id is not None:
        return npc.settlement_id
    if location is not None and location.region_id is not None:
        if str(location.region_id).startswith("settlement_"):
            return location.region_id
    return None


def _selected_memories(npc, partner, max_memories):
    """Deterministic bounded slice of memories (partner-related prioritized)."""
    entries = npc.memory.entries
    limit = max(0, int(max_memories))
    if limit == 0 or not entries:
        return []
    if partner is None:
        chosen = list(range(len(entries)))[-limit:]
    else:
        partner_idx = [i for i, e in enumerate(entries) if e.related_entity == partner.id]
        partner_set = set(partner_idx)
        rest = [i for i in range(len(entries)) if i not in partner_set]
        chosen = sorted(partner_idx + rest)[-limit:]
    return [
        {
            "timestamp": entries[i].timestamp,
            "event_type": entries[i].event_type,
            "description": entries[i].description,
            "importance": entries[i].importance,
        }
        for i in chosen
    ]


def _emotion(npc, world) -> str:
    """Deterministic emotion from needs thresholds (mirrors the presentation
    projection but stays inside the npc layer; no import of presentation)."""
    if not npc.alive:
        return "stressed"
    thresholds = world.config.get("needs", {}).get("thresholds", {})
    hunger = float(thresholds.get("hunger", 80))
    energy = float(thresholds.get("energy", 20))
    social = float(thresholds.get("social", 20))
    if npc.needs.hunger >= hunger:
        return "hungry"
    if npc.needs.energy <= energy:
        return "tired"
    if npc.needs.social <= social:
        return "lonely"
    return "content"