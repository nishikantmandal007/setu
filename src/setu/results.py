# What setu hands back: which arrangement of lanes governed, which vehicle sat in each
# one, which way it was facing, where along the span it stopped, how many of them were in
# the lane, what impact factor each one attracted, and what reduction was applied at the
# end. Every number in a report traces back to one of these fields.

from __future__ import annotations

from dataclasses import dataclass, field

from .irc_code_rules.vehicles import REVERSED_SUFFIX


@dataclass(frozen=True)
class VehiclePlacement:
    # One vehicle, where it ended up, and what it attracted.
    vehicle_name: str

    # The vehicle's centreline across the deck.
    z_centre_m: float

    # The front of the leading vehicle along the span.
    x_front_m: float

    impact_factor: float

    # Where the front of every vehicle in this lane sits, leading vehicle first. A lane
    # may carry several vehicles nose to tail and all of them are part of the load case,
    # so the placement can be rebuilt in any other program from this field alone.
    train_x_front_m: tuple[float, ...] = ()

    @property
    def vehicles_in_train(self) -> int:
        return max(len(self.train_x_front_m), 1)

    @property
    def is_facing_backwards(self) -> bool:
        return self.vehicle_name.endswith(REVERSED_SUFFIX)


@dataclass(frozen=True)
class CriticalPosition:
    # The worst legal load the deck has to carry, for one response quantity.
    response_name: str

    # 'maximum' or 'minimum' - which direction is the damaging one.
    adverse: str

    # What the deck actually has to be designed for.
    response: float

    # The same number before Table 8's lane reduction, kept visible so a report can show
    # what each part of the code contributed.
    response_before_reduction: float

    lane_reduction: float
    design_lanes: int

    # The arrangement that governed, written out, e.g. 'zone_70r + class_a'.
    lane_pattern: str

    carriageways_read_as: str
    vehicles: list[VehiclePlacement] = field(default_factory=list)
    footway_response: float = 0.0
    residual_udl_applied: bool = False

    # What the same vehicles cause with their resultant on the carriageway centreline -
    # the second transverse condition the code asks for. This can never govern: it is a
    # single position inside the set the sweep already searches. So it is reported beside
    # the answer rather than competing with it.
    resultant_centred_response: float | None = None

    @property
    def resultant_centred_shortfall(self) -> float | None:
        # How much lower the resultant-centred position is, as a percentage.
        if self.resultant_centred_response is None or self.response == 0:
            return None
        return 100.0 * (abs(self.response) - abs(self.resultant_centred_response)) / abs(
            self.response
        )

    def describe(self) -> str:
        lines = [
            f"{self.response_name}  [{self.adverse}]",
            "-" * 72,
            f"  Design response          = {self.response:14.3f}",
            f"  Before lane reduction    = {self.response_before_reduction:14.3f}",
            f"  Lane reduction (Table 8) = {self.lane_reduction:14.3f}"
            f"   on {self.design_lanes} lanes",
        ]

        if self.resultant_centred_response is not None:
            lines.append(
                f"  Resultant at mid-width   = {self.resultant_centred_response:14.3f}"
                f"   {self.resultant_centred_shortfall:.1f}% lower"
            )
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
            train_x_front_m = ", ".join(f"{x:.3f}" for x in placed.train_x_front_m)
            lines.append(
                f"  {placed.vehicle_name:<24} {placed.z_centre_m:9.3f} "
                f"{placed.x_front_m:10.3f} {placed.impact_factor:8.4f}"
                f"  {placed.vehicles_in_train} at [{train_x_front_m}]"
            )

        lines.append("-" * 72)
        return "\n".join(lines)
