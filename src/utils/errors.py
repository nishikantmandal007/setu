class SetuError(Exception):
    pass

class CrossSectionError(SetuError):
    pass

class VehicleDefinitionError(SetuError):
    pass

class VehicleNotFoundError(SetuError, KeyError):
    pass

class NoAdmissibleArrangementError(SetuError, ValueError):
    pass

class InfluenceSurfaceError(SetuError, ValueError):
    pass

class BackendError(SetuError):
    pass

class ModelAlreadyLoadedError(SetuError):
    pass

class NotLinearError(SetuError):
    pass
