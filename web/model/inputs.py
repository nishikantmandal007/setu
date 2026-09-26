import inspect

from setu import (AddedDeadLoads, Bracing, BridgeInput, Concrete, DeckCrossSection, DeckSlab, Girders, MeshSettings,
                  PlateGirderSection, SeismicSite, Steel, TemperatureSite, WindSite)

# the form the page draws: one entry per table, each field with its label, starting value and limits
SCHEMA = {
    "tables": [
        {"table": "bridge", "title": "Bridge", "fields": [{"key": "span_m", "label": "Span (m)", "value": 35.0, "min": 5, "max": 150}, {"key": "skew", "label": "Skew (tan of angle)", "value": 0.0, "min": 0, "max": 1}, {"key": "wearing_course_unit_weight_kn_m3", "label": "Wearing course unit weight (kN/m3)", "value": 22.0, "min": 0}]},
        {"table": "cross_section", "title": "Cross-section, left to right (m)", "strips": [["footpath_left", 1.5], ["kerb_left", 0.45], ["carriageway_1", 4.5], ["median", 0.6], ["carriageway_2", 4.5], ["kerb_right", 0.45], ["footpath_right", 1.5]]},
        {"table": "deck", "title": "Deck slab", "fields": [{"key": "thickness_m", "label": "Slab thickness (m)", "value": 0.23, "min": 0.15, "max": 0.4}, {"key": "overhang_m", "label": "Overhang (m)", "value": 1.25, "min": 0}, {"key": "wearing_course_thickness_m", "label": "Wearing course (m)", "value": 0.075, "min": 0}]},
        {"table": "girders", "title": "Girders", "fields": [{"key": "count", "label": "Number of girders", "value": 5, "min": 2, "max": 12, "integer": True}]},
        {"table": "girders.section", "title": "Plate girder section (m)", "fields": [{"key": "top_flange_width_m", "label": "Top flange width", "value": 0.55, "min": 0.1}, {"key": "top_flange_thickness_m", "label": "Top flange thickness", "value": 0.025, "min": 0.005}, {"key": "bottom_flange_width_m", "label": "Bottom flange width", "value": 0.65, "min": 0.1}, {"key": "bottom_flange_thickness_m", "label": "Bottom flange thickness", "value": 0.04, "min": 0.005}, {"key": "web_height_m", "label": "Web height", "value": 2.1, "min": 0.3}, {"key": "web_thickness_m", "label": "Web thickness", "value": 0.014, "min": 0.006}]},
        {"table": "bracing", "title": "Bracing", "fields": [{"key": "station_count", "label": "Brace lines along span", "value": 7, "min": 2, "integer": True}, {"key": "area_m2", "label": "Member area (m2)", "value": 0.01, "min": 0}, {"key": "arrangement", "label": "Arrangement", "value": "XT", "choices": ["X", "XT", "XB", "XTB", "K", "KT"]}]},
        {"table": "mesh", "title": "Mesh", "fields": [{"key": "panels_between_braces", "label": "Panels between braces", "value": 25, "min": 1, "integer": True}, {"key": "target_size_across_width_m", "label": "Target size across (m)", "value": 0.25, "min": 0.05}]},
        {"table": "steel", "title": "Steel", "fields": [{"key": "elastic_modulus_mpa", "label": "E (MPa)", "value": 200000, "min": 1}, {"key": "poissons_ratio", "label": "Poisson's ratio", "value": 0.3, "min": 0, "max": 0.5}, {"key": "unit_weight_kn_m3", "label": "Unit weight (kN/m3)", "value": 78.5, "min": 0}]},
        {"table": "concrete", "title": "Deck concrete", "fields": [{"key": "elastic_modulus_mpa", "label": "Ecm (MPa)", "value": 32000, "min": 1}, {"key": "poissons_ratio", "label": "Poisson's ratio", "value": 0.2, "min": 0, "max": 0.5}, {"key": "unit_weight_kn_m3", "label": "Unit weight (kN/m3)", "value": 25.0, "min": 0}]},
        {"table": "added_dead_loads", "title": "SIDL (footpath area load, the rest line loads per strip)", "fields": [{"key": "footpath_kpa", "label": "Footpath (kN/m2)", "value": 3.6, "min": 0}, {"key": "kerb_kn_per_m", "label": "Kerb (kN/m)", "value": 3.24, "min": 0}, {"key": "median_kn_per_m", "label": "Median (kN/m)", "value": 3.6, "min": 0}, {"key": "crash_barrier_kn_per_m", "label": "Crash barrier (kN/m)", "value": 0.0, "min": 0}, {"key": "railing_kn_per_m", "label": "Railing (kN/m)", "value": 0.0, "min": 0}]},
        {"table": "wind", "title": "Wind (IRC:6 209)", "optional": True, "fields": [{"key": "basic_wind_speed_mps", "label": "Basic wind speed (m/s)", "value": 39.0, "min": 20, "max": 60}, {"key": "terrain", "label": "Terrain", "value": "plain", "choices": ["plain", "obstructed"]}, {"key": "height_m", "label": "Average exposed height (m)", "value": 12.0, "min": 0, "max": 100}, {"key": "solid_barrier_height_m", "label": "Solid barrier height (m)", "value": 1.1, "min": 0}, {"key": "funnelling", "label": "Funnelling topography", "value": False, "choices": [False, True]}]},
        {"table": "seismic", "title": "Seismic (IRC:SP:114)", "optional": True, "fields": [{"key": "zone", "label": "Zone", "value": "IV", "choices": ["II", "III", "IV", "V"]}, {"key": "soil", "label": "Soil type", "value": "II", "choices": ["I", "II", "III"]}, {"key": "importance_factor", "label": "Importance factor I", "value": 1.2, "min": 1}, {"key": "period_s", "label": "Fundamental period T (s)", "value": 0.5, "min": 0}, {"key": "response_reduction", "label": "Response reduction R", "value": 1.0, "choices": [1.0, 2.0, 3.0, 4.0, 5.0]}]},
        {"table": "temperature", "title": "Temperature (IRC:6 215)", "optional": True, "fields": [{"key": "shade_max_c", "label": "Max shade temperature (C)", "value": 45.0}, {"key": "shade_min_c", "label": "Min shade temperature (C)", "value": 2.0}]},
    ]
}
TABLE_CLASSES = {"deck": DeckSlab, "girders.section": PlateGirderSection, "bracing": Bracing, "mesh": MeshSettings, "concrete": Concrete, "steel": Steel,
                 "added_dead_loads": AddedDeadLoads, "wind": WindSite, "seismic": SeismicSite, "temperature": TemperatureSite}
BRIDGE_KEYS = {"span_m", "skew", "wearing_course_unit_weight_kn_m3"}
SITE_TABLES = ("wind", "seismic", "temperature")


# a problem with the form, worded for the page
class InputError(Exception):
    pass


# the parameters a class must be given, and all it accepts
def keys_of(cls):
    parameters = [p for name, p in inspect.signature(cls.__init__).parameters.items() if name != "self"]
    return {p.name for p in parameters if p.default is p.empty}, {p.name for p in parameters}


# one table's values, refused if a key is unknown or a required one is missing
def checked(table, values, required, allowed):
    unknown = set(values) - allowed
    if unknown:
        raise InputError(f"{table} has unknown field(s) {sorted(unknown)}")
    missing = required - set(values)
    if missing:
        raise InputError(f"{table} is missing {sorted(missing)}")
    return values


# one table of the form as its setu object
def build(table, tables):
    if table not in tables:
        raise InputError(f"the form has no {table} table")
    cls = TABLE_CLASSES[table]
    return cls(**checked(table, tables[table], *keys_of(cls)))


# the bridge and its site loads from what the page sent: {"tables": {...}, "strips": [[name, width], ...], "include": {"wind": true, ...}}
def bridge_from_form(form):
    tables, include = form.get("tables", {}), form.get("include", {})
    strips = {name: width for name, width in form.get("strips", [])}
    if not strips:
        raise InputError("the cross-section has no strips")
    girders = checked("girders", tables.get("girders", {}), {"count"}, {"count"})
    bridge = BridgeInput(cross_section=DeckCrossSection.from_widths(strips), deck=build("deck", tables),
                         girders=Girders(section=build("girders.section", tables), **girders),
                         bracing=build("bracing", tables), mesh=build("mesh", tables), steel=build("steel", tables), concrete=build("concrete", tables),
                         added_dead_loads=build("added_dead_loads", tables), **checked("bridge", tables.get("bridge", {}), BRIDGE_KEYS, BRIDGE_KEYS))
    loads = {table: build(table, tables) if include.get(table) else None for table in SITE_TABLES}
    return bridge, loads
