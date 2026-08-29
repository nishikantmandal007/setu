# Colours and the lazy matplotlib import shared by every picture in this package.

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

STRIP_COLOURS = {
    "carriageway": "#3d4451",
    "footpath": "#8d9aad",
    "footway": "#8d9aad",
    "kerb": "#c2b59b",
    "median": "#9aa77f",
}
OTHER_STRIP_COLOUR = "#b8b8b8"

ADVERSE_COLOUR = "#c0392b"
HELPFUL_COLOUR = "#2471a3"
VEHICLE_COLOUR = "#f0b323"

# How many points draw a smooth curve down the span - a drawing proportion, not a value
# from the code, so it lives here rather than in sampling.py.
INFLUENCE_LINE_SAMPLES = 600


def strip_colour(name: str) -> str:
    for prefix, colour in STRIP_COLOURS.items():
        if name.startswith(prefix):
            return colour
    return OTHER_STRIP_COLOUR


def adverse_colourmap() -> Any:
    # Blue where a load helps, red where it hurts, pale in between.
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "adverse", [HELPFUL_COLOUR, "#dfe6ec", "#f7f2e8", "#e8a798", ADVERSE_COLOUR]
    )


# ---------------------------------------------------------------------------
# Matplotlib Access
# ---------------------------------------------------------------------------

# matplotlib ships no usable type stubs, so its objects are aliased to Any here rather
# than described with a Protocol that mypy could not check - the same honest approach
# model_tags.SolverCommands takes for openseespy.
Axes = Any
Figure = Any


def import_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as missing:
        raise ImportError(
            "drawing needs matplotlib, which setu does not install by default. "
            "Add it with `uv sync --extra plot`."
        ) from missing
    return plt
