from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Perception:
    location: Any
    nearby_npcs: list = field(default_factory=list)
    objects: list = field(default_factory=list)
    visible_npcs: list = field(default_factory=list)
    available_resources: list = field(default_factory=list)
    available_activities: list = field(default_factory=list)
    connected_locations: list = field(default_factory=list)
    world_events: list = field(default_factory=list)
    time: Any = None

    def describe(self) -> str:
        nearby = ", ".join(npc.name for npc in self.nearby_npcs) or "nobody"
        resources = ", ".join(resource.name for resource in self.available_resources) or "none"
        return (
            f"at {self.location.name}: nearby [{nearby}], "
            f"resources [{resources}], activities {self.available_activities}"
        )


class PerceptionSystem:
    def perceive(self, npc, world) -> Perception:
        location = world.get_location(npc.location_id)
        nearby = [npc2 for npc2 in world.npcs_at(npc.location_id) if npc2.id != npc.id]
        objects = list(world.objects_at(npc.location_id)) if hasattr(world, "objects_at") else []
        resources = [world.resources[r] for r in location.resources if r in world.resources]
        connected = [world.get_location(c) for c in location.connected if world.get_location(c) is not None]
        events = [event for event in world.active_events() if event.location_id in (None, location.id)]
        return Perception(
            location=location,
            nearby_npcs=nearby,
            objects=objects,
            visible_npcs=list(nearby),
            available_resources=resources,
            available_activities=list(location.activities),
            connected_locations=connected,
            world_events=events,
            time=world.clock,
        )