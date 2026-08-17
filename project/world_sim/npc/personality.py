from dataclasses import dataclass


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class Personality:
    sociability: float = 0.5
    ambition: float = 0.5
    risk_tolerance: float = 0.5
    work_ethic: float = 0.5
    generosity: float = 0.5

    def __post_init__(self) -> None:
        self.sociability = _clamp01(self.sociability)
        self.ambition = _clamp01(self.ambition)
        self.risk_tolerance = _clamp01(self.risk_tolerance)
        self.work_ethic = _clamp01(self.work_ethic)
        self.generosity = _clamp01(self.generosity)