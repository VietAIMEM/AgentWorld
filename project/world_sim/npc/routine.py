from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RoutineBlock:
    start_hour: int
    end_hour: int
    activity: str
    bias: float
    intent_kind: Optional[str] = None


@dataclass
class DailyRoutine:
    id: str
    blocks: list[RoutineBlock] = field(default_factory=list)


def _b(start: int, end: int, activity: str, bias: float, intent_kind: Optional[str] = None) -> RoutineBlock:
    return RoutineBlock(
        start_hour=start,
        end_hour=end,
        activity=activity,
        bias=bias,
        intent_kind=intent_kind,
    )


ROUTINES: dict[str, DailyRoutine] = {
    "worker": DailyRoutine(
        id="worker",
        blocks=[
            _b(0, 6, "sleep", 1.0, "sleeping"),
            _b(6, 8, "rest", 0.5, "resting"),
            _b(8, 12, "work", 1.0, "working"),
            _b(12, 13, "eat", 0.9, "eating"),
            _b(13, 17, "work", 1.0, "working"),
            _b(17, 18, "rest", 0.4, "resting"),
            _b(18, 21, "socialize", 0.7, "socializing"),
            _b(21, 24, "rest", 0.5, "resting"),
        ],
    ),
    "farmer": DailyRoutine(
        id="farmer",
        blocks=[
            _b(0, 5, "sleep", 1.0, "sleeping"),
            _b(5, 8, "rest", 0.4, "resting"),
            _b(8, 12, "work", 1.0, "working"),
            _b(12, 13, "eat", 0.9, "eating"),
            _b(13, 18, "work", 1.0, "working"),
            _b(18, 21, "socialize", 0.5, "socializing"),
            _b(21, 24, "rest", 0.6, "resting"),
        ],
    ),
    "merchant": DailyRoutine(
        id="merchant",
        blocks=[
            _b(0, 6, "sleep", 1.0, "sleeping"),
            _b(6, 8, "rest", 0.4, "resting"),
            _b(8, 12, "work", 1.0, "working"),
            _b(12, 13, "eat", 0.8, "eating"),
            _b(13, 17, "work", 1.0, "working"),
            _b(17, 18, "eat", 0.4, "eating"),
            _b(18, 21, "socialize", 0.7, "socializing"),
            _b(21, 24, "rest", 0.5, "resting"),
        ],
    ),
    "unemployed": DailyRoutine(
        id="unemployed",
        blocks=[
            _b(0, 7, "sleep", 1.0, "sleeping"),
            _b(7, 9, "rest", 0.6, "resting"),
            _b(9, 12, "explore", 0.7, "exploring"),
            _b(12, 13, "eat", 0.8, "eating"),
            _b(13, 18, "socialize", 0.6, "socializing"),
            _b(18, 21, "socialize", 0.8, "socializing"),
            _b(21, 24, "rest", 0.7, "resting"),
        ],
    ),
    "social": DailyRoutine(
        id="social",
        blocks=[
            _b(0, 7, "sleep", 1.0, "sleeping"),
            _b(7, 10, "rest", 0.7, "resting"),
            _b(10, 13, "socialize", 0.8, "socializing"),
            _b(13, 14, "eat", 0.8, "eating"),
            _b(14, 18, "socialize", 0.7, "socializing"),
            _b(18, 22, "socialize", 1.0, "socializing"),
            _b(22, 24, "rest", 0.6, "resting"),
        ],
    ),
    "elderly": DailyRoutine(
        id="elderly",
        blocks=[
            _b(0, 6, "sleep", 1.0, "sleeping"),
            _b(6, 8, "rest", 0.7, "resting"),
            _b(8, 12, "rest", 0.6, "resting"),
            _b(12, 13, "eat", 0.9, "eating"),
            _b(13, 18, "socialize", 0.6, "socializing"),
            _b(18, 21, "socialize", 0.5, "socializing"),
            _b(21, 24, "rest", 0.8, "resting"),
        ],
    ),
}

ELDERLY_AGE = 60

JOB_TO_ROUTINE = {
    "farmer": "farmer",
    "merchant": "merchant",
    "worker": "worker",
}


def routine_id_for_job(job_id: Optional[str], age: Optional[int] = None) -> str:
    if age is not None and age >= ELDERLY_AGE:
        return "elderly"
    return JOB_TO_ROUTINE.get(job_id, "unemployed")


def routine_for_npc(npc, world) -> DailyRoutine:
    routine_id = getattr(npc, "routine_id", None)
    if routine_id in ROUTINES:
        return ROUTINES[routine_id]
    return ROUTINES[routine_id_for_job(getattr(npc.job, "id", None), getattr(npc, "age", None))]


def _hour_in_block(hour: int, block: RoutineBlock) -> bool:
    if block.start_hour <= block.end_hour:
        return block.start_hour <= hour < block.end_hour
    return hour >= block.start_hour or hour < block.end_hour


def active_block(routine: DailyRoutine, hour: int) -> Optional[RoutineBlock]:
    for block in routine.blocks:
        if _hour_in_block(hour, block):
            return block
    return None