from __future__ import annotations

from dataclasses import dataclass

from ..logging import get_logger, log_event
from ..npc.memory import Memory
from ..npc.needs import Needs
from ..npc.npc import Job, NPC
from ..npc.personality import Personality
from ..world.economy import EconomySystem
from ..world.location import Location
from ..world.resource import Resource
from .clock import Clock
from .events import EventState, WorldEvent

log = get_logger()


@dataclass
class WorldStats:
    food_consumed: int = 0
    food_bought: int = 0
    work_actions: int = 0
    social_interactions: int = 0
    deaths: int = 0
    money_earned: float = 0.0


class World:
    def __init__(self, world_config: dict, npcs_config: dict, rng):
        self.config = world_config
        self.rng = rng
        self.locations: dict[str, Location] = {}
        self.resources: dict[str, Resource] = {}
        self.npcs: list[NPC] = []
        self.dead: list[NPC] = []
        self.events: list[WorldEvent] = []
        self.stats = WorldStats()
        economy_cfg = self.config.get("economy", {})
        self.market_id = economy_cfg.get("market_id", "market")
        clock_cfg = self.config.get("clock", {})
        self.clock = Clock(
            tick_minutes=int(clock_cfg.get("tick_minutes", 10)),
            day=int(clock_cfg.get("start_day", 1)),
            hour=int(clock_cfg.get("start_hour", 6)),
            minute=int(clock_cfg.get("start_minute", 0)),
        )
        self.economy = EconomySystem(self.config, rng)
        self._load_locations()
        self._load_resources()
        self._load_npcs(npcs_config)
        self._schedule_events()

    def _load_locations(self) -> None:
        for location_data in self.config.get("locations", []):
            self.locations[location_data["id"]] = Location(
                id=location_data["id"],
                name=location_data["name"],
                type=location_data["type"],
                connected=list(location_data.get("connected", [])),
                resources=list(location_data.get("resources", [])),
                activities=list(location_data.get("activities", [])),
            )

    def _load_resources(self) -> None:
        for resource_data in self.config.get("resources", []):
            self.resources[resource_data["id"]] = Resource(
                id=resource_data["id"],
                name=resource_data["name"],
                price=float(resource_data.get("price", 0.0)),
                hunger_restore=float(resource_data.get("hunger_restore", 0.0)),
            )

    def _load_npcs(self, npcs_config: dict) -> None:
        defaults = self.config.get("npc_defaults", {})
        jobs: dict[str, Job] = {}
        for job_data in self.config.get("jobs", []):
            jobs[job_data["id"]] = Job(
                id=job_data["id"],
                name=job_data["name"],
                work_location=job_data["work_location"],
                income_per_tick=float(job_data.get("income_per_tick", 0.0)),
                energy_cost=float(job_data.get("energy_cost", 0.0)),
                shift_ticks=int(job_data.get("shift_ticks", 48)),
            )
        max_size = int(self.config.get("memory", {}).get("max_size", 50))
        for npc_data in npcs_config.get("npcs", []):
            personality_data = dict(defaults.get("personality", {}))
            personality_data.update(npc_data.get("personality", {}))
            personality = Personality(
                sociability=personality_data.get("sociability", 0.5),
                ambition=personality_data.get("ambition", 0.5),
                risk_tolerance=personality_data.get("risk_tolerance", 0.5),
                work_ethic=personality_data.get("work_ethic", 0.5),
                generosity=personality_data.get("generosity", 0.5),
            )
            needs = Needs(
                hunger=float(npc_data.get("hunger", defaults.get("hunger", 20))),
                energy=float(npc_data.get("energy", defaults.get("energy", 95))),
                social=float(npc_data.get("social", defaults.get("social", 60))),
                health=float(npc_data.get("health", defaults.get("health", 100))),
            )
            home = npc_data.get("home", defaults.get("home", "home"))
            location = npc_data.get("location", home)
            npc = NPC(
                id=npc_data["id"],
                name=npc_data["name"],
                age=int(npc_data.get("age", defaults.get("age", 30))),
                money=float(npc_data.get("money", defaults.get("money", 50))),
                job=jobs[npc_data["job"]],
                location_id=location,
                home_id=home,
                needs=needs,
                personality=personality,
                memory=Memory(max_size=max_size),
            )
            self.npcs.append(npc)

    def _schedule_events(self) -> None:
        events_cfg = self.config.get("events", {})
        count = int(events_cfg.get("count", 8))
        min_spacing = int(events_cfg.get("min_spacing_ticks", 24))
        total_ticks = int(self.config.get("simulation", {}).get("days", 30)) * 24 * (60 // self.clock.tick_minutes)
        last_start: dict[tuple[str, str], int] = {}
        attempts = 0
        while len(self.events) < count and attempts < count * 4:
            attempts += 1
            event_type = self.rng.choice(["festival", "rain"])
            if event_type == "festival":
                location_id = self.rng.choice(["market", "tavern"])
                duration = self.rng.randint(12, 24)
                description = f"Festival at {self.get_location(location_id).name}"
            else:
                location_id = "forest"
                duration = self.rng.randint(12, 36)
                description = f"Heavy rain at {self.get_location(location_id).name}"
            key = (event_type, location_id)
            start_tick = self.rng.randint(0, max(0, total_ticks - 20))
            if last_start.get(key) is not None and start_tick < last_start[key] + min_spacing:
                continue
            last_start[key] = start_tick
            self.events.append(
                WorldEvent(
                    id=f"event_{len(self.events)}",
                    type=event_type,
                    description=description,
                    start_tick=start_tick,
                    duration_ticks=duration,
                    location_id=location_id,
                )
            )

    def get_location(self, location_id: str) -> Location | None:
        return self.locations.get(location_id)

    def get_npc(self, npc_id: str) -> NPC | None:
        for npc in self.npcs:
            if npc.id == npc_id:
                return npc
        return None

    def npcs_at(self, location_id: str) -> list[NPC]:
        return [npc for npc in self.npcs if npc.alive and npc.location_id == location_id]

    def alive_npcs(self) -> list[NPC]:
        return [npc for npc in self.npcs if npc.alive]

    def update_time(self) -> None:
        day_before = self.clock.day
        self.clock.advance()
        if self.clock.day != day_before:
            self.economy.restock()
            log_event(log, f"[{self.clock.stamp()}] The Market restocked its food supply.")

    def is_shop_open(self) -> bool:
        return self.economy.is_shop_open(self.clock)

    def active_events(self) -> list[WorldEvent]:
        return [event for event in self.events if event.state is EventState.ACTIVE]

    def process_events(self) -> None:
        for event in self.events:
            if event.state is EventState.SCHEDULED and self.clock.tick >= event.start_tick:
                event.state = EventState.ACTIVE
                event.started_tick = self.clock.tick
                log_event(log, f"[{self.clock.stamp()}] {event.description} begins.")
            elif event.state is EventState.ACTIVE and self.clock.tick - event.started_tick >= event.duration_ticks:
                event.state = EventState.COMPLETED
                log_event(log, f"[{self.clock.stamp()}] {event.description} ends.")

    def npc_die(self, npc: NPC) -> None:
        npc.alive = False
        npc.current_action = None
        self.dead.append(npc)
        self.stats.deaths += 1
        log_event(log, f"[{self.clock.stamp()}] {npc.name} has died.")