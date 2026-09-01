"""Carrier types.

Capacity is in units of cargo. Speed is travel days covered in one season: a
leg longer than that does not arrive, which is what makes the fast carriers
worth their small holds.
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
    note: str

    def can_work(self, season, terrain) -> bool:
        return season in self.seasons and terrain in self.terrains


LAND = ("INLAND", "PASS", "TUNNEL")
WATER = ("COAST", "TUNNEL")
ICE = ("ICE", "INLAND", "TUNNEL")

CARRIERS = {
    "FAST_HORSE": CarrierType(
        "FAST_HORSE", "fast horse", capacity=3, reach=16.0,
        seasons=("AUTUMN", "SPRING", "SUMMER"), terrains=LAND,
        note="outruns trouble, eats grain year round"),
    "HARDY_HORSE": CarrierType(
        "HARDY_HORSE", "hardy horse", capacity=7, reach=9.0,
        seasons=("AUTUMN", "WINTER", "SUMMER"), terrains=LAND,
        note="eats scrub, caught by anything that wants to"),
    "DOG_SLED": CarrierType(
        "DOG_SLED", "dog sled", capacity=4, reach=15.0,
        seasons=("WINTER",), terrains=ICE,
        note="the only thing that makes deep winter routine"),
    "SMALL_BOAT": CarrierType(
        "SMALL_BOAT", "small boat", capacity=8, reach=12.0,
        seasons=("AUTUMN", "SPRING", "SUMMER"), terrains=WATER,
        note="weather sensitive"),
    "DEEP_VESSEL": CarrierType(
        "DEEP_VESSEL", "deep-sea vessel", capacity=26, reach=14.0,
        seasons=("AUTUMN", "SUMMER"), terrains=WATER,
        note="enormous capacity, ruinous to lose"),
}

# what the post owns at the first turn
STARTING_FLEET = ("HARDY_HORSE", "HARDY_HORSE", "FAST_HORSE",
                  "SMALL_BOAT", "DOG_SLED")
