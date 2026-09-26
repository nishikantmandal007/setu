"""Temperature per IRC:6-2017 clause 215.

215.2: metallic structures range from shade max + 15 C down to shade min - 10 C.
215.3 / Fig. 17b / Table 15B (the same as EN 1991-1-5 Fig. 6.2b) across a composite deck, h1 = 0.6h and h2 = 0.4 m:
heating dT1 at the top, +4 C at h1, 0 at h1 + h2; cooling dT1 at the top, 0 at h1, -8 C at h1 + h2.
dT1 comes from Table 15B by slab depth (0.2-0.3 m) and surfacing (50-100 mm).
215.4: alpha = 12e-6 / C. IRC:22 clause 603.2.1 sets the slab width each girder works with.

A simply supported span with a free bearing takes no girder force from either effect; what
the girder feels are the self-balancing primary stresses of the difference profile.
"""

import pytest

from setu.builder.assembly import PINNED, ROLLER
from setu.irc6.temperature import COOLING, HEATING, effective_temperature_range, temperature_difference_profiles
from setu.models.bridge import BridgeInput
from setu.postprocess.thermal_stresses import effective_slab_width_m, free_bearing_movement_m, primary_stresses, primary_thermal_stresses

from test_design_forces import BRIDGE  # noqa: E402


def test_metallic_range():
    """Shade 45 C and 2 C: effective range 60 C down to -8 C."""
    assert effective_temperature_range(45.0, 2.0) == pytest.approx((-8.0, 60.0))


def test_fig_17b_heating_and_cooling_with_50_mm_surfacing():
    """h = 0.25 m: dT1 halfway between 18 and 20.5 heating, -4.4 and -6.8 cooling; h1 = 0.15 m, h1 + h2 = 0.55 m."""
    profiles = temperature_difference_profiles(0.25, 0.05)

    assert profiles[HEATING] == pytest.approx([(0.0, 19.25), (0.15, 4.0), (0.55, 0.0)])
    assert profiles[COOLING] == pytest.approx([(0.0, -5.6), (0.15, 0.0), (0.55, -8.0)])


@pytest.mark.parametrize("slab_m, surfacing_m, heating_c, cooling_c", [
    (0.2, 0.05, 18.0, -4.4), (0.2, 0.10, 13.0, -3.5), (0.3, 0.05, 20.5, -6.8), (0.3, 0.10, 16.0, -5.0),
    (0.2, 0.075, 15.5, -3.95),
])
def test_table_15b_is_read_by_slab_depth_and_surfacing(slab_m, surfacing_m, heating_c, cooling_c):
    profiles = temperature_difference_profiles(slab_m, surfacing_m)

    assert profiles[HEATING][0][1] == pytest.approx(heating_c)
    assert profiles[COOLING][0][1] == pytest.approx(cooling_c)


@pytest.mark.parametrize("slab_m, surfacing_m, what", [(0.35, 0.05, "slab depth"), (0.25, 0.12, "surfacing thickness")])
def test_table_15b_is_not_extrapolated(slab_m, surfacing_m, what):
    with pytest.raises(ValueError, match=what):
        temperature_difference_profiles(slab_m, surfacing_m)


def test_irc_22_effective_width_inner_and_outer():
    """35 m span, 2.75 m spacing, 1.25 m overhang: inner min(8.75, 2.75); outer min(4.375, 1.375) + min(1.25, 4.375)."""
    assert effective_slab_width_m(BRIDGE, 2) == pytest.approx(2.75)
    assert effective_slab_width_m(BRIDGE, 0) == pytest.approx(1.375 + 1.25)
    assert effective_slab_width_m(BRIDGE, 4) == effective_slab_width_m(BRIDGE, 0)


def test_on_a_short_span_the_quarter_span_limit_governs():
    """8 m span: L/4 = 2.0 m < 2.75 m spacing, and L/8 = 1.0 m caps both parts of the outer width."""
    short = BridgeInput(**{**BRIDGE.__dict__, "span_m": 8.0})

    assert effective_slab_width_m(short, 2) == pytest.approx(2.0)
    assert effective_slab_width_m(short, 0) == pytest.approx(1.0 + 1.0)


def _rectangle(depth_m, width_m, modulus_kpa, strips=400):
    step_m = depth_m / strips
    return [((k + 0.5) * step_m, width_m * step_m, modulus_kpa) for k in range(strips)]


def test_a_linear_gradient_leaves_no_primary_stress():
    """A plane section stays plane under a linear profile, so a homogeneous section is stress free."""
    layers = _rectangle(1.0, 0.5, 2e8)
    stresses = primary_stresses(layers, [(0.0, 20.0), (1.0, 0.0)])

    assert max(abs(stress) for stress in stresses) < 1e-6


@pytest.mark.parametrize("kind", [HEATING, COOLING])
@pytest.mark.parametrize("girder", [0, 2])
def test_primary_stresses_balance_on_the_section(kind, girder):
    """No net axial force and no net moment: the stresses only fight each other."""
    result = primary_thermal_stresses(BRIDGE, girder, temperature_difference_profiles(BRIDGE.deck.thickness_m, 0.05)[kind])
    layers, stresses = result.layers, result.stresses

    net_force = sum(stress * area for (_, area, _), stress in zip(layers, stresses, strict=True))
    centroid_m = sum(depth * area * modulus for depth, area, modulus in layers) / sum(area * modulus for _, area, modulus in layers)
    net_moment = sum(stress * area * (depth - centroid_m) for (depth, area, _), stress in zip(layers, stresses, strict=True))

    assert abs(net_force) < 1e-6 * max(abs(s) for s in stresses)
    assert abs(net_moment) < 1e-6 * max(abs(s) for s in stresses)


def test_a_warm_slab_top_is_squeezed_and_a_cold_one_pulled():
    """Heated from above and held by the section the slab top goes into compression; cooled, into tension."""
    profiles = temperature_difference_profiles(BRIDGE.deck.thickness_m, 0.05)

    assert primary_thermal_stresses(BRIDGE, 2, profiles[HEATING]).slab_top_kpa < 0
    assert primary_thermal_stresses(BRIDGE, 2, profiles[COOLING]).slab_top_kpa > 0


def test_the_far_bearing_is_free_so_uniform_temperature_moves_it_without_force():
    """PINNED holds the girder along the span at one end, ROLLER lets it slide at the other; the bearing spring takes the vertical."""
    assert PINNED[0] == 1 and ROLLER[0] == 0
    assert PINNED[1] == ROLLER[1] == 0
    assert free_bearing_movement_m(35.0, (-8.0, 60.0)) == pytest.approx(12e-6 * 35.0 * 68.0)
