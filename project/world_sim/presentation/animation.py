"""Pure presentation/animation projection layer.

Converts the current NPC simulation state into an AnimationState that a future
renderer can consume. This module is strictly presentational:

- `animate` is a pure function: it never mutates NPC, World, actions, objects,
  conversations, needs, memory, or any other simulation state.
- It never consumes simulation RNG.
- It never imports or depends on any rendering/graphics framework.
- Calling `animate` twice with the same state produces identical results.
- All returned fields are derived from existing simulation state only.

The AI/decision/action systems must never import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..npc.behavior import BehaviorState, behavior_state
from ..npc.needs import NeedLevel
from ..npc.relationships import relationship_tier

_EMOTION_DEAD = "stressed"

_IDLE_POSE = {
    "sit": "sit",
    "stretch": "stretch",
    "inspect_nearby": "inspect",
    "look_around": "idle",
}

_INTERACT_POSE = {
    "sit": "sit",
    "use": "interact",
    "inspect": "inspect",
    "tend": "work",
}


@dataclass
class AnimationState:
    npc_id: str
    pose: str
    moving: bool
    behavior_state: str
    facing_location_id: Optional[str] = None
    facing_object_id: Optional[str] = None
    facing_npc_id: Optional[str] = None
    target_location_id: Optional[str] = None
    target_npc_id: Optional[str] = None
    target_object_id: Optional[str] = None
    emotion: str = "content"
    in_conversation: bool = False
    intent: Optional[str] = None
    pose_progress: float = 0.0
    tone: str = "neutral"


def animate(npc, world) -> AnimationState:
    """Project the current simulation state into an AnimationState."""
    state = behavior_state(npc, world)
    pose = _pose(npc, world)
    moving = state is BehaviorState.MOVING
    facing = _facing(npc, world)
    targets = _targets(npc, world)
    return AnimationState(
        npc_id=npc.id,
        pose=pose,
        moving=moving,
        behavior_state=state.value,
        facing_location_id=facing[0],
        facing_object_id=facing[1],
        facing_npc_id=facing[2],
        target_location_id=targets[0],
        target_npc_id=targets[1],
        target_object_id=targets[2],
        emotion=_emotion(npc, world),
        in_conversation=npc.conversation_id is not None,
        intent=npc.intent.kind if npc.intent is not None else None,
        pose_progress=_pose_progress(npc),
        tone=_conversation_tone(npc, world),
    )


def _pose(npc, world) -> str:
    """Derive the presentation pose from existing simulation state.

    DEAD always wins, then conversations, then the current action, then idle.
    """
    if not npc.alive:
        return "dead"

    if npc.conversation_id is not None:
        return _conversation_pose(npc, world)

    action = npc.current_action
    action_type = action.action_type if action is not None else None

    if action_type == "move":
        return "walk"
    if action_type == "work":
        return "work"
    if action_type == "eat":
        return "eat"
    if action_type == "buy_food":
        return "buy"
    if action_type == "sleep":
        return "sleep"
    if action_type == "interact":
        return _interact_pose(action)
    if action_type == "socialize":
        return "talk"

    idle_state = npc.idle_state
    if idle_state is not None:
        return _IDLE_POSE.get(idle_state, "idle")
    return "idle"


def _conversation_pose(npc, world) -> str:
    conv = world.conversation_for(npc.id)
    if conv is None:
        return "talk"
    if conv.stage == "greeting":
        if getattr(world, "behavior_social_life_enabled", False):
            tiers = getattr(world, "_relationship_tiers", None)
            partner_id = conv.responder_id if npc.id == conv.initiator_id else conv.initiator_id
            tier = relationship_tier(npc.relationships.get(partner_id, 0), tiers)
            if tier in ("rival", "disliked"):
                return "talk"
        return "wave"
    if conv.stage == "farewell":
        return "wave"
    speaker_is_initiator = (world.clock.tick - conv.started_tick - 1) % 2 == 0
    is_initiator = npc.id == conv.initiator_id
    if speaker_is_initiator == is_initiator:
        return "talk"
    return "listen"


def _conversation_tone(npc, world) -> str:
    """Deterministic conversational tone derived from the relationship tier.

    Presentation-only: never mutates state and never consumes simulation RNG.
    """
    if not npc.alive or npc.conversation_id is None:
        return "neutral"
    if not getattr(world, "behavior_social_life_enabled", False):
        return "neutral"
    conv = world.conversation_for(npc.id)
    if conv is None:
        return "neutral"
    partner_id = conv.responder_id if npc.id == conv.initiator_id else conv.initiator_id
    tier = relationship_tier(
        npc.relationships.get(partner_id, 0),
        getattr(world, "_relationship_tiers", None),
    )
    if tier == "close_friend":
        return "warm"
    if tier == "friend":
        return "warm"
    if tier in ("rival", "disliked"):
        return "tense"
    return "neutral"


def _interact_pose(action) -> str:
    interaction = getattr(action, "interaction", None)
    if interaction is None:
        intent_context = getattr(getattr(action, "decision", None), "candidates", None)
        if isinstance(intent_context, dict):
            interaction = intent_context.get("interaction")
    return _INTERACT_POSE.get(interaction, "interact")


def _facing(npc, world):
    """Populate exactly one facing target where simulation state represents it."""
    if npc.conversation_id is not None:
        conv = world.conversation_for(npc.id)
        if conv is not None:
            partner = conv.responder_id if npc.id == conv.initiator_id else conv.initiator_id
            return (None, None, partner)

    action = npc.current_action
    if action is not None and action.action_type == "interact":
        obj_id = getattr(action, "target_object_id", None)
        if obj_id:
            return (None, obj_id, None)

    if action is not None and action.action_type == "move":
        destination = getattr(action, "target", None)
        if destination:
            return (destination, None, None)

    return (None, None, None)


def _targets(npc, world):
    """Derive target fields from action, conversation, then intent."""
    location_id = None
    object_id = None
    npc_id = None

    if npc.conversation_id is not None:
        conv = world.conversation_for(npc.id)
        if conv is not None:
            npc_id = conv.responder_id if npc.id == conv.initiator_id else conv.initiator_id

    action = npc.current_action
    if action is not None:
        if action.action_type == "move":
            location_id = getattr(action, "target", None)
        elif action.action_type == "interact":
            object_id = getattr(action, "target_object_id", None)

    intent = npc.intent
    if location_id is None and intent is not None and intent.target_location_id:
        location_id = intent.target_location_id
    if object_id is None and intent is not None and intent.target_object_id:
        object_id = intent.target_object_id
    if npc_id is None and intent is not None and intent.target_npc_id:
        npc_id = intent.target_npc_id

    return (location_id, npc_id, object_id)


def _emotion(npc, world) -> str:
    """Deterministic presentation-only emotion derived from needs/state.

    Uses the same threshold lookup as the decision system so the mapping stays
    consistent with the project's needs API.
    """
    if not npc.alive:
        return _EMOTION_DEAD
    thresholds = world.config.get("needs", {}).get("thresholds", {})
    hunger_threshold = float(thresholds.get("hunger", NeedLevel.HUNGER_CRITICAL))
    energy_threshold = float(thresholds.get("energy", NeedLevel.ENERGY_CRITICAL))
    social_threshold = float(thresholds.get("social", NeedLevel.SOCIAL_LOW))
    needs = npc.needs
    if needs.hunger >= hunger_threshold:
        return "hungry"
    if needs.energy <= energy_threshold:
        return "tired"
    if needs.social <= social_threshold:
        return "lonely"
    return "content"


def _pose_progress(npc) -> float:
    """Deterministic progress in [0.0, 1.0] from action lifecycle timing."""
    action = npc.current_action
    if action is None:
        return 0.0
    duration = getattr(action, "shift_ticks", None) or getattr(action, "ticks", None)
    if not duration:
        return 1.0
    return min(1.0, max(0.0, action.ticks_elapsed / float(duration)))