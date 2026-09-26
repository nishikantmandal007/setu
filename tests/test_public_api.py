import setu

EXPLICITLY_CALLED = [
    "AddedDeadLoads", "BridgeInput", "DeckSlab", "Girders", "Bracing", "MeshSettings", "DeckCrossSection",
    "Steel", "Concrete", "SurfacingLayer", "PlateGirderSection", "SeismicSite", "TemperatureSite", "WindSite", "CustomLoad",
    "build_mesh", "build_bridge_model", "InfluenceSolver", "find_critical_position", "rank_all_positions", "custom_combination",
    "applied_live_loads", "live_load", "girder_design_values", "analyze_load_case", "dead_load_forces",
    "result_dataset", "merge_datasets",
]


def test_the_public_api_is_what_the_cli_and_osdagbridge_call():
    assert [name for name in EXPLICITLY_CALLED if not hasattr(setu, name)] == []
