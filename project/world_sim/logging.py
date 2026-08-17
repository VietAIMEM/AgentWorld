import logging
import sys

EVENT = 25
logging.addLevelName(EVENT, "EVENT")

_ROOT_NAME = "world_sim"
_configured = False


def get_logger(name: str = _ROOT_NAME) -> logging.Logger:
    return logging.getLogger(name)


def configure(verbose: bool = False, level: int | None = None) -> logging.Logger:
    global _configured
    logger = logging.getLogger(_ROOT_NAME)
    if _configured:
        return logger
    if level is None:
        level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)5s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    _configured = True
    return logger


def log_event(logger: logging.Logger, message: str) -> None:
    logger.log(EVENT, message)
