from __future__ import annotations

import base64
import json
from dataclasses import fields as dc_fields
from enum import Enum
from pathlib import Path
from typing import Optional

from ..actions.eating import BuyFoodAction, EatAction
from ..actions.exploring import ExploreAction
from ..actions.movement import MoveAction
from ..actions.resting import RestAction
from ..actions.sleeping import SleepAction
from ..actions.social import SocializeAction
from ..actions.working import WorkAction
from ..decision.decision_system import Decision
from ..npc.goals import Goal, GoalStatus, GoalType
from ..npc.memory import Memory, MemoryEntry
from ..npc.needs import Needs
from ..npc.npc import NPC
from ..npc.personality import Personality
from .clock import Clock
from .events import EventState, WorldEvent
from .simulation import Simulation
from .world import WorldStats

SAVE_FORMAT = "world_sim_save_v1"

ACTION_CLASSES = {
    "move": MoveAction,
    "eat": EatAction,
    "buy_food": BuyFoodAction,
    "sleep": SleepAction,
    "work": WorkAction,
    "socialize": SocializeAction,
    "rest": RestAction,
    "explore": ExploreAction,
}

_EXCLUDED_ACTION_FIELDS = {"rng", "config", "decision", "priority", "ticks_elapsed", "_actions_cfg"}


def _to_jsonable(obj):
    if isinstance(obj, Enum):
        return {"__enum__": [type(obj).__name__, obj.value]}
    if isinstance(obj, tuple):
        return {"__tuple__": [_to_jsonable(item) for item in obj]}
    if isinstance(obj, bytes):
        return {"__bytes__": base64.b64encode(obj).decode("ascii")}
    if isinstance(obj, list):
        return [_to_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    raise TypeError(f"Unserializable object: {type(obj).__name__}")


def _from_jsonable(obj):
    if isinstance(obj, dict) and len(obj) == 1:
        if "__tuple__" in obj:
            return tuple(_from_jsonable(item) for item in obj["__tuple__"])
        if "__bytes__" in obj:
            return base64.b64decode(obj["__bytes__"])
    if isinstance(obj, list):
        return [_from_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _from_jsonable(value) for key, value in obj.items()}
    return obj


def _goal_to_dict(goal: Optional[Goal]) -> Optional[dict]:
    if goal is None:
        return None
    return {
        "type": goal.type.value,
        "priority": goal.priority,
        "target": goal.target,
        "status": goal.status.value,
        "started_tick": goal.started_tick,
    }


def _goal_from_dict(data: Optional[dict]) -> Optional[Goal]:
    if data is None:
        return None
    return Goal(
        type=GoalType(data["type"]),
        priority=float(data.get("priority", 0.0)),
        target=data.get("target"),
        status=GoalStatus(data.get("status", "proposed")),
        started_tick=data.get("started_tick"),
    )


def _decision_to_dict(decision: Optional[Decision]) -> Optional[dict]:
    if decision is None:
        return None
    return {
        "goal": _goal_to_dict(decision.goal),
        "action_type": decision.action_type,
        "priority": decision.priority,
        "target_location_id": decision.target_location_id,
        "target_npc_id": decision.target_npc_id,
        "reason": decision.reason,
        "candidates": dict(decision.candidates),
        "urgent": decision.urgent,
    }


def _decision_from_dict(data: Optional[dict]) -> Optional[Decision]:
    if data is None:
        return None
    return Decision(
        goal=_goal_from_dict(data["goal"]),
        action_type=data["action_type"],
        priority=float(data.get("priority", 0.0)),
        target_location_id=data.get("target_location_id"),
        target_npc_id=data.get("target_npc_id"),
        reason=data.get("reason", ""),
        candidates=dict(data.get("candidates", {})),
        urgent=bool(data.get("urgent", False)),
    )


def _action_to_dict(action) -> dict:
    fields = {
        key: _to_jsonable(value)
        for key, value in action.__dict__.items()
        if key not in _EXCLUDED_ACTION_FIELDS
    }
    return {
        "action_type": action.action_type,
        "ticks_elapsed": action.ticks_elapsed,
        "priority": action.priority,
        "decision": _decision_to_dict(action.decision),
        "fields": fields,
    }


def _action_from_dict(data: dict, rng, config):
    action_cls = ACTION_CLASSES[data["action_type"]]
    decision = _decision_from_dict(data.get("decision"))
    action = action_cls(rng, config, decision)
    for key, value in data.get("fields", {}).items():
        setattr(action, key, _from_jsonable(value))
    action.ticks_elapsed = int(data.get("ticks_elapsed", 0))
    action.priority = float(data.get("priority", 0.0))
    return action


def _npc_to_dict(npc: NPC) -> dict:
    return {
        "id": npc.id,
        "name": npc.name,
        "age": npc.age,
        "money": npc.money,
        "job_id": npc.job.id,
        "location_id": npc.location_id,
        "home_id": npc.home_id,
        "needs": {
            "hunger": npc.needs.hunger,
            "energy": npc.needs.energy,
            "social": npc.needs.social,
            "health": npc.needs.health,
        },
        "personality": {
            "sociability": npc.personality.sociability,
            "ambition": npc.personality.ambition,
            "risk_tolerance": npc.personality.risk_tolerance,
            "work_ethic": npc.personality.work_ethic,
            "generosity": npc.personality.generosity,
        },
        "relationships": dict(npc.relationships),
        "inventory": dict(npc.inventory),
        "alive": npc.alive,
        "last_wake_day": npc.last_wake_day,
        "last_socialize_day": npc.last_socialize_day,
        "hungry_logged": npc.hungry_logged,
        "memory": {
            "max_size": npc.memory.max_size,
            "entries": [
                {
                    "timestamp": entry.timestamp,
                    "event_type": entry.event_type,
                    "description": entry.description,
                    "importance": entry.importance,
                    "related_entity": entry.related_entity,
                }
                for entry in npc.memory.entries
            ],
        },
        "current_goal": _goal_to_dict(npc.current_goal),
        "current_action": _action_to_dict(npc.current_action) if npc.current_action is not None else None,
    }


def _npc_from_dict(data: dict, world) -> NPC:
    memory = Memory(max_size=int(data["memory"]["max_size"]))
    memory.entries = [
        MemoryEntry(
            timestamp=entry["timestamp"],
            event_type=entry["event_type"],
            description=entry["description"],
            importance=float(entry["importance"]),
            related_entity=entry["related_entity"],
        )
        for entry in data["memory"]["entries"]
    ]
    needs = Needs(
        hunger=float(data["needs"]["hunger"]),
        energy=float(data["needs"]["energy"]),
        social=float(data["needs"]["social"]),
        health=float(data["needs"]["health"]),
    )
    npc = NPC(
        id=data["id"],
        name=data["name"],
        age=int(data["age"]),
        money=float(data["money"]),
        job=world._jobs[data["job_id"]],
        location_id=data["location_id"],
        home_id=data["home_id"],
        needs=needs,
        personality=Personality(**data["personality"]),
        memory=memory,
    )
    npc.relationships = dict(data.get("relationships", {}))
    npc.inventory = dict(data.get("inventory", {}))
    npc.alive = bool(data.get("alive", True))
    npc.last_wake_day = int(data.get("last_wake_day", 0))
    npc.last_socialize_day = int(data.get("last_socialize_day", 0))
    npc.hungry_logged = bool(data.get("hungry_logged", False))
    npc.current_goal = _goal_from_dict(data.get("current_goal"))
    if data.get("current_action") is not None:
        npc.current_action = _action_from_dict(data["current_action"], world.rng, world.config)
        if npc.current_action.decision is not None:
            npc.current_goal = npc.current_action.decision.goal
    return npc


def _event_to_dict(event: WorldEvent) -> dict:
    return {
        "id": event.id,
        "type": event.type,
        "description": event.description,
        "start_tick": event.start_tick,
        "duration_ticks": event.duration_ticks,
        "location_id": event.location_id,
        "state": event.state.value,
        "started_tick": event.started_tick,
    }


def _event_from_dict(data: dict) -> WorldEvent:
    return WorldEvent(
        id=data["id"],
        type=data["type"],
        description=data["description"],
        start_tick=int(data["start_tick"]),
        duration_ticks=int(data["duration_ticks"]),
        location_id=data.get("location_id"),
        state=EventState(data.get("state", "scheduled")),
        started_tick=data.get("started_tick"),
    )


def _world_stats_from_dict(data: dict) -> WorldStats:
    merged = {}
    for field in dc_fields(WorldStats):
        merged[field.name] = data.get(field.name, field.default)
    return WorldStats(**merged)


def save_state(sim: Simulation, path) -> None:
    world = sim.world
    total_days = int(getattr(sim, "_total_days", sim.days))
    data = {
        "format": SAVE_FORMAT,
        "seed": sim.seed,
        "total_days": total_days,
        "rng_state": _to_jsonable(sim.rng.getstate()),
        "clock": {
            "tick_minutes": world.clock.tick_minutes,
            "day": world.clock.day,
            "hour": world.clock.hour,
            "minute": world.clock.minute,
            "tick": world.clock.tick,
        },
        "elapsed_days": world._elapsed_days,
        "farm_stock": world.farm_stock,
        "stats": _to_jsonable(world.stats.__dict__),
        "economy": {
            "food_stock": world.economy.food_stock,
            "restock_amount": world.economy.restock_amount,
            "open_hour": world.economy.open_hour,
            "close_hour": world.economy.close_hour,
        },
        "events": [_event_to_dict(event) for event in world.events],
        "dead_ids": [npc.id for npc in world.dead],
        "npcs": [_npc_to_dict(npc) for npc in world.npcs],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state(
    path,
    world_config: dict,
    npcs_config: dict,
    continue_days: Optional[int] = None,
    seed: Optional[int] = None,
) -> Simulation:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Corrupted save file: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != SAVE_FORMAT:
        raise ValueError("Unrecognized save file format.")
    required = {
        "seed",
        "total_days",
        "rng_state",
        "clock",
        "elapsed_days",
        "farm_stock",
        "stats",
        "economy",
        "events",
        "dead_ids",
        "npcs",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"Save file missing required keys: {sorted(missing)}")

    total_days = int(data["total_days"])
    elapsed_days = int(data["elapsed_days"])
    if continue_days is None:
        continue_days = max(0, total_days - elapsed_days)

    sim = Simulation(
        world_config,
        npcs_config,
        seed=seed if seed is not None else int(data["seed"]),
        days=total_days,
        print_report=False,
    )
    sim._total_days = total_days
    sim.days = continue_days

    world = sim.world
    sim.rng.setstate(_from_jsonable(data["rng_state"]))

    clock_data = data["clock"]
    world.clock = Clock(
        tick_minutes=int(clock_data.get("tick_minutes", 10)),
        day=int(clock_data["day"]),
        hour=int(clock_data["hour"]),
        minute=int(clock_data["minute"]),
        tick=int(clock_data["tick"]),
    )
    world._elapsed_days = elapsed_days
    world.farm_stock = int(data["farm_stock"])
    world.stats = _world_stats_from_dict(data["stats"])

    economy_data = data["economy"]
    world.economy.food_stock = int(economy_data["food_stock"])
    world.economy.restock_amount = int(economy_data.get("restock_amount", world.economy.restock_amount))
    world.economy.open_hour = int(economy_data.get("open_hour", world.economy.open_hour))
    world.economy.close_hour = int(economy_data.get("close_hour", world.economy.close_hour))

    world.events = [_event_from_dict(event) for event in data["events"]]
    npcs = [_npc_from_dict(npc_data, world) for npc_data in data["npcs"]]
    npc_by_id = {npc.id: npc for npc in npcs}
    world.npcs = npcs
    world.dead = [npc_by_id[npc_id] for npc_id in data["dead_ids"]]
    return sim