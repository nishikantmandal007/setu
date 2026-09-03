RULE = "-" * 72
REVERSED_SUFFIX = "_reversed"

class VehiclePlacement:
    def __init__(self, vehicle_name, z_centre_m, x_front_m, impact_factor, train_x_front_m=()):
        self.vehicle_name = vehicle_name
        self.z_centre_m = z_centre_m
        self.x_front_m = x_front_m
        self.impact_factor = impact_factor
        self.train_x_front_m = train_x_front_m

    def vehicles_in_train(self):
        return max(len(self.train_x_front_m), 1)

    def is_facing_backwards(self):
        return self.vehicle_name.endswith(REVERSED_SUFFIX)

    def as_a_row(self):
        where = ", ".join(f"{x:.3f}" for x in self.train_x_front_m)
        return (
            f"  {self.vehicle_name:<24} {self.z_centre_m:9.3f} "
            f"{self.x_front_m:10.3f} {self.impact_factor:8.4f}"
            f"  {self.vehicles_in_train()} at [{where}]"
        )

    def to_dict(self):
        return self.__dict__

class CriticalPosition:
    def __init__(self, response_name, adverse, response, response_before_reduction,
                 lane_reduction, design_lanes, lane_pattern, carriageways_read_as,
                 vehicles=None, footway_response=0.0, residual_udl_applied=False,
                 resultant_centred_response=None):
        self.response_name = response_name
        self.adverse = adverse
        self.response = response
        self.response_before_reduction = response_before_reduction
        self.lane_reduction = lane_reduction
        self.design_lanes = design_lanes
        self.lane_pattern = lane_pattern
        self.carriageways_read_as = carriageways_read_as
        self.vehicles = vehicles or []
        self.footway_response = footway_response
        self.residual_udl_applied = residual_udl_applied
        self.resultant_centred_response = resultant_centred_response

    def resultant_centred_shortfall(self):

        if self.resultant_centred_response is None or self.response == 0:
            return None
        return 100.0 * (abs(self.response) - abs(self.resultant_centred_response)) / abs(self.response)

    def resultant_centred_line(self):
        if self.resultant_centred_response is None:
            return None
        line = f"  Resultant at mid-width   = {self.resultant_centred_response:14.3f}"
        shortfall = self.resultant_centred_shortfall()
        if shortfall is None:
            return line
        return f"{line}   {shortfall:.1f}% lower"

    def describe(self):
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
        if self.residual_udl_applied:
            lines.append("  Residual UDL (Table 6 S.No.1) applied beside the vehicles")
        lines += [
            f"  Arrangement              = {self.lane_pattern}",
            f"  Carriageways read as     = {self.carriageways_read_as}",
            "",
            f"  {'vehicle':<24} {'z (m)':>9} {'x (m)':>10} {'impact':>8}  train",
        ]
        lines += [v.as_a_row() for v in self.vehicles]
        lines.append(RULE)
        return "\n".join(lines)

    def to_dict(self):
        return self.__dict__
