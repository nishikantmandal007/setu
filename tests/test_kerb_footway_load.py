"""IRC:6-2017 clause 206.2 (Amendment 10 S.No. 43): kerbs 0.75 m or wider carry the footway live load; narrower kerbs carry none."""

import pytest

from setu.irc6.lanes import footway_loaded_strips, footway_pressure_kpa
from setu.models.deck import DeckCrossSection


def deck(kerb_m):
    return DeckCrossSection.from_widths({"footpath_left": 1.5, "kerb_left": kerb_m, "carriageway_1": 7.5, "kerb_right": kerb_m, "footpath_right": 1.5})


@pytest.mark.parametrize("kerb_m, loaded", [(0.45, False), (0.6, False), (0.74, False), (0.75, True), (1.0, True)])
def test_a_kerb_carries_footway_load_from_0_75_m(kerb_m, loaded):
    strips = footway_loaded_strips(deck(kerb_m), 35.0)
    kerb_strips = [s for s in strips if abs((s[1] - s[0]) - kerb_m) < 1e-9 and kerb_m != 1.5]
    assert (len(kerb_strips) == 2) == loaded


def test_a_wide_kerb_takes_the_206_3_pressure_for_its_own_width():
    strips = footway_loaded_strips(deck(1.0), 35.0)
    assert [round(to - frm, 6) for frm, to, _ in strips] == [1.5, 1.0, 1.0, 1.5]
    assert strips[1][2] == pytest.approx(footway_pressure_kpa(35.0, 1.0))
