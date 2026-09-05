from setu.config.constants import ROUND_TO_DECIMALS
from setu.utils.errors import CrossSectionError


class DeckStrip:
    def __init__(self, name, width_m, z_from_m, z_to_m):
        self.name = name
        self.width_m = width_m
        self.z_from_m = z_from_m
        self.z_to_m = z_to_m

    def carries_traffic(self):
        return self.name.startswith("carriageway")

    def carries_pedestrians(self):
        return self.name.startswith(("footway", "footpath"))

    def to_dict(self):
        return self.__dict__


class Carriageway:
    def __init__(self, left_m, right_m):
        self.left_m = left_m
        self.right_m = right_m

    def width_m(self):
        return round(self.right_m - self.left_m, ROUND_TO_DECIMALS)


class DeckCrossSection:
    def __init__(self, strips):
        self.strips = tuple(strips)

    @staticmethod
    def from_widths(widths):
        strips = []
        edge_m = 0.0
        for name, width_m in widths.items():
            if width_m < 0:
                raise CrossSectionError(f"{name}: width must not be negative, got {width_m}")
            strips.append(DeckStrip(
                name=name,
                width_m=float(width_m),
                z_from_m=round(edge_m, ROUND_TO_DECIMALS),
                z_to_m=round(edge_m + width_m, ROUND_TO_DECIMALS),
            ))
            edge_m += width_m

        cs = DeckCrossSection(strips)
        if not cs.has_carriageway():
            raise CrossSectionError("cross-section has no carriageway")
        return cs

    def total_width_m(self):
        return round(sum(s.width_m for s in self.strips), ROUND_TO_DECIMALS)

    def has_carriageway(self):
        return any(s.carries_traffic() for s in self.strips)

    def strip_named(self, name):
        for s in self.strips:
            if s.name.startswith(name):
                return s
        return None

    def footways(self):
        return [s for s in self.strips if s.carries_pedestrians()]

    def carriageways(self, split="separate"):
        stretches = [
            Carriageway(left_m=s.z_from_m, right_m=s.z_to_m)
            for s in self.strips if s.carries_traffic()
        ]
        if split == "separate":
            return stretches
        if split == "combined":
            return [Carriageway(left_m=stretches[0].left_m, right_m=stretches[-1].right_m)]
        raise CrossSectionError(f"split must be 'separate' or 'combined', got {split!r}")
