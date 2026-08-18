from __future__ import annotations

from collections import deque

from .action import Action, log


def _stamp(world) -> str:
    return world.clock.stamp()


class MoveAction(Action):
    action_type = "move"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.target = decision.target_location_id if decision is not None else None
        self.path: list[str] = []
        self.edge_ticks = self._int("move_edge_ticks", 1)
        self._edge_progress = 0

    def can_execute(self, npc, world) -> bool:
        return self.target is not None and self.target in world.locations

    def start(self, npc, world) -> None:
        self.path = self._find_path(world, npc.location_id, self.target)
        if self.target and self.target != npc.location_id:
            target_name = world.get_location(self.target).name
            log.debug(f"[{_stamp(world)}] {npc.name} decided to go to {target_name}.")

    def apply(self, npc, world) -> None:
        self._edge_progress += 1
        if self._edge_progress < self.edge_ticks:
            return
        self._edge_progress = 0
        if self.path:
            next_id = self.path.pop(0)
            from_loc = npc.location_id
            npc.move_to(next_id)
            world.record_settlement_crossing(npc, from_loc, next_id)
            log.info(f"[{_stamp(world)}] {npc.name} went to {world.get_location(next_id).name}.")

    def is_complete(self, npc, world) -> bool:
        return npc.location_id == self.target or not self.path

    def _find_path(self, world, start: str, target: str) -> list[str]:
        if start == target:
            return []
        queue = deque([(start, [])])
        visited = {start}
        while queue:
            current, trail = queue.popleft()
            for neighbor in world.get_location(current).connected:
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                new_trail = trail + [neighbor]
                if neighbor == target:
                    return new_trail
                queue.append((neighbor, new_trail))
        return []