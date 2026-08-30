from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .errors import CrossSectionError
from .irc_code_rules.code_tables import ROUND_TO_DECIMALS

CARRIAGEWAY_PREFIX = "carriageway"
FOOTWAY_PREFIXES = ("footway", "footpath")
KERB_PREFIX = "kerb"
MEDIAN_PREFIX = "median"
CRASH_BARRIER_PREFIX = "crash_barrier"

READ_EACH_CARRIAGEWAY_ON_ITS_OWN = "separate"
READ_ALL_CARRIAGEWAYS_AS_ONE = "combined"

DECK_LEFT_EDGE_M = 0.0


@dataclass(frozen=True)
class DeckStrip:
    name: str
    width_m: float
    z_from_m: float
    z_to_m: float

    @property
    def carries_traffic(self) -> bool:
        return self.name.startswith(CARRIAGEWAY_PREFIX)

    @property
    def carries_pedestrians(self) -> bool:
        return self.name.startswith(FOOTWAY_PREFIXES)


@dataclass(frozen=True)
class Carriageway:
    left_m: float
    right_m: float

    @property
    def width_m(self) -> float:
        return round(self.right_m - self.left_m, ROUND_TO_DECIMALS)


@dataclass(frozen=True)
class DeckCrossSection:
    strips: tuple[DeckStrip, ...]

    @classmethod
    def from_widths(cls, widths: Mapping[str, float]) -> DeckCrossSection:
        strips = []
        edge_m = DECK_LEFT_EDGE_M

        for name, width_m in widths.items():
            if width_m < 0:
                raise CrossSectionError(f"{name}: width must not be negative, got {width_m}")
            strips.append(
                DeckStrip(
                    name=name,
                    width_m=float(width_m),
                    z_from_m=round(edge_m, ROUND_TO_DECIMALS),
                    z_to_m=round(edge_m + width_m, ROUND_TO_DECIMALS),
                )
            )
            edge_m += width_m

        cross_section = cls(strips=tuple(strips))
        if not cross_section.has_carriageway:
            raise CrossSectionError(
                "this cross-section has no carriageway, so no vehicle can be placed on "
                f"it; name at least one strip starting with {CARRIAGEWAY_PREFIX!r}. "
                f"Strips given: {[strip.name for strip in strips]}"
            )
        return cross_section

    @property
    def total_width_m(self) -> float:
        return round(sum(strip.width_m for strip in self.strips), ROUND_TO_DECIMALS)

    @property
    def has_carriageway(self) -> bool:
        return any(strip.carries_traffic for strip in self.strips)

    def strip_named(self, name: str) -> DeckStrip | None:
        for strip in self.strips:
            if strip.name.startswith(name):
                return strip
        return None

    def footways(self) -> list[DeckStrip]:
        return [strip for strip in self.strips if strip.carries_pedestrians]

    def carriageways(
        self, *, split: str = READ_EACH_CARRIAGEWAY_ON_ITS_OWN
    ) -> list[Carriageway]:
        # A carriageway under 5.30 m attracts its own residual UDL, so two narrow
        # carriageways read separately can be more onerous than the same width read as one.
        stretches = [
            Carriageway(left_m=strip.z_from_m, right_m=strip.z_to_m)
            for strip in self.strips
            if strip.carries_traffic
        ]

        if split == READ_EACH_CARRIAGEWAY_ON_ITS_OWN:
            return stretches
        if split == READ_ALL_CARRIAGEWAYS_AS_ONE:
            return [Carriageway(left_m=stretches[0].left_m, right_m=stretches[-1].right_m)]

        raise CrossSectionError(f"split must be 'separate' or 'combined', got {split!r}")
