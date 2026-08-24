"""Every error setu raises on purpose.

They all derive from SetuError, so a caller can write `except SetuError` and be
sure of catching every intentional failure without also swallowing bugs.
"""

from __future__ import annotations


class SetuError(Exception):
    """Base class for every error setu raises on purpose."""


class CrossSectionError(SetuError):
    """The deck cross-section is malformed - no carriageway, or an unknown split mode."""


class VehicleDefinitionError(SetuError):
    """A vehicle definition failed validation."""


class VehicleNotFoundError(SetuError, KeyError):
    """A vehicle name was asked for that no registry knows."""


class NoAdmissibleArrangementError(SetuError, ValueError):
    """No IRC:6 lane arrangement fits the carriageway it was given."""


class InfluenceSurfaceError(SetuError, ValueError):
    """The influence surface data is unusable - wrong shape, or an empty sample range."""


class BackendError(SetuError):
    """The finite element backend is missing, unusable, or refused a command."""


class ModelAlreadyLoadedError(SetuError):
    """Something else is loading the model, so an influence surface would be wrong.

    An influence surface is read off the deflected shape under one imaginary
    load. Any other load pattern still acting adds its own deflections to that
    shape, and the surface silently comes out wrong rather than failing.
    """


class NotLinearError(SetuError):
    """The model failed the superposition check.

    Influence surfaces are only valid for a linear model, so the whole method
    stops being applicable the moment this fails.
    """
