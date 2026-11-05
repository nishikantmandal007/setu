import numpy as np
from scipy import sparse

from setu.solver import backend
from setu.utils.constants import END_I_FORCE_TO_INTERNAL_FORCE

DOFS_PER_NODE = 6
ABOUT_THE_TRANSVERSE_AXIS = 5  # rotation about z, across the deck: the axis the girders bend about
# a deck shell's nodes run (i, j) (i+1, j) (i+1, j+1) (i, j+1): two lie on the station it starts at, two on the one it ends at
ON_ITS_START = (0, 3)
ON_ITS_END = (1, 2)
SAME_SHAPE_DECIMALS = 9


# Each girder's share of the deck slab's own bending across a station, in kN m with the girders' sign, as linear rows on the
# displacements of every node. The slab carries part of the bridge's moment by bending about its own mid-plane; with the
# girders' steel moment and axial couple it makes up the composite section's whole moment (IRC:22 checks the composite
# section). The shells beside the cut give their nodal moments about the transverse axis there, and each node on the cut
# belongs to the nearest girder (half to each when it is midway), so the girders' shares add up to the whole slab's bending.
class SlabMoments:
    def __init__(self, model):
        mesh = model.mesh
        self.model = model
        self.girders = model.bridge.girders.count
        self.stations = mesh.stations_along_span
        self.node_tags = np.sort(np.array(backend.node_tags(), int))
        width_m = np.asarray(mesh.width_mesh_m, float)
        girder_m = width_m[[mesh.width_station_of_girder(g) for g in range(self.girders)]]
        distance = np.abs(width_m[:, None] - girder_m[None, :])
        nearest = np.isclose(distance, distance.min(axis=1, keepdims=True), rtol=0.0, atol=10.0 ** -SAME_SHAPE_DECIMALS)
        self.share = nearest / nearest.sum(axis=1, keepdims=True)  # width station x girder
        self.stiffness_by_shape = {}
        last = self.stations - 1
        self.operator = sparse.vstack([self.cut_rows(station, at_start=station < last) for station in range(self.stations)]).tocsr()
        # rows ordered station by station, a row per girder within each: girder g at station s is row s * girders + g

    # the rows (one per girder) of the slab's bending across a station, read from the shells starting at it or from those ending at it
    def cut_rows(self, station, *, at_start):
        row_of_shells = station if at_start else station - 1
        on_the_cut = ON_ITS_START if at_start else ON_ITS_END
        sign = END_I_FORCE_TO_INTERNAL_FORCE if at_start else 1.0
        rows, columns, values = [], [], []
        for j in range(self.model.mesh.stations_across_width - 1):
            element = self.model.deck_elements[row_of_shells, j]
            nodes = backend.element_nodes(element)
            stiffness = self.stiffness_of(element, nodes)
            columns_of_element = (np.searchsorted(self.node_tags, nodes)[:, None] * DOFS_PER_NODE + np.arange(DOFS_PER_NODE)).ravel()
            for local, width_station in zip(on_the_cut, (j, j + 1)):
                moment_row = sign * stiffness[DOFS_PER_NODE * local + ABOUT_THE_TRANSVERSE_AXIS]
                for girder in np.flatnonzero(self.share[width_station]):
                    rows.append(np.full(columns_of_element.size, girder))
                    columns.append(columns_of_element)
                    values.append(self.share[width_station, girder] * moment_row)
        return sparse.csr_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(columns))),
                                 shape=(self.girders, self.node_tags.size * DOFS_PER_NODE))

    # a shell's stiffness, probed once for each shape of shell
    def stiffness_of(self, element, nodes):
        corners = np.array([backend.node_coordinates(node) for node in nodes], float)
        shape = tuple(np.round(corners - corners[0], SAME_SHAPE_DECIMALS).ravel())
        if shape not in self.stiffness_by_shape:
            self.stiffness_by_shape[shape] = backend.element_stiffness_by_probing(element, nodes)
        return self.stiffness_by_shape[shape]

    # every girder's slab bending at every station (girders x stations), from every node's displacements in node tag order
    def from_displacements(self, displacements):
        return (self.operator @ np.asarray(displacements, float).ravel()).reshape(self.stations, self.girders).T

    # the nodal loads whose deflections are the influence surface of one girder's slab bending at a girder element's end
    def adjoint_loads(self, girder, element_station, end):
        last = self.stations - 1
        if end == "i":
            row = self.operator[element_station * self.girders + girder] if element_station < last else self.cut_rows(element_station, at_start=True)[girder]
        elif element_station + 1 == last:
            row = self.operator[last * self.girders + girder]
        else:
            row = self.cut_rows(element_station + 1, at_start=False)[girder]
        row = row.tocoo()
        loads = {}
        for column, value in zip(row.col, row.data):
            node = int(self.node_tags[column // DOFS_PER_NODE])
            loads.setdefault(node, np.zeros(DOFS_PER_NODE))[column % DOFS_PER_NODE] += value
        return loads
