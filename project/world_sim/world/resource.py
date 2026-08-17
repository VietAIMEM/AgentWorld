from dataclasses import dataclass


@dataclass
class Resource:
    id: str
    name: str
    price: float = 0.0
    hunger_restore: float = 0.0
