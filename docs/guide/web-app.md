# Web app

A local page that runs the full analysis and shows the results in plain words, with animations and plots.

```bash
uv run python web/main.py              # then open http://localhost:5000
```

Open http://localhost:5000, fill in the bridge and press **Analyse**. A progress bar follows the analysis, then the results appear in plain words:

- **Movement overview**: traffic and total midspan deflection, each beside its allowed value and a plain-language explanation. “Within limit” applies to that movement check. Open **See design forces & fatigue stress** for member and bearing demands, with a description of each quantity.
- **Check bridge inputs** (collapsed initially): bridge width and girder spacing, with separate expandable sections for material grades/stiffness, effective slab widths, and dead deflection by construction stage. Choose a girder to read the stage movements vertically, including surfacing, before camber.
- **Traffic positions**: a scale drawing of the deck with the vehicles where they do the most harm to each girder. Open **See vehicle positions & impact factors** for carriageway, centre z from the deck edge, centre offset from the left carriageway boundary, front x and impact multiplier (1 + i).
- **Search replay**: the search played as an animation on your bridge's real influence surfaces.
- **Girder diagrams**: bending moment, shear and deflection along one girder or all of them, for each load case.
- **3D model**: the deck mesh, girders and braces, with forces drawn on the girders.
- **Detailed results by girder** (collapsed initially): select the worst combination for each check or an individual load combination, and inspect its station and factored load shares. These are independent response envelopes, not one simultaneous truck layout. The load-case dropdown in Girder diagrams and 3D model selects unfactored solved cases.
- **Fatigue**: longitudinal steel stress ranges in MPa at both flange faces, with extrema, section and truck positions, and fatigue impact multiplier. The headline shows the larger face range; fatigue resistance and life are outside this check.
- **Export critical loads CSV**: the maximum-moment critical position as a static load case (wheels as point loads with impact and lane reduction, lane and footpath loads as area loads), to check in any finite element program.

The web app lives in `web/` and only uses Setu's public functions.
