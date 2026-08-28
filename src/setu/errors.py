# Every error setu raises on purpose. They all derive from SetuError, so a
# caller can write `except SetuError` and be sure of catching every intentional
# failure without also swallowing bugs.

from __future__ import annotations


class SetuError(Exception):
    # Base class for every error setu raises on purpose.
    pass


class CrossSectionError(SetuError):
    # The deck cross-section is malformed - no carriageway, or an unknown split mode.
    pass


class VehicleDefinitionError(SetuError):
    # A vehicle definition failed validation.
    pass


class VehicleNotFoundError(SetuError, KeyError):
    # A vehicle name was asked for that no registry knows.
    pass


class NoAdmissibleArrangementError(SetuError, ValueError):
    # No IRC:6 lane arrangement fits the carriageway it was given.
    pass


class InfluenceSurfaceError(SetuError, ValueError):
    # The influence surface data is unusable - wrong shape, or an empty sample range.
    pass


class BackendError(SetuError):
    # The finite element backend is missing, unusable, or refused a command.
    pass


class ModelAlreadyLoadedError(SetuError):
    # Something else is loading the model, so an influence surface would be wrong.
    # A surface is read off the deflected shape under one imaginary load. Any other
    # load pattern still acting adds its own deflections to that shape, and the
    # surface comes out silently wrong rather than failing.
    pass


class NotLinearError(SetuError):
    # The model failed the superposition check - influence surfaces only apply
    # to a linear model. Never raised by setu itself; kept for a third-party
    # backend to raise.
    pass
