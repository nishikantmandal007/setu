import csv
import io

from model import drawing


# each girder's maximum-moment critical position as a static load case: vehicles for reference, wheels as point loads, lane and footway loads as area loads
def critical_loads_csv(bridge, results, girders):
    out = io.StringIO()
    rows = csv.writer(out)
    out.write("# Setu live load at each girder's maximum-moment critical position, for a static check in any finite element program\n"
              "# x along the span from the first bearing, z across from the left deck edge (m); loads act downward\n"
              "# point loads already include impact and lane reduction; area pressures include lane reduction; wheels off the span are left out\n")
    for girder in girders:
        critical, at_m, wheels, patches = drawing.loads_at(bridge, results, girder)
        out.write(f"\n# girder {girder}: Setu composite moment at x = {at_m:.3f} m is {critical.response:.2f} kN·m (IRC:6 live load with impact, lane reduction and footway)\n")
        rows.writerow(["vehicles", "girder", "vehicle", "facing", "train", "front_x_m", "centre_z_m", "impact_factor", "lane_reduction"])
        for placed in critical.vehicles:
            for train, x_m in enumerate(placed.train_x_front_m):
                facing = "reversed" if placed.vehicle_name.endswith("_reversed") else "forward"
                rows.writerow(["vehicle", girder, placed.vehicle_name.removesuffix("_reversed"), facing, train, round(x_m, 4), round(placed.z_centre_m, 4),
                               round(placed.impact_factor, 4), critical.lane_reduction])
        rows.writerow(["point loads", "girder", "vehicle", "train", "x_m", "z_m", "wheel_kn", "impact_factor", "lane_reduction", "load_kn"])
        for w in wheels:
            if w["on_span"]:
                rows.writerow(["point", girder, w["vehicle"], w["train"], round(w["x_m"], 4), round(w["z_m"], 4), round(w["wheel_load_kn"], 4),
                               round(w["impact_factor"], 4), w["lane_reduction"], round(w["applied_kn"], 4)])
        rows.writerow(["area loads", "girder", "kind", "pressure_kpa", "x1_m", "z1_m", "x2_m", "z2_m", "x3_m", "z3_m", "x4_m", "z4_m"])
        for p in patches:
            rows.writerow(["area", girder, p["kind"], round(p["pressure_kpa"], 4), *[round(v, 4) for corner in p["corners_x_z_m"] for v in corner]])
    return out.getvalue()
