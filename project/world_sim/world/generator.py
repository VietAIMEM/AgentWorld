from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..npc.npc import Job
from .location import Location
from .region import Region

_WILDERNESS_REGION_ID = "wilderness"
_NATURAL_KINDS = {"forest": "Forest", "river": "River", "mountain": "Mountain"}


@dataclass
class NpcPlacement:
    npc_id: str
    home_id: str
    location_id: str
    settlement_id: str
    job_id: str
    work_location_id: str


@dataclass
class GeneratedWorld:
    locations: dict[str, Location]
    regions: dict[str, Region]
    jobs: dict[str, Job]
    placements: list[NpcPlacement] = field(default_factory=list)
    market_id: str = ""
    social_location: str = ""


class WorldGenerator:
    """Deterministic procedural world builder.

    Uses its own random.Random(seed) so generation never consumes the simulation
    RNG stream. Structure is deterministic by construction; the seed only varies
    coordinates and which non-hub natural locations attach to which settlement.
    """

    def __init__(self, world_config: dict, npcs_config: dict, seed: int):
        self.config = world_config
        self.npcs_config = npcs_config
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.gen = world_config.get("world_generation", {})

    def generate(self) -> GeneratedWorld:
        settlements = self._settlement_ids()
        locations = self._create_locations(settlements)
        self._connect(locations, settlements)
        self._attach_resources(locations, settlements)
        regions = self._build_regions(locations, settlements)
        jobs = self._build_jobs(settlements)
        placements = self._place_npcs(settlements, jobs)
        result = GeneratedWorld(
            locations=locations,
            regions=regions,
            jobs=jobs,
            placements=placements,
            market_id=f"{settlements[0]}_market",
            social_location=f"{settlements[0]}_tavern",
        )
        self._validate(result)
        return result

    def _settlement_ids(self) -> list[str]:
        count = max(1, int(self.gen.get("settlements", 2)))
        return [f"settlement_{i}" for i in range(count)]

    def _natural_ids(self) -> list[str]:
        natural: list[str] = []
        forest_count = int(self.gen.get("forests", 2))
        river_count = int(self.gen.get("rivers", 1))
        mountain_count = int(self.gen.get("mountains", 0))
        for i in range(max(0, forest_count)):
            natural.append(f"forest_{i}")
        for i in range(max(0, river_count)):
            natural.append(f"river_{i}")
        for i in range(max(0, mountain_count)):
            natural.append(f"mountain_{i}")
        return natural

    def _create_locations(self, settlements: list[str]) -> dict[str, Location]:
        locations: dict[str, Location] = {}
        houses = max(1, int(self.gen.get("houses_per_settlement", 10)))
        farms = int(self.gen.get("farms_per_settlement", 1))
        workshops = int(self.gen.get("workshops_per_settlement", 1))
        for s in settlements:
            locations[f"{s}_market"] = self._loc(
                f"{s}_market", "Market", "commercial", s, ["buy_food", "work", "socialize", "rest"]
            )
            locations[f"{s}_tavern"] = self._loc(
                f"{s}_tavern", "Tavern", "social", s, ["socialize", "work", "rest"]
            )
            for h in range(houses):
                locations[f"{s}_house_{h}"] = self._loc(
                    f"{s}_house_{h}", "House", "residence", s, ["sleep", "rest"]
                )
            for f in range(max(0, farms)):
                locations[f"{s}_farm_{f}"] = self._loc(
                    f"{s}_farm_{f}", "Farm", "workplace", s, ["work", "rest", "explore"]
                )
            for w in range(max(0, workshops)):
                locations[f"{s}_workshop_{w}"] = self._loc(
                    f"{s}_workshop_{w}", "Workshop", "workplace", s, ["work", "rest"]
                )
        for nid in self._natural_ids():
            kind = next(k for k in _NATURAL_KINDS if nid.startswith(k))
            locations[nid] = self._loc(
                nid, _NATURAL_KINDS[kind], "natural", _WILDERNESS_REGION_ID, ["explore", "forage"]
            )
        return locations

    def _loc(self, lid: str, name: str, ltype: str, region_id: str, activities) -> Location:
        return Location(
            id=lid,
            name=name,
            type=ltype,
            connected=[],
            resources=[],
            activities=list(activities),
            region_id=region_id,
            position=(round(self.rng.uniform(0.0, 100.0), 2), round(self.rng.uniform(0.0, 100.0), 2)),
        )

    @staticmethod
    def _link(locations: dict[str, Location], a: str, b: str) -> None:
        if b not in locations[a].connected:
            locations[a].connected.append(b)
        if a not in locations[b].connected:
            locations[b].connected.append(a)

    def _connect(self, locations: dict[str, Location], settlements: list[str]) -> None:
        natural = self._natural_ids()
        hub = natural[0] if natural else None
        for s in settlements:
            market = f"{s}_market"
            self._link(locations, market, f"{s}_tavern")
            for lid, loc in locations.items():
                if loc.region_id != s:
                    continue
                if lid.startswith(f"{s}_house_") or lid.startswith(f"{s}_farm_") or lid.startswith(
                    f"{s}_workshop_"
                ):
                    self._link(locations, market, lid)
            if hub is not None:
                self._link(locations, market, hub)
        roads = bool(self.gen.get("settlement_roads", True))
        if roads and len(settlements) > 1:
            for i in range(len(settlements) - 1):
                self._link(locations, f"{settlements[i]}_market", f"{settlements[i + 1]}_market")
        elif hub is None and len(settlements) > 1:
            for i in range(len(settlements) - 1):
                self._link(locations, f"{settlements[i]}_market", f"{settlements[i + 1]}_market")
        for extra in natural[1:] if hub is not None else []:
            self._link(locations, extra, self.rng.choice(settlements) + "_market")

    def _attach_resources(self, locations: dict[str, Location], settlements: list[str]) -> None:
        resource_ids = [r.get("id") for r in self.config.get("resources", [])]
        food = "food" if "food" in resource_ids else None
        for s in settlements:
            for lid, loc in locations.items():
                if loc.region_id != s:
                    continue
                if lid.startswith(f"{s}_market") or lid.startswith(f"{s}_farm_"):
                    loc.resources = [food] if food else []
        for lid, loc in locations.items():
            if lid.startswith("forest_"):
                loc.resources = [food] if food else []

    def _build_regions(self, locations: dict[str, Location], settlements: list[str]) -> dict[str, Region]:
        regions: dict[str, Region] = {}
        for s in settlements:
            ids = sorted(lid for lid, loc in locations.items() if loc.region_id == s)
            regions[s] = Region(id=s, name=f"Settlement {s}", kind="settlement", location_ids=ids)
        wilderness_ids = sorted(
            lid for lid, loc in locations.items() if loc.region_id == _WILDERNESS_REGION_ID
        )
        regions[_WILDERNESS_REGION_ID] = Region(
            id=_WILDERNESS_REGION_ID, name="Wilderness", kind="wilderness", location_ids=wilderness_ids
        )
        return regions

    def _build_jobs(self, settlements: list[str]) -> dict[str, Job]:
        job_defs = {j["id"]: j for j in self.config.get("jobs", [])}
        jobs: dict[str, Job] = {}
        for s in settlements:
            mapping = (
                ("farmer", f"{s}_farm_0"),
                ("merchant", f"{s}_market"),
                ("worker", f"{s}_workshop_0"),
            )
            for role, work_location in mapping:
                jd = job_defs.get(role)
                if jd is None:
                    continue
                job_id = f"{role}_{s}"
                jobs[job_id] = Job(
                    id=job_id,
                    name=jd["name"],
                    work_location=work_location,
                    income_per_tick=float(jd.get("income_per_tick", 0.0)),
                    energy_cost=float(jd.get("energy_cost", 0.0)),
                    shift_ticks=int(jd.get("shift_ticks", 48)),
                    produces_food=bool(jd.get("produces_food", False)),
                )
        return jobs

    def _place_npcs(self, settlements: list[str], jobs: dict[str, Job]) -> list[NpcPlacement]:
        placements: list[NpcPlacement] = []
        houses = max(1, int(self.gen.get("houses_per_settlement", 10)))
        npcs = self.npcs_config.get("npcs", [])
        for idx, npc_data in enumerate(npcs):
            role = npc_data.get("job")
            settlement = settlements[idx % len(settlements)]
            job_id = f"{role}_{settlement}"
            if job_id not in jobs:
                raise ValueError(
                    f"NPC {npc_data.get('id')!r} references job role {role!r} "
                    f"but no {role!r} job exists in {settlement}."
                )
            house_k = (idx // len(settlements)) % houses
            home = f"{settlement}_house_{house_k}"
            placements.append(
                NpcPlacement(
                    npc_id=npc_data["id"],
                    home_id=home,
                    location_id=home,
                    settlement_id=settlement,
                    job_id=job_id,
                    work_location_id=jobs[job_id].work_location,
                )
            )
        return placements

    def _reachable(self, locations: dict[str, Location], start: str) -> set[str]:
        if start not in locations:
            return set()
        seen = {start}
        queue = deque(locations[start].connected)
        while queue:
            nid = queue.popleft()
            if nid in seen or nid not in locations:
                continue
            seen.add(nid)
            queue.extend(locations[nid].connected)
        return seen

    def _path_exists(self, locations: dict[str, Location], start: str, target: str) -> bool:
        if start not in locations or target not in locations:
            return False
        if start == target:
            return True
        return target in self._reachable(locations, start)

    def _validate(self, result: GeneratedWorld) -> None:
        locations = result.locations
        commercial = [lid for lid, loc in locations.items() if loc.type == "commercial"]
        if not commercial:
            raise ValueError("Generated world has no commercial locations.")
        if result.market_id not in locations:
            raise ValueError(f"Generated market_id {result.market_id!r} does not exist.")
        if result.social_location not in locations:
            raise ValueError(f"Generated social_location {result.social_location!r} does not exist.")
        for lid, loc in locations.items():
            for neighbor in loc.connected:
                if neighbor not in locations:
                    raise ValueError(f"Location {lid!r} references unknown connected location {neighbor!r}.")
        reachable = self._reachable(locations, result.market_id)
        isolated = [lid for lid in locations if lid not in reachable]
        if isolated:
            raise ValueError(f"Unreachable locations from market: {sorted(isolated)}")
        food_naturals = [
            lid
            for lid, loc in locations.items()
            if loc.type == "natural" and "food" in loc.resources
        ]
        has_food_resource = any(
            r.get("id") == "food" for r in self.config.get("resources", [])
        )
        for job_id, job in result.jobs.items():
            if job.work_location not in locations:
                raise ValueError(f"Job {job_id!r} references unknown work location {job.work_location!r}.")
        for placement in result.placements:
            if placement.home_id not in locations:
                raise ValueError(f"NPC {placement.npc_id!r} home {placement.home_id!r} does not exist.")
            if placement.location_id not in locations:
                raise ValueError(
                    f"NPC {placement.npc_id!r} location {placement.location_id!r} does not exist."
                )
            if placement.work_location_id not in locations:
                raise ValueError(
                    f"NPC {placement.npc_id!r} work location {placement.work_location_id!r} does not exist."
                )
            for target in (result.market_id, result.social_location, placement.work_location_id):
                if not self._path_exists(locations, placement.home_id, target):
                    raise ValueError(
                        f"NPC {placement.npc_id!r} home {placement.home_id!r} "
                        f"cannot reach {target!r}."
                    )
            if has_food_resource and not any(
                self._path_exists(locations, placement.home_id, nid) for nid in food_naturals
            ):
                raise ValueError(
                    f"NPC {placement.npc_id!r} home {placement.home_id!r} "
                    "cannot reach any food-bearing natural location."
                )