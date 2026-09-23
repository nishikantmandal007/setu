"""Concrete stiffness per IRC:22-2015: Table III.1 for Ecm, clause 604.3 for the modular ratio."""

import pytest

from setu.models.materials import LONG_TERM, SHORT_TERM, Concrete, Steel

STEEL_KPA = Steel().elastic_modulus_kpa


@pytest.mark.parametrize("grade, ecm_gpa", [(15, 27), (35, 32), (40, 33), (90, 41)])
def test_ecm_comes_from_table_iii_1(grade, ecm_gpa):
    assert Concrete(characteristic_strength_mpa=grade).elastic_modulus_kpa == pytest.approx(ecm_gpa * 1e6)


def test_ecm_between_two_grades_is_interpolated():
    assert Concrete(characteristic_strength_mpa=37.5).elastic_modulus_kpa == pytest.approx(32.5e6)


def test_short_term_modular_ratio_never_below_7_5():
    """M35: Es / Ecm = 200 / 32 = 6.25, so the floor of 7.5 governs."""
    modulus = Concrete(characteristic_strength_mpa=35).modulus_for(SHORT_TERM, STEEL_KPA)

    assert STEEL_KPA / modulus == pytest.approx(7.5)


def test_long_term_modular_ratio_never_below_15():
    """M35: Es / (0.5 Ecm) = 12.5, so the floor of 15 governs."""
    modulus = Concrete(characteristic_strength_mpa=35).modulus_for(LONG_TERM, STEEL_KPA)

    assert STEEL_KPA / modulus == pytest.approx(15.0)


def test_weak_concrete_uses_its_own_ratio():
    """M15: Es / Ecm = 200 / 27 = 7.41 < 7.5 still; long term 200 / 13.5 = 14.8 < 15 - both floors hold."""
    concrete = Concrete(characteristic_strength_mpa=15)

    assert STEEL_KPA / concrete.modulus_for(SHORT_TERM, STEEL_KPA) == pytest.approx(7.5)
    assert STEEL_KPA / concrete.modulus_for(LONG_TERM, STEEL_KPA) == pytest.approx(15.0)


def test_softer_steel_lets_the_real_ratio_govern():
    soft_steel_kpa = 300e6
    concrete = Concrete(characteristic_strength_mpa=35)

    assert soft_steel_kpa / concrete.modulus_for(SHORT_TERM, soft_steel_kpa) == pytest.approx(300 / 32)
    assert soft_steel_kpa / concrete.modulus_for(LONG_TERM, soft_steel_kpa) == pytest.approx(300 / 16)
