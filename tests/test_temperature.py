"""Temperature per IRC:6-2017 clause 215.

215.2: metallic structures range from shade max + 15 C down to shade min - 10 C; Table 15 for
restrained structures. 215.3 / Fig. 16b: temperature difference across a composite section -
positive: T1 at the top (18 C at h = 0.2 m, 20.5 C at 0.3 m), 4 C at 0.6h, 0 a further 0.4 m down.
The reverse profile's depths are not given by the code, so the user must give them.
215.4: alpha = 12e-6 / C.

A simply supported span with a free bearing takes no girder force from either effect; what
the girder feels are the self-balancing primary stresses of the difference profile.
"""

import pytest

from setu.builder.assembly import PINNED, ROLLER
from setu.irc6.temperature import effective_temperature_range, temperature_difference_profile
from setu.postprocess.thermal_stresses import free_bearing_movement_m, primary_stresses, primary_thermal_stresses

from test_design_forces import BRIDGE  # noqa: E402


def test_metallic_range():
    """Shade 45 C and 2 C: effective range 60 C down to -8 C."""
    assert effective_temperature_range(45.0, 2.0) == pytest.approx((-8.0, 60.0))


def test_table_15_for_a_restrained_structure():
    """Mean 23.5 C; shade range 43 C > 20 C so +/- 10 C. A 15 C shade range gives +/- 5 C."""
    assert effective_temperature_range(45.0, 2.0, metallic=False) == pytest.approx((13.5, 33.5))
    assert effective_temperature_range(30.0, 15.0, metallic=False) == pytest.approx((17.5, 27.5))


def test_fig_16b_positive_profile():
    """h = 0.25 m: T1 halfway between 18 and 20.5 = 19.25 C; 4 C at 0.15 m; 0 at 0.55 m."""
    assert temperature_difference_profile(0.25) == pytest.approx([(0.0, 19.25), (0.15, 4.0), (0.55, 0.0)])


def test_fig_16b_is_only_drawn_for_0_2_to_0_3_m():
    with pytest.raises(ValueError, match="0.2 to 0.3 m"):
        temperature_difference_profile(0.35)


def test_the_reverse_profile_needs_the_depths_the_code_leaves_out():
    with pytest.raises(ValueError, match="depths"):
        temperature_difference_profile(0.25, positive=False)

    profile = temperature_difference_profile(0.25, positive=False, reverse_depths_m=(0.1, 0.3))
    assert profile == pytest.approx([(0.0, -5.6), (0.1, 0.0), (0.4, -8.0)])


def _rectangle(depth_m, width_m, modulus_kpa, strips=400):
    step_m = depth_m / strips
    return [((k + 0.5) * step_m, width_m * step_m, modulus_kpa) for k in range(strips)]


def test_a_linear_gradient_leaves_no_primary_stress():
    """A plane section stays plane under a linear profile, so a homogeneous section is stress free."""
    layers = _rectangle(1.0, 0.5, 2e8)
    stresses = primary_stresses(layers, [(0.0, 20.0), (1.0, 0.0)])

    assert max(abs(stress) for stress in stresses) < 1e-6


def test_primary_stresses_balance_on_the_section():
    """No net axial force and no net moment: the stresses only fight each other."""
    result = primary_thermal_stresses(BRIDGE, temperature_difference_profile(BRIDGE.deck.thickness_m))
    layers, stresses = result.layers, result.stresses

    net_force = sum(stress * area for (_, area, _), stress in zip(layers, stresses, strict=True))
    centroid_m = sum(depth * area * modulus for depth, area, modulus in layers) / sum(area * modulus for _, area, modulus in layers)
    net_moment = sum(stress * area * (depth - centroid_m) for (depth, area, _), stress in zip(layers, stresses, strict=True))

    assert abs(net_force) < 1e-6 * max(abs(s) for s in stresses)
    assert abs(net_moment) < 1e-6 * max(abs(s) for s in stresses)


def test_a_warm_slab_top_is_squeezed():
    """Heated from above and held by the section: the slab top goes into compression."""
    result = primary_thermal_stresses(BRIDGE, temperature_difference_profile(BRIDGE.deck.thickness_m))

    assert result.slab_top_kpa < 0


def test_the_far_bearing_is_free_so_uniform_temperature_moves_it_without_force():
    """PINNED holds the girder along the span at one end, ROLLER lets it slide at the other."""
    assert PINNED[0] == 1 and ROLLER[0] == 0
    assert free_bearing_movement_m(35.0, (-8.0, 60.0)) == pytest.approx(12e-6 * 35.0 * 68.0)
