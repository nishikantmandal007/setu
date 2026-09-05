def irc6_uls_recipes():
    return {
        "ULS-1": {"dead": 1.35, "live": 1.50},
        "ULS-2": {"dead": 1.35, "live": 1.50, "wind": 1.15},
        "ULS-3": {"dead": 1.35, "live": 1.50, "temperature": 0.90},
        "ULS-4": {"dead": 1.35, "temperature": 1.50},
        "ULS-5": {"dead": 1.35, "temperature": 1.50, "wind": 1.15},
        "ULS-6": {"dead": 1.00, "wind": 1.50},
        "ULS-7": {"dead": 1.35, "live": 1.50, "braking": 1.50},
        "ULS-8": {"dead": 1.35, "seismic": 1.50},
        "ULS-9": {"dead": 1.35, "live": 0.20, "seismic": 1.50},
        "ULS-10": {"dead": 1.00, "live": 1.00},
    }


def irc6_sls_recipes():
    return {
        "SLS-rare-1": {"dead": 1.00, "live": 1.00},
        "SLS-rare-2": {"dead": 1.00, "live": 1.00, "wind": 0.60},
        "SLS-rare-3": {"dead": 1.00, "live": 1.00, "temperature": 0.60},
        "SLS-rare-4": {"dead": 1.00, "temperature": 1.00},
        "SLS-rare-5": {"dead": 1.00, "wind": 1.00},
        "SLS-freq-1": {"dead": 1.00, "live": 0.75},
        "SLS-freq-2": {"dead": 1.00, "live": 0.75, "temperature": 0.50},
        "SLS-qp-1": {"dead": 1.00},
        "SLS-qp-2": {"dead": 1.00, "temperature": 0.50},
    }


def irc6_fatigue_recipe():
    return {"fatigue": {"dead": 1.00, "fatigue": 1.00}}


def irc6_construction_recipe():
    return {"construction": {"dead": 1.00, "construction": 1.20}}
