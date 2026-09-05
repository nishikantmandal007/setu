"""Reading a deck across its width."""


import pytest

from setu.models.deck import DeckCrossSection
from setu.errors import CrossSectionError


def test_strips_are_laid_out_from_the_left_edge(cross_section):
    first, second = cross_section.strips[0], cross_section.strips[1]

    assert first.z_from_m == 0.0
    assert first.z_to_m == pytest.approx(1.50)
    assert second.z_from_m == pytest.approx(1.50)


def test_a_median_splits_the_traffic_in_two(cross_section):
    carriageways = cross_section.carriageways(split="separate")

    assert len(carriageways) == 2
    assert carriageways[0].width_m() == pytest.approx(4.50)
    assert carriageways[1].left_m > carriageways[0].right_m


def test_combining_reads_the_median_as_carriageway(cross_section):
    """Which is the more onerous reading sometimes, and the less onerous others -
    so setu never picks for you."""
    combined = cross_section.carriageways(split="combined")

    assert len(combined) == 1
    assert combined[0].width_m() == pytest.approx(4.50 + 0.60 + 4.50)


def test_footways_are_found_by_name(cross_section):
    assert [strip.name for strip in cross_section.footways()] == [
        "footpath_left",
        "footpath_right",
    ]


def test_total_width_is_every_strip_added_up(cross_section):
    assert cross_section.total_width_m() == pytest.approx(13.50)


def test_a_deck_with_nowhere_to_drive_is_refused():
    with pytest.raises(CrossSectionError, match="no carriageway"):
        DeckCrossSection.from_widths({"footpath_left": 1.5, "footpath_right": 1.5})


def test_a_negative_width_is_refused():
    with pytest.raises(CrossSectionError, match="negative"):
        DeckCrossSection.from_widths({"carriageway": 7.5, "kerb": -0.5})


def test_an_unknown_split_says_what_it_accepts():
    section = DeckCrossSection.from_widths({"carriageway": 7.5})
    with pytest.raises(CrossSectionError, match="separate.*combined"):
        section.carriageways(split="whatever")
