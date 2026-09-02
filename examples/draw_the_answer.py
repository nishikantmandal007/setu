from src.services.critical_position import find_critical_position
from src.services.drawing import animate_vehicle_along_span, draw_everything
"""Draws the critical position setu found, on the 35 m plate girder bridge.

Run it::

    uv run python examples/draw_the_answer.py

It writes two files next to itself: a four-panel figure of the answer, and an
animation of the governing vehicle driving across the deck.
"""


from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from plate_girder_35m import BRIDGE, CROSS_SECTION  # noqa: E402

from src.services.influence_surface import InfluenceSolver  # noqa: E402
from src.services.bridge_geometry import build_bridge_model  # noqa: E402

HERE = Path(__file__).parent


def main() -> None:
    model = build_bridge_model(BRIDGE)
    influence = InfluenceSolver(model.as_deck_model())
    surface = influence.for_girder_moment(
        "middle girder, midspan moment",
        model.midspan_element_of_girder(BRIDGE.girders.count // 2),
    )

    worst = find_critical_position(
        surface,
        CROSS_SECTION,
        span_m=BRIDGE.span_m,
        adverse="minimum",
        wearing_course_thickness_m=BRIDGE.deck.wearing_course_thickness_m,
    )
    print(worst.describe())

    figure = draw_everything(
        surface,
        CROSS_SECTION,
        worst,
        span_m=BRIDGE.span_m,
        wearing_course_thickness_m=BRIDGE.deck.wearing_course_thickness_m,
    )
    figure.savefig(HERE / "critical_position.png", dpi=130, bbox_inches="tight")
    print(f"\nwrote {HERE / 'critical_position.png'}")

    sweep = animate_vehicle_along_span(surface, worst)
    sweep.save(HERE / "vehicle_sweep.gif", writer="pillow", fps=22)
    print(f"wrote {HERE / 'vehicle_sweep.gif'}")

    plt.close("all")


if __name__ == "__main__":
    main()
