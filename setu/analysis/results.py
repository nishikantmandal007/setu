from setu.utils.constants import RULE


class VehiclePlacement:
    # a vehicle, or a train of them, placed on the deck with its impact factor
    def __init__(self, vehicle_name, z_centre_m, x_front_m, impact_factor, train_x_front_m):
        self.vehicle_name = vehicle_name
        self.z_centre_m = z_centre_m
        self.x_front_m = x_front_m
        self.impact_factor = impact_factor
        self.train_x_front_m = train_x_front_m

    # how many vehicles in the train
    def vehicles_in_train(self):
        return max(len(self.train_x_front_m), 1)

    # one printed row for the vehicle
    def as_a_row(self):
        where = ", ".join(f"{x:.3f}" for x in self.train_x_front_m)
        return (
            f"  {self.vehicle_name:<24} {self.z_centre_m:9.3f} "
            f"{self.x_front_m:10.3f} {self.impact_factor:8.4f}"
            f"  {self.vehicles_in_train()} at [{where}]"
        )


class CriticalPosition:
    # the worst legal traffic for one response: vehicles, lanes, residual UDL and footway strips
    def __init__(self, response_name, adverse, response, response_before_reduction, lane_reduction, design_lanes,
                 lane_pattern, vehicles, footway_response, residual_udl_strips, footway_strips, wearing_course_thickness_m):
        self.response_name = response_name
        self.adverse = adverse
        self.response = response
        self.response_before_reduction = response_before_reduction
        self.lane_reduction = lane_reduction
        self.design_lanes = design_lanes
        self.lane_pattern = lane_pattern
        self.vehicles = vehicles
        self.footway_response = footway_response
        self.residual_udl_strips = residual_udl_strips
        self.footway_strips = footway_strips
        self.wearing_course_thickness_m = wearing_course_thickness_m

    # printed summary of the critical position
    def describe(self):
        lines = [
            f"{self.response_name}  [{self.adverse}]",
            RULE,
            f"  Design response          = {self.response:14.3f}",
            f"  Before lane reduction    = {self.response_before_reduction:14.3f}",
            f"  Lane reduction (Table 8) = {self.lane_reduction:14.3f}"
            f"   on {self.design_lanes} lanes",
        ]
        if self.residual_udl_strips:
            lines.append("  Residual UDL (Table 6 S.No.1) applied beside the vehicles")
        lines += [
            f"  Arrangement              = {self.lane_pattern}",
            "",
            f"  {'vehicle':<24} {'z (m)':>9} {'x (m)':>10} {'impact':>8}  train",
        ]
        lines += [v.as_a_row() for v in self.vehicles]
        lines.append(RULE)
        return "\n".join(lines)
