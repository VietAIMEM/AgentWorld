import json
import random
from pathlib import Path

from world_sim.simulation.world import World

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def load_configs():
    world_config = json.loads((CONFIG_DIR / "world.json").read_text(encoding="utf-8"))
    npcs_config = json.loads((CONFIG_DIR / "npcs.json").read_text(encoding="utf-8"))
    return world_config, npcs_config


def build_world(seed=1, world_config=None, npcs_config=None):
    wc, nc = load_configs()
    if world_config:
        wc.update(world_config)
    if npcs_config:
        nc = npcs_config
    return World(wc, nc, random.Random(seed))


def first_npc(world):
    return world.npcs[0]


def set_time(world, hour, minute=0):
    world.clock.hour = hour
    world.clock.minute = minute