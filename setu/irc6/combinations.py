from setu.helpers import adverse_sign
from setu.irc6.irc_constants import (
    EACH_VARIABLE_LOAD_LEADS_IN,
    LIVE_LOAD_OFF_ABOVE_WIND_SPEED_MPS,
    PERMANENT_LOAD_FACTORS,
    VARIABLE_LOAD_FACTORS,
)
from setu.utils.constants import LIVE, WIND

IGNORED_WHEN_RELIEVING = 0.0


class Combination:
    def __init__(self, name, limit_state, factors, leading=None):
        self.name = name
        self.limit_state = limit_state
        self.factors = factors
        self.leading = leading

    def to_dict(self):
        return self.__dict__


def irc6_combinations(wind_speed_at_deck_mps=None):
    combinations = []
    for limit_state, variable_loads in VARIABLE_LOAD_FACTORS.items():
        if limit_state in EACH_VARIABLE_LOAD_LEADS_IN:
            leaders = list(variable_loads)
        else:
            leaders = [group for group, (leading, _) in variable_loads.items() if leading is not None] or [None]
        for leading in leaders:
            factors = dict(PERMANENT_LOAD_FACTORS[limit_state])
            for group, (leading_factor, accompanying_factor) in variable_loads.items():
                factor = leading_factor if group == leading else accompanying_factor
                factors[group] = (factor, IGNORED_WHEN_RELIEVING)
            if too_windy_for_traffic(wind_speed_at_deck_mps) and LIVE in factors and WIND in factors:
                del factors[LIVE if leading == WIND else WIND]
            name = limit_state if leading is None else f"{limit_state}, {leading} leading"
            combinations.append(Combination(name, limit_state, factors, leading))
    return combinations


def too_windy_for_traffic(wind_speed_at_deck_mps):
    return wind_speed_at_deck_mps is not None and wind_speed_at_deck_mps > LIVE_LOAD_OFF_ABOVE_WIND_SPEED_MPS


def custom_combination(name, factors, limit_state="custom"):
    return Combination(name, limit_state, {group: (factor, factor) for group, factor in factors.items()})


def design_value(effects, combination, adverse):
    worse_is_positive = adverse_sign(adverse)
    shares = {}
    for group, (adding, relieving) in combination.factors.items():
        effect = worst_of(effects.get(group, 0.0), worse_is_positive)
        factor = adding if worse_is_positive * effect >= 0 else relieving
        shares[group] = factor * effect
    return (sum(shares.values()), shares)


def worst_of(effect, worse_is_positive):
    alternatives = effect if isinstance(effect, (list, tuple)) else [effect]
    return max(alternatives, key=lambda value: worse_is_positive * value)
