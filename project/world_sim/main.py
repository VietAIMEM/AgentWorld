from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from .logging import configure as configure_logging
from .simulation.simulation import Simulation

CONFIG_DIR = Path(__file__).resolve().parent / "config"

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "EVENT": 25,
    "WARNING": logging.WARNING,
}


def _load_json(name: str) -> dict:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="NPC world simulation")
    parser.add_argument("--days", type=int, default=None, help="number of days to simulate")
    parser.add_argument("--seed", type=int, default=42, help="random seed for determinism")
    parser.add_argument("--verbose", action="store_true", help="enable DEBUG logging and periodic state display")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "EVENT", "WARNING"],
        default=None,
        help="explicit log level (overrides --verbose)",
    )
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose, level=_LOG_LEVELS.get(args.log_level))
    world_config = _load_json("world.json")
    npcs_config = _load_json("npcs.json")
    simulation = Simulation(
        world_config,
        npcs_config,
        seed=args.seed,
        days=args.days,
        verbose=args.verbose,
    )
    simulation.run()


if __name__ == "__main__":
    main()