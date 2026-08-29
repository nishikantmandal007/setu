# The deck read across its width as named, ordered strips, left to right from the deck's
# left edge - the way an engineer would draw it. z is measured across the deck from that
# same left edge. This is the file an OsdagBridge maintainer will recognise fastest: it
# plays the part CrossSectionLayout plays there, walking named components left to right.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .errors import CrossSectionError
from .irc_code_rules.code_tables import ROUND_TO_DECIMALS

# A strip is classified by its name prefix: carriageway* carries traffic, footway*/
# footpath* carries the Clause 206 crowd, and everything else - kerbs, medians, crash
# barriers - takes up width and carries no live load.
CARRIAGEWAY_PREFIX = "carriageway"
FOOTWAY_PREFIXES = ("footway", "footpath")

# The remaining two prefixes dead_loads.surfacing_pressure_at dispatches on, to decide what
# added surfacing sits on a kerb or a median.
KERB_PREFIX = "kerb"
MEDIAN_PREFIX = "median"


@dataclass(frozen=True)
class DeckStrip:
    # One named strip of the deck, and where it sits across the width.
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
    # A stretch of deck that traffic runs on, and where it starts and ends.
    left_m: float
    right_m: float

    @property
    def width_m(self) -> float:
        return round(self.right_m - self.left_m, ROUND_TO_DECIMALS)


@dataclass(frozen=True)
class DeckCrossSection:
    # The whole deck width, as ordered strips.
    strips: tuple[DeckStrip, ...]

    @classmethod
    def from_widths(cls, widths: Mapping[str, float]) -> DeckCrossSection:
        # Walks the named widths from the left deck edge, building a strip for each.
        strips = []
        edge_m = 0.0

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
        # No caller in setu itself - public API for a caller that addresses a strip by name.
        for strip in self.strips:
            if strip.name.startswith(name):
                return strip
        return None

    def footways(self) -> list[DeckStrip]:
        return [strip for strip in self.strips if strip.carries_pedestrians]

    def carriageways(self, *, split: str = "separate") -> list[Carriageway]:
        # split is stringly-typed - two magic values, checked by the trailing raise below -
        # because it propagates up to rank_all_positions(carriageways_read_as=...), which is
        # public API. Left exactly as it is.
        #
        # "separate" reads each carriageway on its own, which is right for a deck with a
        # median: a carriageway under 5.30 m attracts its own residual UDL beside the
        # vehicle, so two narrow carriageways read separately can be more onerous than the
        # same width read as one. Whether a median separates the traffic changes the design
        # load by 15 to 30 per cent, so setu never guesses - it is stated here.
        #
        # "combined" reads all the traffic strips as one continuous stretch instead.
        stretches = [
            Carriageway(left_m=strip.z_from_m, right_m=strip.z_to_m)
            for strip in self.strips
            if strip.carries_traffic
        ]

        if split == "separate":
            return stretches
        if split == "combined":
            return [Carriageway(left_m=stretches[0].left_m, right_m=stretches[-1].right_m)]

        raise CrossSectionError(f"split must be 'separate' or 'combined', got {split!r}")
