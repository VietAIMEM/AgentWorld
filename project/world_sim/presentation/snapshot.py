"""Deterministic presentation snapshot/payload for the Unity client.

This module is strictly presentational and additive:

- `build_payload` derives a versioned JSON-able payload from the simulation
  using only `world_sim.presentation.animation.animate` (a pure projection).
- `serialize_payload` produces deterministic JSON (sorted keys).
- `coerce_payload` normalizes arbitrary payload dicts into the Unity-consumable
  shape (fills optional-field defaults, falls back unknown poses to ``idle``,
  and nulls targets that do not resolve against the payload's entities).

None of these functions mutate simulation state and none consume simulation RNG.
Simulation/AI systems must never import this module.
"""

from __future__ import annotations

import json

from .animation import AnimationState, animate

VERSION = 1

# Pose values produced by the animation projection plus the full spec set.
KNOWN_POSES = frozenset(
    {
        "idle",
        "walk",
        "work",
        "eat",
        "buy",
        "sleep",
        "sit",
        "stand",
        "talk",
        "listen",
        "wave",
        "inspect",
        "stretch",
        "interact",
        "dead",
    }
)

_NPC_DEFAULTS = {
    "npc_id": "",
    "name": "",
    "pose": "idle",
    "moving": False,
    "behavior_state": "idle",
    "facing_location_id": None,
    "facing_object_id": None,
    "facing_npc_id": None,
    "target_location_id": None,
    "target_npc_id": None,
    "target_object_id": None,
    "emotion": "content",
    "in_conversation": False,
    "intent": None,
    "pose_progress": 0.0,
    "tone": "neutral",
}

_PAYLOAD_FIELDS = (
    "npc_id",
    "name",
    "pose",
    "moving",
    "behavior_state",
    "facing_location_id",
    "facing_object_id",
    "facing_npc_id",
    "target_location_id",
    "target_npc_id",
    "target_object_id",
    "emotion",
    "in_conversation",
    "intent",
    "pose_progress",
    "tone",
)


def _state_to_dict(state: AnimationState, name: str, thought=None) -> dict:
    entry = {
        "npc_id": state.npc_id,
        "name": name,
        "pose": state.pose,
        "moving": state.moving,
        "behavior_state": state.behavior_state,
        "facing_location_id": state.facing_location_id,
        "facing_object_id": state.facing_object_id,
        "facing_npc_id": state.facing_npc_id,
        "target_location_id": state.target_location_id,
        "target_npc_id": state.target_npc_id,
        "target_object_id": state.target_object_id,
        "emotion": state.emotion,
        "in_conversation": state.in_conversation,
        "intent": state.intent,
        "pose_progress": state.pose_progress,
        "tone": state.tone,
    }
    if thought is not None:
        entry["thought"] = thought
    return entry


def build_payload(sim) -> dict:
    """Build the versioned presentation payload from a Simulation.

    Pure: reads state only, never mutates it, never draws simulation RNG.
    NPCs are listed in world order (stable), locations are sorted by id.
    """
    world = sim.world
    npcs = []
    for npc in world.npcs:
        state = animate(npc, world)
        npcs.append(_state_to_dict(state, npc.name, npc.thought))

    payload = {
        "version": VERSION,
        "tick": world.clock.tick,
        "day": world.clock.day,
        "hour": world.clock.hour,
        "minute": world.clock.minute,
        "npcs": npcs,
    }
    if world.objects:
        payload["objects"] = [
            {
                "object_id": obj.id,
                "name": obj.name,
                "location_id": obj.location_id,
                "object_type": obj.object_type,
                "state": obj.state,
            }
            for obj in world.objects
        ]
    if world.locations:
        payload["locations"] = [
            {
                "location_id": lid,
                "name": loc.name,
                "type": loc.type,
                "x": loc.position[0] if loc.position is not None else None,
                "z": loc.position[1] if loc.position is not None else None,
            }
            for lid, loc in sorted(world.locations.items())
        ]
    return payload


def serialize_payload(payload: dict) -> str:
    """Deterministic JSON serialization (sorted keys, compact separators)."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _resolve_target(value, known_ids):
    if value is None:
        return None
    return value if value in known_ids else None


def coerce_payload(data: dict) -> dict:
    """Normalize an arbitrary payload dict into the Unity-compatible shape.

    - Fills missing optional NPC fields from defaults.
    - Falls unknown poses back to ``idle``.
    - Nulls facing/target ids that do not resolve against the payload's
      NPC / object / location id sets.
    """
    npcs_in = data.get("npcs", [])
    npc_ids = {entry.get("npc_id") for entry in npcs_in if entry.get("npc_id")}
    object_ids = {
        entry.get("object_id")
        for entry in data.get("objects", [])
        if entry.get("object_id")
    }
    location_ids = {
        entry.get("location_id")
        for entry in data.get("locations", [])
        if entry.get("location_id")
    }

    npcs = []
    for entry in npcs_in:
        merged = dict(_NPC_DEFAULTS)
        if isinstance(entry, dict):
            merged.update(entry)
        if merged.get("pose") not in KNOWN_POSES:
            merged["pose"] = "idle"
        merged["facing_location_id"] = _resolve_target(merged.get("facing_location_id"), location_ids)
        merged["facing_object_id"] = _resolve_target(merged.get("facing_object_id"), object_ids)
        merged["facing_npc_id"] = _resolve_target(merged.get("facing_npc_id"), npc_ids)
        merged["target_location_id"] = _resolve_target(merged.get("target_location_id"), location_ids)
        merged["target_npc_id"] = _resolve_target(merged.get("target_npc_id"), npc_ids)
        merged["target_object_id"] = _resolve_target(merged.get("target_object_id"), object_ids)
        merged["moving"] = bool(merged.get("moving", False))
        merged["in_conversation"] = bool(merged.get("in_conversation", False))
        merged["pose_progress"] = float(
            min(1.0, max(0.0, float(merged.get("pose_progress", 0.0))))
        )
        entry = {key: merged.get(key) for key in _PAYLOAD_FIELDS}
        thought = merged.get("thought")
        if thought is not None:
            entry["thought"] = thought
        npcs.append(entry)

    payload = {
        "version": int(data.get("version", VERSION)),
        "tick": int(data.get("tick", 0)),
        "day": int(data.get("day", 0)),
        "hour": int(data.get("hour", 0)),
        "minute": int(data.get("minute", 0)),
        "npcs": npcs,
    }
    payload["objects"] = list(data.get("objects", []))
    payload["locations"] = list(data.get("locations", []))
    return payload