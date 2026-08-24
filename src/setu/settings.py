"""How finely setu samples candidate positions.

These are the numbers *we* chose, not numbers the code prescribes - every IRC:6
value lives in `irc_code_rules/code_tables.py`.

The searches enrich their grids with the exact breakpoints of the response
curves, so these defaults already give the exact answer for the sampled model.
Raising them costs time and buys nothing; they exist so an unusual deck can be
sampled more finely if it ever needs to be.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SamplingSettings:
    """Grid densities for the transverse and longitudinal searches."""

    sliding_steps: int = 41
    """How many sliding offsets to try for a lane arrangement."""

    float_steps: int = 41
    """How many positions to try for a 70R vehicle floating inside its zone."""

    transverse_steps: int = 241
    """Uniform fill across the deck width, on top of the exact breakpoints."""

    positions_per_chunk: int = 192
    """Longitudinal positions evaluated at once. Bounds peak memory."""

    patch_steps_along_span: int = 4
    """Point loads along a tracked vehicle's contact patch."""

    patch_steps_across_width: int = 2
    """Point loads across a tracked vehicle's contact patch."""

    udl_cells_along_span: int = 2
    """Integration cells per mesh interval, along the span, for the residual UDL."""

    udl_cells_across_width: int = 4
    """Integration cells per mesh interval, across the width, for the residual UDL."""


DEFAULT_SAMPLING = SamplingSettings()
