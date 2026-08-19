from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..decision.decision_system import Decision
from ..logging import get_logger
from ..npc.goals import Goal, GoalType

log = get_logger()


class Action(ABC):
    action_type = "base"

    def __init__(self, rng, config: dict, decision: Decision | None):
        self.rng = rng
        self.config = config
        self.decision = decision
        self.priority = decision.priority if decision is not None else 0.0
        self.ticks_elapsed = 0
        self._actions_cfg = config.get("actions", {})

    @abstractmethod
    def can_execute(self, npc, world) -> bool:
        ...

    def start(self, npc, world) -> None:
        pass

    def apply(self, npc, world) -> None:
        pass

    def tick(self, npc, world) -> None:
        self.ticks_elapsed += 1
        self.apply(npc, world)
        if self.is_complete(npc, world):
            self.finish(npc, world)
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f"[{world.clock.stamp()}] {npc.name} completed action: {self.action_type}.")

    @abstractmethod
    def is_complete(self, npc, world) -> bool:
        ...

    def finish(self, npc, world) -> None:
        pass

    def cancel(self, npc, world) -> None:
        pass

    def _int(self, key: str, default: int) -> int:
        return int(self._actions_cfg.get(key, default))

    def _float(self, key: str, default: float) -> float:
        return float(self._actions_cfg.get(key, default))


class ActionManager:
    def __init__(self, rng, config: dict):
        from .eating import BuyFoodAction, EatAction
        from .exploring import ExploreAction
        from .interacting import InteractAction
        from .movement import MoveAction
        from .resting import RestAction
        from .sleeping import SleepAction
        from .social import SocializeAction
        from .working import WorkAction

        self.rng = rng
        self.config = config
        self._registry: dict[str, type] = {
            "move": MoveAction,
            "eat": EatAction,
            "buy_food": BuyFoodAction,
            "sleep": SleepAction,
            "work": WorkAction,
            "socialize": SocializeAction,
            "rest": RestAction,
            "explore": ExploreAction,
            "interact": InteractAction,
        }

    def register(self, name: str, action_cls: type) -> None:
        self._registry[name] = action_cls

    def update(self, npc, decision: Decision, world) -> Action:
        current = npc.current_action
        if current is not None and not current.is_complete(npc, world) and current.can_execute(npc, world):
            if self._compatible(npc, current):
                same_goal = npc.current_goal is not None and npc.current_goal.type == decision.goal.type
                same_action = current.action_type == decision.action_type
                same_target = (
                    decision.action_type != "move"
                    or decision.target_location_id is None
                    or getattr(current, "target", None) == decision.target_location_id
                )
                if same_goal and same_action and same_target:
                    return current
                if not decision.urgent and not same_goal:
                    return current
                if same_goal and current.priority >= decision.priority:
                    return current
                if decision.urgent and not same_goal:
                    self._log_interrupted(npc, current, decision, world)
        if current is not None:
            if current.is_complete(npc, world):
                npc.current_action = None
            else:
                current.cancel(npc, world)
                npc.current_action = None
        action = self._build(decision)
        if not action.can_execute(npc, world):
            from .resting import RestAction

            if decision.goal.type is GoalType.EAT:
                decision = Decision(
                    goal=Goal(GoalType.REST, decision.priority, npc.location_id),
                    action_type="rest",
                    priority=decision.priority,
                )
            action = RestAction(self.rng, self.config, decision)
        changed = npc.current_goal is None or npc.current_goal.type != decision.goal.type
        action.start(npc, world)
        npc.current_action = action
        if changed:
            decision.goal.started_tick = world.clock.tick
            self._log_goal_committed(npc, decision, world)
        else:
            previous = npc.current_goal
            if previous is not None and previous.started_tick is not None:
                decision.goal.started_tick = previous.started_tick
        npc.current_goal = decision.goal
        return action

    @staticmethod
    def _compatible(npc, current) -> bool:
        goal = npc.current_goal
        if goal is None or goal.type is not GoalType.EAT:
            return True
        return current.action_type in ("eat", "move", "buy_food")

    def _build(self, decision: Decision) -> Action:
        from .resting import RestAction

        action_cls = self._registry.get(decision.action_type, RestAction)
        return action_cls(self.rng, self.config, decision)

    @staticmethod
    def _log_goal_committed(npc, decision: Decision, world) -> None:
        if not log.isEnabledFor(logging.DEBUG):
            return
        prev = npc.current_goal.type.value if npc.current_goal else "-"
        lines = [
            f"[{world.clock.stamp()}] {npc.name} goal committed: {prev} -> "
            f"{decision.goal.type.value} ({decision.action_type})"
        ]
        lines.append(
            f"  needs: hunger={npc.needs.hunger:.1f} energy={npc.needs.energy:.1f} "
            f"social={npc.needs.social:.1f} health={npc.needs.health:.1f}"
        )
        if decision.candidates:
            ranking = ", ".join(
                f"{key.upper()}={value:.2f}"
                for key, value in sorted(decision.candidates.items(), key=lambda item: item[1], reverse=True)
            )
            lines.append(f"  scores: {ranking}")
        lines.append(f"  reason = {decision.reason}")
        log.debug("\n".join(lines))

    @staticmethod
    def _log_interrupted(npc, current, decision: Decision, world) -> None:
        if not log.isEnabledFor(logging.DEBUG):
            return
        prev = npc.current_goal.type.value if npc.current_goal else "-"
        log.debug(
            f"[{world.clock.stamp()}] {npc.name} action interrupted by emergency: "
            f"{current.action_type} ({prev}) -> {decision.goal.type.value} ({decision.action_type}) "
            f"[{decision.reason}]"
        )