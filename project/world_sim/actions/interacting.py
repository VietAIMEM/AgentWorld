from __future__ import annotations

from ..npc.intent import clear_intent, set_intent
from ..npc.needs import clamp
from .action import Action, log

INTERACTION_PROPERTIES: dict[str, dict] = {
    "sit": {"energy": 1.5, "social": 1.0},
    "use": {"energy": 2.0},
    "inspect": {"social": 0.5},
    "tend": {"energy": -2.0},
}

INTERACTION_POSE: dict[str, str] = {
    "sit": "sitting",
    "use": "using",
    "inspect": "inspecting",
    "tend": "tending",
}

_MEMORY_INTERACTIONS = {"inspect", "tend"}


def _stamp(world) -> str:
    return world.clock.stamp()


class InteractAction(Action):
    action_type = "interact"

    def __init__(self, rng, config: dict, decision, target_object_id: str | None = None):
        super().__init__(rng, config, decision)
        self.ticks = self._int("interact_ticks", 3)
        self.target_object_id = target_object_id
        if self.target_object_id is None and decision is not None:
            self.target_object_id = decision.candidates.get("target_object_id")
        self.interaction = None
        if decision is not None:
            self.interaction = decision.candidates.get("interaction")
        self._applied = False

    def _target_object(self, world):
        if not self.target_object_id:
            return None
        for obj in world.objects:
            if obj.id == self.target_object_id:
                return obj
        return None

    def can_execute(self, npc, world) -> bool:
        if not getattr(world, "behavior_interactions_enabled", True):
            return False
        obj = self._target_object(world)
        if obj is None or npc.location_id != obj.location_id or not obj.is_available():
            return False
        if self.interaction and self.interaction not in obj.interactions:
            return False
        return True

    def start(self, npc, world) -> None:
        obj = self._target_object(world)
        if obj is None:
            return
        obj.state = "in_use"
        obj.in_use_by = npc.id
        interaction = self.interaction or (obj.interactions[0] if obj.interactions else "use")
        set_intent(
            npc,
            world,
            "interacting",
            target_location_id=npc.location_id,
            target_object_id=obj.id,
            context=INTERACTION_POSE.get(interaction, interaction),
        )
        log.debug(f"[{_stamp(world)}] {npc.name} started interacting with {obj.name}.")

    def apply(self, npc, world) -> None:
        if self._applied:
            return
        self._applied = True
        obj = self._target_object(world)
        interaction = self.interaction or (obj.interactions[0] if obj is not None and obj.interactions else "use")
        props = INTERACTION_PROPERTIES.get(interaction, {})
        if "energy" in props:
            npc.needs.energy = clamp(npc.needs.energy + props["energy"], 0.0, 100.0)
        if "social" in props:
            npc.needs.social = clamp(npc.needs.social + props["social"], 0.0, 100.0)
        if interaction in _MEMORY_INTERACTIONS and obj is not None:
            location_name = world.get_location(obj.location_id).name
            npc.add_memory(
                _stamp(world),
                "interaction",
                f"{npc.name} {INTERACTION_POSE.get(interaction, interaction)} {obj.name} at {location_name}.",
                3.0,
            )

    def is_complete(self, npc, world) -> bool:
        return self.ticks_elapsed >= self.ticks

    def finish(self, npc, world) -> None:
        npc.last_interact_tick = world.clock.tick
        clear_intent(npc, world)
        self._release(world)

    def cancel(self, npc, world) -> None:
        clear_intent(npc, world)
        self._release(world)

    def _release(self, world) -> None:
        obj = self._target_object(world)
        if obj is not None and obj.in_use_by is not None:
            obj.state = "available"
            obj.in_use_by = None