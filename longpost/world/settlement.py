"""Settlements: what they hold, what they need, what they produce.

Decline, doom and abandonment attach here at M1 and M4. At M0 a settlement is
a population, a set of needs, a surplus, a standing and a desperation value.
"""

from dataclasses import dataclass, field

GOODS = ("GRAIN", "FUEL", "MEDICINE", "TOOLS", "POST")

# per head, per year
NEED_PER_HEAD = {
    "GRAIN": 1.0,
    "FUEL": 0.6,
    "MEDICINE": 0.12,
    "TOOLS": 0.2,
    "POST": 0.05,
}


@dataclass
class Settlement:
    id: int
    name: str
    pos: tuple            # world coordinates
    population: int
    surplus: tuple        # one or two goods produced beyond its own needs
    standing: float = 55.0
    desperation: float = 0.0
    known: bool = False   # discovered by the post
    abandoned_year: int = 0
    received: dict = field(default_factory=dict)

    def needs(self) -> dict:
        """What this settlement consumes in a year."""
        return {g: round(self.population * per, 2) for g, per in NEED_PER_HEAD.items()}

    @property
    def alive(self) -> bool:
        return self.abandoned_year == 0 and self.population > 0

    def radius(self) -> float:
        """Chart radius, scaled to population."""
        return 7.0 + (self.population ** 0.5) * 0.85
