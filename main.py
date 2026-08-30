from src.services.critical_position import CriticalPositionService

def find_critical_position(*args, **kwargs):
    return CriticalPositionService.find_critical_position(*args, **kwargs)

def rank_all_positions(*args, **kwargs):
    return CriticalPositionService.rank_all_positions(*args, **kwargs)

