from __future__ import annotations

from enum import Enum


class BehaviorState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    ACTING = "acting"
    SOCIALIZING = "socializing"
    CONVERSING = "conversing"
    INTERACTING = "interacting"
    SLEEPING = "sleeping"
    DEAD = "dead"


def behavior_state(npc, world) -> BehaviorState:
    if not npc.alive:
        return BehaviorState.DEAD

    action_type = npc.current_action.action_type if npc.current_action is not None else None

    if npc.conversation_id is not None:
        return BehaviorState.CONVERSING

    if action_type == "move":
        return BehaviorState.MOVING

    if action_type == "interact":
        return BehaviorState.INTERACTING

    if action_type == "sleep":
        return BehaviorState.SLEEPING

    if action_type == "socialize" or (
        npc.intent is not None and npc.intent.kind == "socializing"
    ):
        return BehaviorState.SOCIALIZING

    if action_type in ("work", "eat"):
        return BehaviorState.ACTING

    return BehaviorState.IDLE