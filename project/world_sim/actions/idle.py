from __future__ import annotations

import zlib

from .action import Action, log

_IDLE_TOKENS = ["look_around", "stretch", "sit", "inspect_nearby"]


def _stamp(world) -> str:
    return world.clock.stamp()


def _crc32(text: str) -> int:
    return zlib.crc32(text.encode("utf-8"))


class IdleAction(Action):
    action_type = "idle"

    def __init__(self, rng, config: dict, decision):
        super().__init__(rng, config, decision)
        self.ticks = self._int("idle_ticks", 4)
        self.idle_state: str = "idle"

    def can_execute(self, npc, world) -> bool:
        return getattr(world, "behavior_idle_enabled", True)

    def start(self, npc, world) -> None:
        self.idle_state = self._select_token(npc, world)
        npc.idle_state = self.idle_state
        log.debug(f"[{_stamp(world)}] {npc.name} is idling ({self.idle_state}).")

    def _select_token(self, npc, world) -> str:
        weights = {
            "look_around": 0.4 + 0.6 * npc.personality.sociability,
            "stretch": 0.3 + 0.3 * (1.0 - npc.personality.work_ethic),
            "sit": 0.3 + 0.7 * (1.0 - npc.personality.ambition),
            "inspect_nearby": 0.2 + 0.8 * npc.personality.risk_tolerance,
        }
        total = sum(weights.values())
        draw = _crc32(f"{npc.id}|idle|{world.clock.day}")
        threshold = (draw % int(total * 1000 + 1)) / 1000.0
        cumulative = 0.0
        for token in _IDLE_TOKENS:
            cumulative += weights[token] / total
            if threshold < cumulative:
                return token
        return _IDLE_TOKENS[0]

    def apply(self, npc, world) -> None:
        pass

    def is_complete(self, npc, world) -> bool:
        return self.ticks_elapsed >= self.ticks

    def finish(self, npc, world) -> None:
        npc.idle_state = None

    def cancel(self, npc, world) -> None:
        npc.idle_state = None