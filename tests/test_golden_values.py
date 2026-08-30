from src.services.critical_position import CriticalPositionService
# The answers setu gives today, pinned so a rewrite cannot quietly move them.
# Nothing else in the suite asserts an actual number - the other tests check
# relations, or race the searches against brute-force oracles - so without this
# file a behaviour change during a refactor would sail through green.


from dataclasses import dataclass, field

import numpy as np
import pytest

from src.models.deck import DeckCrossSection
from src.services.influence import InfluenceSurface
from src.services.critical_position import CriticalPositionService
rank_all_positions = CriticalPositionService.rank_all_positions

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
    options: dict
    cases: int
    response: float
    response_before_reduction: float
    lane_reduction: float
    design_lanes: int
    lane_pattern: str
    footway_response: float
    residual_udl_applied: bool
    resultant_centred_response: float
    total_over_all_cases: float
    vehicles: list[tuple[str, float, float, tuple[float, ...]]] = field(default_factory=list)


GOLDEN_ANSWERS = [
    GoldenAnswer(
        name="two class a vehicles on a dual carriageway, sagging",
        surface=sagging_surface(),
        cross_section=DUAL_CARRIAGEWAY,
        span_m=SPAN_M,
        options={"adverse": "maximum"},
        cases=1,
        response=14643.631387490512,
        response_before_reduction=14643.631387490512,
        lane_reduction=1.0,
        design_lanes=2,
        lane_pattern="class_a | class_a",
        footway_response=0.0,
        residual_udl_applied=True,
        resultant_centred_response=14484.663402483677,
        total_over_all_cases=14643.631387490512,
        vehicles=[
            ("Class_A_reversed", 5.15, 4.199999999999999, (4.199999999999999,)),
            ("Class_A", 8.35, 12.0, (12.0,)),
        ],
    ),
    GoldenAnswer(
        name="the same, with the clause 206 crowd on both footpaths",
        surface=sagging_surface(),
        cross_section=DUAL_CARRIAGEWAY,
        span_m=SPAN_M,
        options={"adverse": "maximum", "apply_footway_load": True},
        cases=1,
        response=17079.377783436674,
        response_before_reduction=17079.377783436674,
        lane_reduction=1.0,
        design_lanes=2,
        lane_pattern="class_a | class_a",
        footway_response=2435.746395946163,
        residual_udl_applied=True,
        resultant_centred_response=16920.40979842984,
        total_over_all_cases=17079.377783436674,
        vehicles=[
            ("Class_A_reversed", 5.15, 4.199999999999999, (4.199999999999999,)),
            ("Class_A", 8.35, 12.0, (12.0,)),
        ],
    ),
    GoldenAnswer(
        name="a train of two in each lane, hogging over the pier",
        surface=hogging_surface(),
        cross_section=DUAL_CARRIAGEWAY,
        span_m=2 * SPAN_M,
        options={"adverse": "minimum"},
        cases=1,
        response=-13346.181789873128,
        response_before_reduction=-13346.181789873128,
        lane_reduction=1.0,
        design_lanes=2,
        lane_pattern="class_a | class_a",
        footway_response=0.0,
        residual_udl_applied=True,
        resultant_centred_response=-13221.640892932408,
        total_over_all_cases=-13346.181789873128,
        vehicles=[
            ("Class_A", 5.15, 6.4, (6.4, 45.2)),
            ("Class_A", 8.35, 6.4, (6.4, 45.2)),
        ],
    ),
    GoldenAnswer(
        name="a narrow carriageway carrying the table 6 residual udl",
        surface=sagging_surface(),
        cross_section=NARROW_CARRIAGEWAY,
        span_m=SPAN_M,
        options={"adverse": "maximum"},
        cases=1,
        response=7036.801253437773,
        response_before_reduction=7036.801253437773,
        lane_reduction=1.0,
        design_lanes=1,
        lane_pattern="class_a",
        footway_response=0.0,
        residual_udl_applied=True,
        resultant_centred_response=6907.310799101389,
        total_over_all_cases=7036.801253437773,
        vehicles=[("Class_A", 3.8, 12.0, (12.0,))],
    ),
    GoldenAnswer(
        # A 70R boxed in by Class A is never drawn, so this arrangement only
        # appears once the combination drawings are lifted. It then governs.
        #
        # These figures moved by ~0.5 in 16,000 when the 70R Wheeled first axle spacing
        # was corrected from 3.95 m to 3.96 m. They are the only pinned numbers a 70R
        # Wheeled takes part in, which is why nothing else here changed.
        name="a 70r between two class a lanes, drawings lifted",
        surface=sagging_surface(),
        cross_section=WIDE_CARRIAGEWAY,
        span_m=SPAN_M,
        options={"adverse": "maximum", "follow_combination_drawings": False},
        cases=8,
        response=16335.39080706197,
        response_before_reduction=20419.23850882746,
        lane_reduction=0.8,
        design_lanes=4,
        lane_pattern="class_a + zone_70r + class_a",
        footway_response=0.0,
        residual_udl_applied=False,
        resultant_centred_response=16328.715138053403,
        total_over_all_cases=101774.74837333518,
        vehicles=[
            ("Class_A_reversed", 2.0625, 4.199999999999999, (4.199999999999999,)),
            ("Class_70R_Wheeled", 6.7325, 8.52, (8.52,)),
            ("Class_A", 11.3625, 12.0, (12.0,)),
        ],
    ),
]


@pytest.fixture(scope="module", params=GOLDEN_ANSWERS, ids=lambda golden: golden.name)
def golden_and_ranked(request):
    golden = request.param
    ranked = CriticalPositionService.rank_all_positions(
        golden.surface, golden.cross_section, span_m=golden.span_m, **golden.options
    )
    return golden, ranked


def test_the_governing_response_has_not_moved(golden_and_ranked):
    golden, ranked = golden_and_ranked
    worst = ranked[0]

    assert worst.response == pytest.approx(golden.response, rel=1e-12)
    assert worst.response_before_reduction == pytest.approx(
        golden.response_before_reduction, rel=1e-12
    )
    assert worst.lane_reduction == pytest.approx(golden.lane_reduction, rel=1e-12)


def test_the_governing_arrangement_has_not_moved(golden_and_ranked):
    golden, ranked = golden_and_ranked
    worst = ranked[0]

    assert len(ranked) == golden.cases
    assert worst.lane_pattern == golden.lane_pattern
    assert worst.design_lanes == golden.design_lanes
    assert worst.residual_udl_applied is golden.residual_udl_applied


def test_the_added_loads_have_not_moved(golden_and_ranked):
    golden, ranked = golden_and_ranked
    worst = ranked[0]

    assert worst.footway_response == pytest.approx(golden.footway_response, rel=1e-12)
    assert worst.resultant_centred_response == pytest.approx(
        golden.resultant_centred_response, rel=1e-12
    )


def test_every_vehicle_stands_where_it_stood(golden_and_ranked):
    golden, ranked = golden_and_ranked
    placed_vehicles = ranked[0].vehicles

    assert len(placed_vehicles) == len(golden.vehicles)

    for placed, (name, z_centre_m, x_front_m, train_x_front_m) in zip(
        placed_vehicles, golden.vehicles, strict=True
    ):
        assert placed.vehicle_name == name
        assert placed.z_centre_m == pytest.approx(z_centre_m, abs=1e-9)
        assert placed.x_front_m == pytest.approx(x_front_m, abs=1e-9)
        assert placed.train_x_front_m == pytest.approx(train_x_front_m, abs=1e-9)


def test_the_losing_cases_have_not_moved_either(golden_and_ranked):
    # Ranking every case, not just the winner, is what catches a change that
    # only shows up in an arrangement the sweep happened to reject.
    golden, ranked = golden_and_ranked

    total = sum(case.response for case in ranked)

    assert total == pytest.approx(golden.total_over_all_cases, rel=1e-12)


def test_the_report_block_still_reads(golden_and_ranked):
    golden, ranked = golden_and_ranked

    report = ranked[0].describe()

    assert golden.lane_pattern in report
    assert f"{golden.response:14.3f}" in report


def test_describe_survives_a_zero_response():
    # The shortfall is None when there is nothing to take a percentage of, and describe()
    # used to format that None straight into the report and raise TypeError.
    from src.models.results import CriticalPosition

    nothing_happened = CriticalPosition(
        response_name="a response that came out at zero",
        adverse="maximum",
        response=0.0,
        response_before_reduction=0.0,
        lane_reduction=1.0,
        design_lanes=1,
        lane_pattern="class_a",
        carriageways_read_as="separate",
        resultant_centred_response=0.0,
    )

    report = nothing_happened.describe()

    assert nothing_happened.resultant_centred_shortfall() is None
    assert "Resultant at mid-width" in report
    assert "% lower" not in report
