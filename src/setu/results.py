"""What setu hands back, and everything needed to reproduce it.

A result is only useful if someone can check it. So a CriticalPosition carries
the whole story: which arrangement of lanes governed, which vehicle sat in each
one, which way it was facing, where along the span it stopped, how many of them
were in the lane, what impact factor each one attracted, and what reduction was
applied at the end.

Every number in a report can be traced back to one of these fields, and the
placement can be rebuilt in any other program from `vehicles` alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VehiclePlacement:
    """One vehicle, where it ended up, and what it attracted."""

    vehicle_name: str
    z_centre_m: float
    """Where its centreline sits across the deck."""

    x_front_m: float
    """Where the front of the leading vehicle sits along the span."""

    impact_factor: float

    train_x_front_m: tuple[float, ...] = ()
    """Where the front of every vehicle in this lane sits, leading vehicle first.

    A lane may carry several vehicles nose to tail, and all of them are part of
    the load case - so all of them are here, ready to be redrawn.
    """

    @property
    def vehicles_in_train(self) -> int:
        return max(len(self.train_x_front_m), 1)

    @property
    def is_facing_backwards(self) -> bool:
        return self.vehicle_name.endswith("_reversed")


@dataclass(frozen=True)
class CriticalPosition:
    """The worst legal load the deck has to carry, for one response quantity.

    `response` is what the deck actually has to be designed for.
    `response_before_reduction` is the same number before Table 8, kept visible
    so a report can show exactly what each part of the code contributed.
    """

    response_name: str
    adverse: str
    """Which direction is the damaging one - 'maximum' or 'minimum'."""

    response: float
    response_before_reduction: float
    lane_reduction: float
    design_lanes: int
    lane_pattern: str
    """The arrangement that governed, written out, e.g. 'zone_70r + class_a'."""

    carriageways_read_as: str
    vehicles: list[VehiclePlacement] = field(default_factory=list)
    footway_response: float = 0.0
    residual_udl_applied: bool = False

    def describe(self) -> str:
        """Returns the result as a report block."""
        lines = [
            f"{self.response_name}  [{self.adverse}]",
            "-" * 72,
            f"  Design response          = {self.response:14.3f}",
            f"  Before lane reduction    = {self.response_before_reduction:14.3f}",
            f"  Lane reduction (Table 8) = {self.lane_reduction:14.3f}"
            f"   on {self.design_lanes} lanes",
        ]

        if self.footway_response:
            lines.append(f"  Footway load (Cl. 206)   = {self.footway_response:14.3f}")
        if self.residual_udl_applied:
            lines.append("  Residual UDL (Table 6 S.No.1) applied beside the vehicles")

        lines += [
            f"  Arrangement              = {self.lane_pattern}",
            f"  Carriageways read as     = {self.carriageways_read_as}",
            "",
            f"  {'vehicle':<24} {'z (m)':>9} {'x (m)':>10} {'impact':>8}  train",
        ]

        for placed in self.vehicles:
            train = ", ".join(f"{x:.3f}" for x in placed.train_x_front_m)
            lines.append(
                f"  {placed.vehicle_name:<24} {placed.z_centre_m:9.3f} "
                f"{placed.x_front_m:10.3f} {placed.impact_factor:8.4f}"
                f"  {placed.vehicles_in_train} at [{train}]"
            )

        lines.append("-" * 72)
        return "\n".join(lines)
