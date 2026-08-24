"""The deck read across its width, strip by strip.

A cross-section is written the way an engineer would draw it: named strips in
order from the left edge of the deck to the right.

    DeckCrossSection.from_widths({
        "footpath_left": 1.50, "kerb_left": 0.45,
        "carriageway_1": 4.5, "median": 0.60, "carriageway_2": 4.5,
        "kerb_right": 0.45, "footpath_right": 1.50,
    })

Strips named `carriageway...` carry traffic. Strips named `footpath...` or
`footway...` carry the Clause 206 crowd loading. Everything else - kerbs,
medians, crash barriers - takes up width and carries no live load.

Distances across the deck are called z, measured from the left edge.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .errors import CrossSectionError
from .irc_code_rules.code_tables import ROUND_TO_DECIMALS

CARRIAGEWAY_PREFIX = "carriageway"
FOOTWAY_PREFIXES = ("footway", "footpath")


@dataclass(frozen=True)
class DeckStrip:
    """One named strip of the deck, and where it sits across the width."""

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
    """A stretch of deck that traffic runs on, and where it starts and ends."""

    left_m: float
    right_m: float

    @property
    def width_m(self) -> float:
        return round(self.right_m - self.left_m, ROUND_TO_DECIMALS)


@dataclass(frozen=True)
class DeckCrossSection:
    """The whole deck width, as ordered strips."""

    strips: tuple[DeckStrip, ...]

    @classmethod
    def from_widths(cls, widths: Mapping[str, float]) -> DeckCrossSection:
        """Builds a cross-section by walking named widths from the left deck edge."""
        strips = []
        z_m = 0.0

        for name, width_m in widths.items():
            if width_m < 0:
                raise CrossSectionError(f"{name}: width must not be negative, got {width_m}")
            strips.append(
                DeckStrip(
                    name=name,
                    width_m=float(width_m),
                    z_from_m=round(z_m, ROUND_TO_DECIMALS),
                    z_to_m=round(z_m + width_m, ROUND_TO_DECIMALS),
                )
            )
            z_m += width_m

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
        """Returns the first strip whose name starts with this, or None."""
        for strip in self.strips:
            if strip.name.startswith(name):
                return strip
        return None

    def footways(self) -> list[DeckStrip]:
        """Returns every footway and footpath strip, left to right."""
        return [strip for strip in self.strips if strip.carries_pedestrians]

    def carriageways(self, *, split: str = "separate") -> list[Carriageway]:
        """Returns the stretches of deck that traffic runs on, left to right.

        `split="separate"` treats each carriageway on its own, which is the right
        reading for a deck with a median. It matters: a carriageway under 5.30 m
        wide attracts its own residual UDL beside the vehicle, so two narrow
        carriageways read separately can be more onerous than the same width read
        as one. Whether a median separates the traffic or not changes the design
        load by 15 to 30 per cent, so setu never guesses - it is stated here.

        `split="combined"` reads all the traffic strips as one continuous stretch.
        """
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
