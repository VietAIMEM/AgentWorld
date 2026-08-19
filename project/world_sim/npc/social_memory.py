from __future__ import annotations

from collections import defaultdict

_SOCIAL_MEMORY_HOUR = 12


class SocialMemorySystem:
    """Writes structured social memories for co-located NPCs.

    Additive and strictly deterministic:

    - Only active when ``behavior.social_life.enabled`` is true (disabled mode
      is byte-identical to the baseline simulation).
    - Runs at a fixed clock hour so each (pair, day) produces at most one
      memory entry; memory caps are enforced by the existing prune logic.
    - Never consumes simulation RNG and never mutates decisions/actions.
    """

    def tick(self, world) -> None:
        if not getattr(world, "behavior_social_life_enabled", False):
            return
        if world.clock.hour != _SOCIAL_MEMORY_HOUR or world.clock.minute != 0:
            return
        by_location: dict[str, list] = defaultdict(list)
        for npc in world.alive_npcs():
            by_location[npc.location_id].append(npc)
        stamp = world.clock.stamp()
        for location_id in sorted(by_location):
            group = sorted(by_location[location_id], key=lambda npc: npc.id)
            for index in range(len(group)):
                for other_index in range(index + 1, len(group)):
                    first, second = group[index], group[other_index]
                    first_action = first.current_action.action_type if first.current_action else None
                    second_action = second.current_action.action_type if second.current_action else None
                    location_name = first.location_name(world)
                    if first_action == "work" and second_action == "work":
                        first.add_memory(
                            stamp,
                            "worked_with",
                            f"{first.name} worked alongside {second.name} at {location_name}.",
                            2.0,
                            second.id,
                        )
                        second.add_memory(
                            stamp,
                            "worked_with",
                            f"{second.name} worked alongside {first.name} at {location_name}.",
                            2.0,
                            first.id,
                        )
                    elif first_action == "eat" and second_action == "eat":
                        first.add_memory(
                            stamp,
                            "ate_with",
                            f"{first.name} ate with {second.name} at {location_name}.",
                            2.0,
                            second.id,
                        )
                        second.add_memory(
                            stamp,
                            "ate_with",
                            f"{second.name} ate with {first.name} at {location_name}.",
                            2.0,
                            first.id,
                        )