from __future__ import annotations

from .object import WorldObject

LOCATION_OBJECT_TEMPLATES: dict[str, list[dict]] = {
    "commercial": [
        {"object_type": "stall", "name": "Stall", "interactions": ["inspect"]},
        {"object_type": "counter", "name": "Counter", "interactions": ["inspect"]},
    ],
    "social": [
        {"object_type": "table", "name": "Table", "interactions": ["sit"]},
        {"object_type": "bench", "name": "Bench", "interactions": ["sit"]},
        {"object_type": "fire", "name": "Fire", "interactions": ["sit"]},
    ],
    "residence": [
        {"object_type": "bed", "name": "Bed", "interactions": ["sit"]},
        {"object_type": "chair", "name": "Chair", "interactions": ["sit"]},
    ],
    "workplace": [
        {"object_type": "well", "name": "Well", "interactions": ["use"]},
        {"object_type": "crate", "name": "Crate", "interactions": ["inspect"]},
        {"object_type": "plant", "name": "Plant", "interactions": ["tend", "inspect"]},
    ],
    "natural": [
        {"object_type": "tree", "name": "Tree", "interactions": ["inspect"]},
        {"object_type": "log", "name": "Log", "interactions": ["sit"]},
    ],
}


def generate_objects_for_location(location) -> list[WorldObject]:
    templates = LOCATION_OBJECT_TEMPLATES.get(location.type, [])
    result: list[WorldObject] = []
    for template in templates:
        count = int(template.get("count", 1))
        for index in range(count):
            result.append(
                WorldObject(
                    id=f"{location.id}_{template['object_type']}_{index}",
                    name=template["name"],
                    location_id=location.id,
                    object_type=template["object_type"],
                    interactions=list(template["interactions"]),
                )
            )
    return result


def generate_world_objects(world) -> None:
    for location_id in sorted(world.locations):
        for obj in generate_objects_for_location(world.locations[location_id]):
            world.add_object(obj)