from contextlib import contextmanager
from importlib import import_module

import numpy as np

from setu.errors import BackendError, OtherLoadsStillActiveError
from setu.utils.constants import LOAD_CASE_PATTERN_BASE

# the one place that imports and calls OpenSees
try:
    opensees = import_module("openseespy.opensees")  # a compiled module: imported by name so type checkers do not judge its commands against an empty stub
except ImportError as missing:
    raise BackendError("openseespy is not installed") from missing


analysis_configured = False


# start a new 3-D model with six DOFs per node
def start_model():
    global analysis_configured
    analysis_configured = False
    opensees.wipe()
    opensees.model('basic', '-ndm', 3, '-ndf', 6)


# add one node at its coordinates
def add_node(tag, x, y, z):
    opensees.node(tag, x, y, z)


# fix the selected node DOFs
def fix_node(node, *dofs):
    opensees.fix(node, *dofs)


# elastic uniaxial material for trusses and springs
def elastic_material(tag, stiffness):
    opensees.uniaxialMaterial('Elastic', tag, stiffness)


# elastic membrane and plate section for the slab
def shell_section(tag, modulus, poissons_ratio, thickness):
    opensees.section('ElasticMembranePlateSection', tag, modulus, poissons_ratio, thickness)


# four-node slab shell
def add_shell(tag, node_i, node_j, node_k, node_l, section):
    opensees.element('ShellMITC4', tag, node_i, node_j, node_k, node_l, section)


# linear beam transform with its local axis
def linear_transform(tag, *axis):
    opensees.geomTransf('Linear', tag, *axis)


# elastic girder beam in its local axes
def add_beam(tag, start, end, area, modulus, shear_modulus, torsion, weak_inertia, strong_inertia, transform):
    opensees.element('elasticBeamColumn', tag, start, end, area, modulus, shear_modulus, torsion, weak_inertia, strong_inertia, transform)


# axial brace member
def add_truss(tag, start, end, area, material):
    opensees.element('truss', tag, start, end, area, material)


# spring between coincident nodes in one DOF
def add_spring(tag, start, end, material, dof):
    opensees.element('zeroLength', tag, start, end, '-mat', material, '-dir', dof)


# internal link in the supplied orientation
def add_link(tag, start, end, material, dof, *orientation):
    opensees.element('twoNodeLink', tag, start, end, '-mat', material, '-dir', dof, '-orient', *orientation)


# rigid beam link from master to child
def rigid_beam(master, child):
    opensees.rigidLink('beam', master, child)


# tie selected DOFs to their master
def equal_dofs(master, child, *dofs):
    opensees.equalDOF(master, child, *dofs)


# tags of every node in the domain
def node_tags():
    return opensees.getNodeTags()


# tags of every element in the domain
def element_tags():
    return opensees.getEleTags()


# coordinates of one node
def node_coordinates(node):
    return opensees.nodeCoord(node)


# end nodes of one element
def element_nodes(element):
    return tuple(opensees.eleNodes(element))


# active load pattern tags
def load_patterns():
    return opensees.getPatterns()


# put nodal and element loads on one pattern
def apply_loads(nodal_loads, element_loads=(), pattern=LOAD_CASE_PATTERN_BASE, *, time_series="Constant"):
    opensees.timeSeries(time_series, pattern)
    opensees.pattern("Plain", pattern, pattern)
    for node, fx, fy, fz, mx, my, mz in nodal_loads:
        opensees.load(node, fx, fy, fz, mx, my, mz)
    for element, load_type, parameters in element_loads:
        opensees.eleLoad("-ele", element, "-type", load_type, *parameters)


# remove both parts of one load case
def remove_loads(pattern):
    opensees.remove("loadPattern", pattern)
    opensees.remove("timeSeries", pattern)


# reset displacements and the load clock
def reset():
    opensees.reset()
    opensees.setTime(0.0)


# one linear static step, stiffness factored once
def configure_linear_static():
    opensees.wipeAnalysis()
    opensees.system("SparseGeneral")  # SuperLU honours -factorOnce; UmfPack refactors every solve before OpenSees c440269c, SparseSYM's destructor segfaults if never sized
    opensees.numberer("RCM")
    opensees.constraints("Transformation")
    opensees.integrator("LoadControl", 1.0)
    opensees.algorithm("Linear", "-factorOnce")
    opensees.analysis("Static")


# one solver step, kept separate so failure tests can replace it
def analyze():
    return opensees.analyze(1)


# solve one case and keep its loads active until its results have been read
@contextmanager
def solved(nodal_loads, element_loads=(), pattern=LOAD_CASE_PATTERN_BASE, *, time_series="Constant"):
    global analysis_configured
    already_loading = load_patterns()
    if already_loading:
        raise OtherLoadsStillActiveError(f"load patterns {already_loading} are still on the model. Remove them, or combine them into this load case, first.")
    reset()
    try:
        apply_loads(nodal_loads, element_loads, pattern, time_series=time_series)
        if not analysis_configured:
            configure_linear_static()
            analysis_configured = True
        elif element_loads:
            # Element loads resize the system; discard its old factors and form the tangent again.
            opensees.system("SparseGeneral")
            opensees.algorithm("Linear", "-factorOnce")
        status = analyze()
        if status != 0:
            raise BackendError(f"analysis failed with OpenSees status {status}")
        yield
    except Exception:
        analysis_configured = False
        reset()
        raise
    finally:
        remove_loads(pattern)


# local element end forces
def element_local_forces(element):
    return opensees.eleResponse(element, "localForce")


# element end forces in global axes
def element_forces(element):
    return opensees.eleResponse(element, "force")


# truss axial force, tension positive
def truss_axial_force(element):
    return float(opensees.eleResponse(element, "axialForce")[0])


# displacement of one node in one DOF
def node_displacement(node, dof):
    return opensees.nodeDisp(node, dof)


# all six displacements of one node
def node_displacements(node):
    return opensees.nodeDisp(node)


# every node tag in increasing order, and the six displacements of each in the same order
def every_node_displacement():
    nodes = np.sort(np.array(node_tags(), int))
    return nodes, np.array([node_displacements(int(node)) for node in nodes], float)


# calculate nodal reactions while the loads are active
def calculate_reactions():
    opensees.reactions()


# reaction of one node in one DOF
def node_reaction(node, dof):
    return opensees.nodeReaction(node, dof)


# all six reactions of one node
def node_reactions(node):
    return opensees.nodeReaction(node)


# nodes with fixed DOFs
def fixed_nodes():
    return opensees.getFixedNodes()


# fixed DOFs of one node
def fixed_dofs(node):
    return opensees.getFixedDOFs(node)


# children constrained to one master
def constrained_nodes(master):
    return opensees.getConstrainedNodes(master)


# child DOFs constrained to one master
def constrained_dofs(child, master):
    return opensees.getConstrainedDOFs(child, master)


# solver element type for model inspection
def element_type(element):
    return opensees.eleType(element)


# basic element forces for internal link checks
def element_basic_forces(element):
    return opensees.eleResponse(element, "basicForce")


# send solver output to the chosen file without echoing it
def log_file(path):
    opensees.logFile(path, "-noEcho")


class OpenSeesBackend:

    ADJOINT_PATTERN = 7

    # adapt the influence solver's paired loads to the shared solve context
    def solved(self, loads, pattern=ADJOINT_PATTERN):
        return solved(((node, *forces) for node, forces in loads), pattern=pattern, time_series="Linear")

    node_displacement = staticmethod(node_displacement)
    element_nodes = staticmethod(element_nodes)
    node_coordinates = staticmethod(node_coordinates)
    every_node_displacement = staticmethod(every_node_displacement)
