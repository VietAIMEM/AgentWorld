"""Additive, deterministic player-interaction layer (presentation-side).

The Python simulation stays authoritative. This module maintains a
``PlayerSession`` (player position, current target, and a player-facing
conversation) and builds a versioned interaction payload for the Unity client.

Properties:

- Commands are validated against authoritative simulation state here, before
  any client-side UI is allowed to act.
- ``handle_command`` mutates only the session (never the simulation) and
  consumes zero simulation RNG.
- Responses are deterministic functions of (npc, world, option) using the
  stable CRC32 mixer — never LLM, never random.
- The player conversation is a separate additive structure; the existing
  NPC ``Conversation`` engine is never touched.

Simulation/AI systems never import this module.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from ..npc.behavior import behavior_state
from ..npc.conversation import crc32
from ..npc.relationships import player_tier, relationship_tier
from .animation import animate

PLAYER_INTERACTION_VERSION = 1

COMMAND_TYPES = (
    "player_update",
    "player_talk",
    "player_inspect",
    "player_observe",
    "player_interact",
)

CONVERSATION_OPTIONS = (
    ("work", "Ask about work"),
    ("place", "Ask about this place"),
    ("farewell", "Goodbye"),
)

_RELATIONSHIP_MIN = -100
_RELATIONSHIP_MAX = 100

PLAYER_RELATIONSHIP_DELTAS = {
    "greeting": 1,
    "work": 2,
    "place": 1,
    "farewell": 0,
}

_GREETINGS = (
    "Hello there.",
    "Good day, traveler.",
    "Ah, a visitor. Welcome.",
    "Hello. What brings you here?",
)

_WORKING = (
    "I'm finishing up my work right now.",
    "Busy as ever — work waits for no one.",
    "Just tending to my duties.",
    "A moment, I'm in the middle of my work.",
)

_EATING = (
    "Please excuse me, I'm just eating.",
    "A quick meal between tasks.",
    "I'll talk once I've finished eating.",
)

_SHOPPING = (
    "Just picking up a few supplies.",
    "Shopping for the essentials.",
    "Keeping the pantry stocked.",
)

_RESTING = (
    "Just resting a while.",
    "Taking a well-earned break.",
    "Catching my breath.",
)

_SOCIALIZING = (
    "Enjoying some company today.",
    "Just chatting with friends.",
    "A pleasant gathering, isn't it?",
)

_BUSY = (
    "I'm in the middle of something right now.",
    "Can we talk a little later?",
    "Sorry, I'm occupied at the moment.",
)

_FAREWELL = (
    "Take care, traveler.",
    "Goodbye for now.",
    "Until we meet again.",
    "Safe travels.",
)

_LOCATION_TEXTS = {
    "market": ("The market is always lively.", "Good trade here today."),
    "commercial": ("Plenty of commerce in these parts.", "Busy trading day."),
    "social": ("This is a fine place to gather.", "Good company here."),
    "farm": ("The fields keep us fed.", "Hard work, good harvests."),
    "residence": ("A quiet part of town.", "Home is home."),
    "workplace": ("The daily grind.", "Work keeps the village going."),
    "natural": ("The outdoors are peaceful.", "Fresh air and open ground."),
    "unknown": ("This place has its own rhythm.", "Not much to say about it."),
}

_CATEGORY_TEXTS = {
    "greeting": _GREETINGS,
    "working": _WORKING,
    "eating": _EATING,
    "shopping": _SHOPPING,
    "resting": _RESTING,
    "socializing": _SOCIALIZING,
    "busy": _BUSY,
    "farewell": _FAREWELL,
}


class PlayerCommandError(Exception):
    """Raised when a player command is invalid per authoritative state."""


def _pick(lines, key):
    return lines[crc32(key) % len(lines)]


def command_category(npc, world) -> str:
    """Deterministic response category from the NPC's current state."""
    if npc.conversation_id is not None:
        return "busy"
    action = npc.current_action
    action_type = action.action_type if action is not None else None
    if action_type == "work":
        return "working"
    if action_type == "eat":
        return "eating"
    if action_type == "buy_food":
        return "shopping"
    if action_type == "socialize":
        return "socializing"
    if action_type == "interact":
        return "busy"
    if action_type in ("sleep", "rest"):
        return "resting"
    return "greeting"


def response_for(npc, world, option: Optional[str] = None):
    """Deterministic (npc, world, option) -> (category, text)."""
    if not npc.alive:
        return "farewell", _pick(_FAREWELL, npc.id + "farewell")
    if option == "farewell":
        return "farewell", _pick(_FAREWELL, npc.id + "farewell")
    if option == "place":
        loc = world.locations.get(npc.location_id)
        key = loc.type if loc is not None else "unknown"
        texts = _LOCATION_TEXTS.get(key, _LOCATION_TEXTS["unknown"])
        return "location", _pick(texts, npc.id + "place" + npc.location_id)
    if option == "work":
        return "working", _pick(_WORKING, npc.id + "work")
    category = command_category(npc, world)
    text = _pick(_CATEGORY_TEXTS[category], npc.id + category + str(world.clock.day))
    return category, text


def observe_text(npc, world) -> str:
    state = animate(npc, world)
    loc = world.locations.get(npc.location_id)
    place = loc.name if loc is not None else "the area"
    return f"{npc.name} is {state.pose} at {place}."


def _settlement_for(world, loc) -> Optional[str]:
    region = getattr(loc, "region_id", None)
    if region is not None and str(region).startswith("settlement_"):
        return region
    for sid in sorted(world.settlement_economies):
        if loc.id.startswith(sid + "_"):
            return sid
    return None


def npc_public_info(npc, world) -> dict:
    """Public NPC inspection data (authoritative but presentation-shaped)."""
    state = animate(npc, world)
    goal = npc.current_goal
    rel = dict(npc.relationships)
    top = sorted(rel.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    tiers = getattr(world, "_relationship_tiers", None)
    return {
        "npc_id": npc.id,
        "name": npc.name,
        "age": npc.age,
        "job": npc.job.id,
        "settlement_id": npc.settlement_id,
        "location_id": npc.location_id,
        "alive": npc.alive,
        "behavior_state": state.behavior_state,
        "pose": state.pose,
        "emotion": state.emotion,
        "intent": state.intent,
        "goal": goal.type.value if goal is not None else None,
        "action": npc.current_action.action_type if npc.current_action is not None else None,
        "money": round(npc.money, 2),
        "needs": {
            "hunger": round(npc.needs.hunger, 1),
            "energy": round(npc.needs.energy, 1),
            "social": round(npc.needs.social, 1),
        },
        "relationships": [
            {
                "npc_id": other,
                "value": value,
                "tier": relationship_tier(value, tiers),
            }
            for other, value in top
        ],
    }


def location_info(world, loc_id: str) -> Optional[dict]:
    loc = world.locations.get(loc_id)
    if loc is None:
        return None
    alive = sorted(n.id for n in world.npcs if n.alive and n.location_id == loc_id)
    objects = [
        {
            "object_id": o.id,
            "name": o.name,
            "object_type": o.object_type,
            "state": o.state,
        }
        for o in world.objects
        if o.location_id == loc_id
    ]
    return {
        "location_id": loc.id,
        "name": loc.name,
        "type": loc.type,
        "settlement_id": _settlement_for(world, loc),
        "npc_count": len(alive),
        "npc_ids": alive,
        "objects": objects,
        "activities": list(loc.activities),
    }


def object_info(obj) -> dict:
    return {
        "object_id": obj.id,
        "name": obj.name,
        "object_type": obj.object_type,
        "state": obj.state,
        "location_id": obj.location_id,
        "interactions": list(obj.interactions),
    }


@dataclass
class PlayerConversation:
    npc_id: str
    npc_name: str
    started_tick: int
    last_category: str = ""
    last_text: str = ""
    llm_emotion: Optional[str] = None
    llm_topic: Optional[str] = None
    llm: bool = False


class PlayerSession:
    """Player-side state for the interactive client (never simulated)."""

    def __init__(self, llm_bridge=None):
        self._lock = threading.Lock()
        self.position: Optional[tuple] = None
        self.nearest_location_id: Optional[str] = None
        self.target_id: Optional[str] = None
        self.conversation: Optional[PlayerConversation] = None
        self.relationships: dict = {}
        self._llm_bridge = llm_bridge

    def _nearest_location(self, world) -> Optional[str]:
        x, z = self.position
        if x is None or z is None:
            return None
        best = None
        best_dist = float("inf")
        for lid, loc in world.locations.items():
            if loc.position is None:
                continue
            dist = (loc.position[0] - x) ** 2 + (loc.position[1] - z) ** 2
            if dist < best_dist:
                best_dist = dist
                best = lid
        return best

    def expire_conversation(self, world) -> None:
        if self.conversation is None:
            return
        npc = world.get_npc(self.conversation.npc_id)
        if npc is None or not npc.alive:
            self.conversation = None

    def handle_command(self, sim, command: dict) -> dict:
        if not isinstance(command, dict):
            raise PlayerCommandError("command must be a JSON object")
        ctype = command.get("type")
        if ctype not in COMMAND_TYPES:
            raise PlayerCommandError(f"unknown command type {ctype!r}")
        world = sim.world
        with self._lock:
            self.expire_conversation(world)
            if ctype == "player_update":
                x = command.get("x")
                z = command.get("z")
                if x is None or z is None:
                    raise PlayerCommandError("player_update requires x and z")
                self.position = (float(x), float(z))
                self.nearest_location_id = self._nearest_location(world)
                return {
                    "ok": True,
                    "position": {"x": float(x), "z": float(z)},
                    "location_id": self.nearest_location_id,
                }
            if ctype == "player_talk":
                target_id = command.get("target_id")
                npc = world.get_npc(target_id) if target_id else None
                if npc is None:
                    raise PlayerCommandError(f"npc {target_id!r} not found")
                if not npc.alive:
                    raise PlayerCommandError(f"npc {target_id!r} is dead")
                self.target_id = target_id
                return self._talk(npc, world, command.get("option"))
            if ctype == "player_inspect":
                target_id = command.get("target_id")
                npc = world.get_npc(target_id) if target_id else None
                if npc is not None:
                    self.target_id = target_id
                    return {"ok": True, "target": npc_public_info(npc, world)}
                obj = next((o for o in world.objects if o.id == target_id), None)
                if obj is not None:
                    self.target_id = target_id
                    return {"ok": True, "object": object_info(obj)}
                raise PlayerCommandError(f"target {target_id!r} not found")
            if ctype == "player_observe":
                target_id = command.get("target_id")
                npc = world.get_npc(target_id) if target_id else None
                if npc is None:
                    raise PlayerCommandError(f"npc {target_id!r} not found")
                if not npc.alive:
                    raise PlayerCommandError(f"npc {target_id!r} is dead")
                self.target_id = target_id
                state = animate(npc, world)
                return {
                    "ok": True,
                    "observe": {
                        "npc_id": npc.id,
                        "name": npc.name,
                        "behavior_state": state.behavior_state,
                        "pose": state.pose,
                        "emotion": state.emotion,
                        "intent": state.intent,
                        "action": npc.current_action.action_type if npc.current_action else None,
                        "description": observe_text(npc, world),
                    },
                }
            if ctype == "player_interact":
                target_id = command.get("target_id")
                obj = next((o for o in world.objects if o.id == target_id), None)
                if obj is None:
                    raise PlayerCommandError(f"object {target_id!r} not found")
                self.target_id = target_id
                return {"ok": True, "object": object_info(obj)}
            raise PlayerCommandError(f"unhandled command type {ctype!r}")

    def _talk(self, npc, world, option) -> dict:
        option = option if option in ("work", "place", "farewell") else None
        if self.conversation is not None and self.conversation.npc_id != npc.id:
            self.conversation = None
        if option == "farewell":
            if self._llm_bridge is not None and self.conversation is not None:
                self._llm_bridge.on_farewell(npc, world, self.conversation)
            category, text = response_for(npc, world, "farewell")
            reply = {"category": category, "text": text}
            self.conversation = None
            return {
                "ok": True,
                "conversation": {"active": False, "npc_id": npc.id, "npc_name": npc.name, "reply": reply, "options": []},
            }
        delta = PLAYER_RELATIONSHIP_DELTAS.get(option if option is not None else "greeting", 0)
        if delta:
            current = self.relationships.get(npc.id, 0)
            self.relationships[npc.id] = max(
                _RELATIONSHIP_MIN, min(_RELATIONSHIP_MAX, current + delta)
            )
        category, text = response_for(npc, world, option)
        if self.conversation is None or self.conversation.npc_id != npc.id:
            self.conversation = PlayerConversation(
                npc_id=npc.id, npc_name=npc.name, started_tick=world.clock.tick
            )
        self.conversation.last_category = category
        self.conversation.last_text = text
        emotion = None
        topic = None
        llm = False
        if self._llm_bridge is not None:
            override = self._llm_bridge.maybe_reply(npc, world, option, self.conversation)
            if override is not None:
                text = override["dialogue"]
                category = override.get("topic") or category
                emotion = override.get("emotion")
                topic = override.get("topic")
                llm = True
        return {
            "ok": True,
            "conversation": {
                "active": True,
                "npc_id": npc.id,
                "npc_name": npc.name,
                "reply": {"category": category, "text": text},
                "options": [{"key": key, "label": label} for key, label in CONVERSATION_OPTIONS],
                "emotion": emotion,
                "topic": topic,
                "llm": llm,
            },
        }

    def build_interaction_payload(self, sim) -> dict:
        world = sim.world
        with self._lock:
            if self._llm_bridge is not None:
                self._llm_bridge.poll()
            self.expire_conversation(world)
            if self.position is not None and self.nearest_location_id is None:
                self.nearest_location_id = self._nearest_location(world)
            payload = {
                "version": PLAYER_INTERACTION_VERSION,
                "tick": world.clock.tick,
                "day": world.clock.day,
                "hour": world.clock.hour,
                "minute": world.clock.minute,
            }
            if self.position is not None:
                payload["player"] = {
                    "x": round(self.position[0], 2),
                    "z": round(self.position[1], 2),
                    "location_id": self.nearest_location_id,
                }
            if self.nearest_location_id is not None:
                payload["location"] = location_info(world, self.nearest_location_id)
            nearby_npcs = []
            nearby_objects = []
            if self.nearest_location_id is not None:
                nearby_npcs = sorted(
                    n.id for n in world.npcs if n.alive and n.location_id == self.nearest_location_id
                )
                nearby_objects = sorted(
                    o.id for o in world.objects if o.location_id == self.nearest_location_id
                )
            payload["nearby"] = {"npc_ids": nearby_npcs, "object_ids": nearby_objects}

            if self.target_id is not None:
                npc = world.get_npc(self.target_id)
                if npc is not None and npc.alive:
                    payload["target"] = npc_public_info(npc, world)
                    value = self.relationships.get(self.target_id, 0)
                    payload["target"]["player_relationship"] = {
                        "value": value,
                        "tier": player_tier(value),
                    }
                else:
                    obj = next((o for o in world.objects if o.id == self.target_id), None)
                    if obj is not None:
                        payload["object"] = object_info(obj)

            if self.conversation is not None:
                payload["conversation"] = {
                    "active": True,
                    "npc_id": self.conversation.npc_id,
                    "npc_name": self.conversation.npc_name,
                    "text": self.conversation.last_text,
                    "category": self.conversation.last_category,
                    "options": [{"key": key, "label": label} for key, label in CONVERSATION_OPTIONS],
                    "emotion": self.conversation.llm_emotion,
                    "topic": self.conversation.llm_topic,
                    "llm": self.conversation.llm,
                }
            else:
                payload["conversation"] = {"active": False, "options": []}
            return payload