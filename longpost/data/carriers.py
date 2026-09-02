"""Carrier types.

Capacity is in loads. Reach is travel days a carrier covers in one season: a
leg longer than that does not arrive, and a leg shorter than half of it is a
round trip. That is what makes the fast carriers worth their small holds — and
what makes the far side of the chart a different problem from the near side.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CarrierType:
    key: str
    name: str
    capacity: int
    reach: float                  # travel days a season affords this carrier
    seasons: tuple                # seasons it can work at all
    terrains: tuple               # terrain it can work on
    team: str                     # what it actually is, on the ground
    note: str

    def can_work(self, season, terrain) -> bool:
        return season in self.seasons and terrain in self.terrains


LAND = ("INLAND", "PASS", "TUNNEL")
WATER = ("COAST", "TUNNEL")
ICE = ("ICE", "INLAND", "TUNNEL")

CARRIERS = {
    "FAST_HORSE": CarrierType(
        "FAST_HORSE", "fast horse", capacity=8, reach=30.0,
        seasons=("AUTUMN", "SPRING", "SUMMER"), terrains=LAND,
        team="four horses and two riders",
        note="outruns trouble, eats grain year round"),
    "HARDY_HORSE": CarrierType(
        "HARDY_HORSE", "hardy horse", capacity=18, reach=19.0,
        seasons=("AUTUMN", "WINTER", "SUMMER"), terrains=LAND,
        team="eight horses and four drivers",
        note="eats scrub, caught by anything that wants to"),
    "DOG_SLED": CarrierType(
        "DOG_SLED", "dog sled", capacity=12, reach=28.0,
        seasons=("WINTER",), terrains=ICE,
        team="three sleds and their teams",
        note="the only thing that makes deep winter routine"),
    "SMALL_BOAT": CarrierType(
        "SMALL_BOAT", "small boat", capacity=30, reach=25.0,
        seasons=("AUTUMN", "SPRING", "SUMMER"), terrains=WATER,
        team="a boat and five hands",
        note="weather sensitive"),
    "DEEP_VESSEL": CarrierType(
        "DEEP_VESSEL", "deep-sea vessel", capacity=110, reach=27.0,
        seasons=("AUTUMN", "SUMMER"), terrains=WATER,
        team="a vessel and eighteen hands",
        note="enormous capacity, ruinous to lose"),
}

# what the post owns at the first turn
STARTING_FLEET = ("HARDY_HORSE", "HARDY_HORSE", "FAST_HORSE",
                  "SMALL_BOAT", "DOG_SLED")
