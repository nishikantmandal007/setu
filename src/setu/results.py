from __future__ import annotations

from dataclasses import dataclass, field

from .irc_code_rules.vehicles import REVERSED_SUFFIX

RULE = "-" * 72


@dataclass(frozen=True)
class VehiclePlacement:
    vehicle_name: str
    z_centre_m: float
    x_front_m: float
    impact_factor: float
    train_x_front_m: tuple[float, ...] = ()

    @property
    def vehicles_in_train(self) -> int:
        return max(len(self.train_x_front_m), 1)

    @property
    def is_facing_backwards(self) -> bool:
        return self.vehicle_name.endswith(REVERSED_SUFFIX)

    def as_a_row(self) -> str:
        where_each_one_sits = ", ".join(f"{x:.3f}" for x in self.train_x_front_m)
        return (
            f"  {self.vehicle_name:<24} {self.z_centre_m:9.3f} "
            f"{self.x_front_m:10.3f} {self.impact_factor:8.4f}"
            f"  {self.vehicles_in_train} at [{where_each_one_sits}]"
        )


@dataclass(frozen=True)
class CriticalPosition:
    response_name: str
    adverse: str
    response: float
    response_before_reduction: float
    lane_reduction: float
    design_lanes: int
    lane_pattern: str
    carriageways_read_as: str
    vehicles: list[VehiclePlacement] = field(default_factory=list)
    footway_response: float = 0.0
    residual_udl_applied: bool = False
    resultant_centred_response: float | None = None

    @property
    def resultant_centred_shortfall(self) -> float | None:
        if self.resultant_centred_response is None or self.response == 0:
            return None

        fallen_short_by = abs(self.response) - abs(self.resultant_centred_response)
        return 100.0 * fallen_short_by / abs(self.response)

    def resultant_centred_line(self) -> str | None:
        if self.resultant_centred_response is None:
            return None

        line = f"  Resultant at mid-width   = {self.resultant_centred_response:14.3f}"
        if self.resultant_centred_shortfall is None:
            return line
        return f"{line}   {self.resultant_centred_shortfall:.1f}% lower"

    def describe(self) -> str:
        lines = [
            f"{self.response_name}  [{self.adverse}]",
            RULE,
            f"  Design response          = {self.response:14.3f}",
            f"  Before lane reduction    = {self.response_before_reduction:14.3f}",
            f"  Lane reduction (Table 8) = {self.lane_reduction:14.3f}"
            f"   on {self.design_lanes} lanes",
        ]

        resultant_line = self.resultant_centred_line()
        if resultant_line is not None:
            lines.append(resultant_line)
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
        lines += [placed.as_a_row() for placed in self.vehicles]
        lines.append(RULE)

        return "\n".join(lines)
