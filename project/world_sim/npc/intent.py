from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Intent:
    kind: str
    started_tick: int
    target_location_id: Optional[str] = None
    target_npc_id: Optional[str] = None
    target_object_id: Optional[str] = None
    context: str = ""


def set_intent(
    npc,
    world,
    kind: str,
    target_location_id: Optional[str] = None,
    target_npc_id: Optional[str] = None,
    target_object_id: Optional[str] = None,
    context: str = "",
) -> None:
    if not getattr(world, "behavior_enabled", False):
        return
    npc.intent = Intent(
        kind=kind,
        started_tick=world.clock.tick,
        target_location_id=target_location_id,
        target_npc_id=target_npc_id,
        target_object_id=target_object_id,
        context=context,
    )


def clear_intent(npc, world) -> None:
    if not getattr(world, "behavior_enabled", False):
        return
    npc.intent = None