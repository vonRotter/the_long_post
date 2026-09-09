"""The post's animals, boats and sleds.

A carrier is one thing the post owns. It runs one leg in a season or it rests.
"""

from dataclasses import dataclass, field

from ..data.carriers import CARRIERS


@dataclass
class Carrier:
    id: int
    kind: str                     # a key into CARRIERS
    at: int                       # the settlement it is standing at
    runs: int = 0
    delivered: int = 0
    history: list = field(default_factory=list)   # (year, season, edge id)

    @property
    def type(self):
        return CARRIERS[self.kind]

    @property
    def name(self) -> str:
        return f"{self.type.name} {self.id + 1}"

    def can_run(self, season, edge) -> bool:
        return self.type.can_work(season, edge.effective_terrain)

    def reaches(self, edge) -> bool:
        return edge.days <= self.type.reach

    def round_trip(self, edge) -> bool:
        """Whether the season affords the leg both ways.

        A carrier that can get there and back carries a return load and ends
        the season where it started, which is what makes a leg a run the post
        keeps rather than a one-way errand.
        """
        return edge.days * 2 <= self.type.reach
