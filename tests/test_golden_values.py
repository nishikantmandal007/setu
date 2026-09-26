# The answers setu gives today, pinned so a rewrite cannot quietly move them.
# Nothing else in the suite asserts an actual number - the other tests check
# relations, or race the searches against brute-force oracles - so without this
# file a behaviour change during a refactor would sail through green.


from dataclasses import dataclass, field

import numpy as np
import pytest

from setu.models.deck import DeckCrossSection
from setu.analysis.influence_surface import InfluenceSurface
from setu.analysis.critical_position import rank_all_positions

SPAN_M = 35.0
WIDTH_M = 13.5


def transverse_variation(width_mesh_m: np.ndarray) -> np.ndarray:
    # A gentle rise towards mid-width, so which lane a vehicle takes matters.
    return 1.0 + 0.35 * np.cos(np.pi * (width_mesh_m - WIDTH_M / 2) / WIDTH_M)


def sagging_surface() -> InfluenceSurface:
    # Midspan moment on a simply supported deck: one sign everywhere.
    length_mesh_m = np.round(np.linspace(0.0, SPAN_M, 71), 9)
    width_mesh_m = np.round(np.linspace(0.0, WIDTH_M, 41), 9)
    at_midspan = SPAN_M / 2

    along = np.where(
        length_mesh_m <= at_midspan,
        length_mesh_m * (SPAN_M - at_midspan) / SPAN_M,
        at_midspan * (SPAN_M - length_mesh_m) / SPAN_M,
    )
    return InfluenceSurface(
        values=along[:, None] * transverse_variation(width_mesh_m)[None, :],
        length_mesh_m=length_mesh_m,
        width_mesh_m=width_mesh_m,
        name="midspan sagging moment",
        skew=0.0,
    )


def hogging_surface() -> InfluenceSurface:
    # Hogging over the pier of a two-span deck, adverse in both spans - the
    # shape where a train of vehicles genuinely governs.
    length_mesh_m = np.round(np.linspace(0.0, 2 * SPAN_M, 141), 9)
    width_mesh_m = np.round(np.linspace(0.0, WIDTH_M, 41), 9)

    into_the_span = np.where(
        length_mesh_m <= SPAN_M,
        length_mesh_m / SPAN_M,
        (2 * SPAN_M - length_mesh_m) / SPAN_M,
    )
    along = -0.25 * SPAN_M * into_the_span * (1 - into_the_span) * (1 + into_the_span)

    return InfluenceSurface(
        values=along[:, None] * transverse_variation(width_mesh_m)[None, :],
        length_mesh_m=length_mesh_m,
        width_mesh_m=width_mesh_m,
        name="hogging moment over the pier",
        skew=0.0,
    )


DUAL_CARRIAGEWAY = DeckCrossSection.from_widths(
    {
        "footpath_left": 1.50,
        "kerb_left": 0.45,
        "carriageway_1": 4.50,
        "median": 0.60,
        "carriageway_2": 4.50,
        "kerb_right": 0.45,
        "footpath_right": 1.50,
    }
)

NARROW_CARRIAGEWAY = DeckCrossSection.from_widths(
    {"kerb_left": 0.50, "carriageway": 4.60, "kerb_right": 0.50}
)

WIDE_CARRIAGEWAY = DeckCrossSection.from_widths(
    {"kerb_left": 0.45, "carriageway": 13.10, "kerb_right": 0.45}
)


@dataclass(frozen=True)
class GoldenAnswer:
    name: str
    surface: InfluenceSurface
    cross_section: DeckCrossSection
    span_m: float
    adverse: str
    cases: int
    response: float
    response_before_reduction: float
    lane_reduction: float
    design_lanes: int
    lane_pattern: str
    footway_response: float
    residual_udl_applied: bool
    total_over_all_cases: float
    vehicles: list[tuple[str, float, float, tuple[float, ...]]] = field(default_factory=list)


# The full IRC:6 live load - vehicles, residual UDL and footway load - checked equal to the pre-cleanup
# search run with its default switches, number for number, before the switches were removed.
GOLDEN_ANSWERS = [
    GoldenAnswer(
        name='two class a vehicles on a dual carriageway, sagging, with the clause 206.3 footway load',
        surface=sagging_surface(),
        cross_section=DUAL_CARRIAGEWAY,
        span_m=SPAN_M,
        adverse='maximum',
        cases=1,
        response=15968.07892919936,
        response_before_reduction=15968.07892919936,
        lane_reduction=1.0,
        design_lanes=2,
        lane_pattern='class_a | class_a',
        footway_response=1324.4475417088515,
        residual_udl_applied=True,
        total_over_all_cases=15968.07892919936,
        vehicles=[
            ('Class_A_reversed', 5.15, 4.2, (4.2,)),
            ('Class_A', 8.35, 12.0, (12.0,)),
        ],
    ),
    GoldenAnswer(
        # A follower exactly one pitch (38.8 m) behind each breakpoint is what makes the train worst here.
        name='a train of two in each lane, hogging over the pier',
        surface=hogging_surface(),
        cross_section=DUAL_CARRIAGEWAY,
        span_m=2 * SPAN_M,
        adverse='minimum',
        cases=1,
        response=-14342.843527917632,
        response_before_reduction=-14342.843527917632,
        lane_reduction=1.0,
        design_lanes=2,
        lane_pattern='class_a | class_a',
        footway_response=-996.5457626734934,
        residual_udl_applied=True,
        total_over_all_cases=-14342.843527917632,
        vehicles=[
            ('Class_A', 5.15, 6.5, (6.5, 45.3)),
            ('Class_A', 8.35, 6.5, (6.5, 45.3)),
        ],
    ),
    GoldenAnswer(
        name='a narrow carriageway carrying the table 6 residual udl',
        surface=sagging_surface(),
        cross_section=NARROW_CARRIAGEWAY,
        span_m=SPAN_M,
        adverse='maximum',
        cases=1,
        response=7036.801253437773,
        response_before_reduction=7036.801253437773,
        lane_reduction=1.0,
        design_lanes=1,
        lane_pattern='class_a',
        footway_response=0.0,
        residual_udl_applied=True,
        total_over_all_cases=7036.801253437773,
        vehicles=[
            ('Class_A', 3.8, 12.0, (12.0,)),
        ],
    ),
    GoldenAnswer(
        name='four class a lanes on a wide carriageway, as table 6a draws them',
        surface=sagging_surface(),
        cross_section=WIDE_CARRIAGEWAY,
        span_m=SPAN_M,
        adverse='maximum',
        cases=7,
        response=15597.548983659555,
        response_before_reduction=19496.936229574443,
        lane_reduction=0.8,
        design_lanes=4,
        lane_pattern='class_a + class_a + class_a + class_a',
        footway_response=0.0,
        residual_udl_applied=False,
        total_over_all_cases=85439.35756627322,
        vehicles=[
            ('Class_A', 1.75, 12.0, (12.0,)),
            ('Class_A_reversed', 5.25, 4.2, (4.2,)),
            ('Class_A', 8.75, 12.0, (12.0,)),
            ('Class_A', 12.25, 12.0, (12.0,)),
        ],
    ),
]


@pytest.fixture(scope="module", params=GOLDEN_ANSWERS, ids=lambda golden: golden.name)
def golden_and_ranked(request):
    golden = request.param
    return golden, rank_all_positions(golden.surface, golden.cross_section, golden.span_m, golden.adverse, 0.0)


def test_the_governing_response_has_not_moved(golden_and_ranked):
    golden, ranked = golden_and_ranked
    worst = ranked[0]

    assert worst.response == pytest.approx(golden.response, rel=1e-12)
    assert worst.response_before_reduction == pytest.approx(golden.response_before_reduction, rel=1e-12)
    assert worst.lane_reduction == pytest.approx(golden.lane_reduction, rel=1e-12)


def test_the_governing_arrangement_has_not_moved(golden_and_ranked):
    golden, ranked = golden_and_ranked
    worst = ranked[0]

    assert len(ranked) == golden.cases
    assert worst.lane_pattern == golden.lane_pattern
    assert worst.design_lanes == golden.design_lanes
    assert bool(worst.residual_udl_strips) is golden.residual_udl_applied


def test_the_footway_load_has_not_moved(golden_and_ranked):
    golden, ranked = golden_and_ranked

    assert ranked[0].footway_response == pytest.approx(golden.footway_response, rel=1e-12)


def test_every_vehicle_stands_where_it_stood(golden_and_ranked):
    golden, ranked = golden_and_ranked
    placed_vehicles = ranked[0].vehicles

    assert len(placed_vehicles) == len(golden.vehicles)
    for placed, (name, z_centre_m, x_front_m, train_x_front_m) in zip(placed_vehicles, golden.vehicles, strict=True):
        assert placed.vehicle_name == name
        assert placed.z_centre_m == pytest.approx(z_centre_m, abs=1e-9)
        assert placed.x_front_m == pytest.approx(x_front_m, abs=1e-9)
        assert placed.train_x_front_m == pytest.approx(train_x_front_m, abs=1e-9)


def test_the_losing_cases_have_not_moved_either(golden_and_ranked):
    # Ranking every case, not just the winner, is what catches a change that
    # only shows up in an arrangement the sweep happened to reject.
    golden, ranked = golden_and_ranked

    assert sum(case.response for case in ranked) == pytest.approx(golden.total_over_all_cases, rel=1e-12)


def test_the_report_block_still_reads(golden_and_ranked):
    golden, ranked = golden_and_ranked

    report = ranked[0].describe()

    assert golden.lane_pattern in report
    assert f"{golden.response:14.3f}" in report
