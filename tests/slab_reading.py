import numpy as np
import openseespy.opensees as ops

ABOUT_THE_TRANSVERSE_AXIS = 5
VERTICAL = 1


# The deck slab's own bending (or, with component=VERTICAL, its vertical shear) across a girder element's end, read straight off
# the solved shells' nodal forces, for checking setu's probed slab operator against: the shells beside the cut give their nodal
# forces at the cut's nodes, and each node goes to its nearest girder (half to each when midway). Read while the case is solved.
def slab_moment_read_off_the_shells(model, element, end="i", component=ABOUT_THE_TRANSVERSE_AXIS):
    girder, station = next(key for key, tag in model.girder_elements.items() if tag == element)
    width_m = np.asarray(model.mesh.width_mesh_m, float)
    girder_m = width_m[[model.mesh.width_station_of_girder(g) for g in range(model.bridge.girders.count)]]
    on_the_cut, sign = ((0, 3), -1.0) if end == "i" else ((1, 2), 1.0)  # shells (i, j): nodes (i,j) (i+1,j) (i+1,j+1) (i,j+1)
    total = 0.0
    for j in range(model.mesh.stations_across_width - 1):
        forces = ops.eleResponse(model.deck_elements[station, j], "forces")
        for local, width_station in zip(on_the_cut, (j, j + 1)):
            distance = np.abs(girder_m - width_m[width_station])
            nearest = np.flatnonzero(np.isclose(distance, distance.min(), rtol=0.0, atol=1e-9))
            if girder in nearest:
                total += sign * forces[6 * local + component] / len(nearest)
    return total
