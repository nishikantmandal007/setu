"""Materials come in from OsdagBridge with E in MPa; the solver gets kN/m2. Modular ratio per IRC:22-2015 clause 604.3."""

import pytest

from setu.models.materials import Concrete, Steel
from setu.utils.constants import LONG_TERM, SHORT_TERM

STEEL = Steel(elastic_modulus_mpa=200000.0, poissons_ratio=0.3, unit_weight_kn_m3=78.5)
STEEL_KPA = STEEL.elastic_modulus_kpa
M35 = Concrete(elastic_modulus_mpa=32000.0, poissons_ratio=0.2, unit_weight_kn_m3=25.0)
M15 = Concrete(elastic_modulus_mpa=27000.0, poissons_ratio=0.2, unit_weight_kn_m3=25.0)


def test_mpa_in_kpa_out():
    assert STEEL_KPA == pytest.approx(2e8)
    assert M35.elastic_modulus_kpa == pytest.approx(3.2e7)
    assert STEEL.shear_modulus_kpa == pytest.approx(2e8 / 2.6)


@pytest.mark.parametrize("cls", [Steel, Concrete])
def test_nothing_is_assumed(cls):
    with pytest.raises(TypeError, match="missing"):
        cls(elastic_modulus_mpa=200000.0)


@pytest.mark.parametrize("cls", [Steel, Concrete])
def test_a_misspelt_key_is_refused(cls):
    with pytest.raises(TypeError, match="unexpected keyword"):
        cls(elastic_modulus_mpa=200000.0, poissons_ratio=0.3, unit_weight_kn_m3=78.5, grade="M35")


def test_short_term_modular_ratio_never_below_7_5():
    """M35: Es / Ecm = 200 / 32 = 6.25, so the floor of 7.5 governs."""
    assert STEEL_KPA / M35.modulus_for(SHORT_TERM, STEEL_KPA) == pytest.approx(7.5)


def test_long_term_modular_ratio_never_below_15():
    """M35: Es / (0.5 Ecm) = 12.5, so the floor of 15 governs."""
    assert STEEL_KPA / M35.modulus_for(LONG_TERM, STEEL_KPA) == pytest.approx(15.0)


def test_weak_concrete_uses_its_own_ratio():
    """M15: Es / Ecm = 200 / 27 = 7.41 < 7.5 still; long term 200 / 13.5 = 14.8 < 15 - both floors hold."""
    assert STEEL_KPA / M15.modulus_for(SHORT_TERM, STEEL_KPA) == pytest.approx(7.5)
    assert STEEL_KPA / M15.modulus_for(LONG_TERM, STEEL_KPA) == pytest.approx(15.0)


def test_softer_steel_lets_the_real_ratio_govern():
    soft_steel_kpa = 300e6

    assert soft_steel_kpa / M35.modulus_for(SHORT_TERM, soft_steel_kpa) == pytest.approx(300 / 32)
    assert soft_steel_kpa / M35.modulus_for(LONG_TERM, soft_steel_kpa) == pytest.approx(300 / 16)
