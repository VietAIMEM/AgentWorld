from dataclasses import dataclass


@dataclass
class Clock:
    tick_minutes: int = 10
    day: int = 1
    hour: int = 6
    minute: int = 0
    tick: int = 0

    def stamp(self) -> str:
        return f"Day {self.day} {self.hour:02d}:{self.minute:02d}"

    def advance(self) -> None:
        self.tick += 1
        self.minute += self.tick_minutes
        if self.minute >= 60:
            carry = self.minute // 60
            self.minute %= 60
            self.hour += carry
        if self.hour >= 24:
            carry = self.hour // 24
            self.hour %= 24
            self.day += carry
