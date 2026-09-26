# Web app

A local page that runs the full analysis and shows the results in plain words, with animations and plots.

```bash
uv run python web/main.py              # then open http://localhost:5000
```

Open http://localhost:5000, fill in the bridge and press **Analyse**. A progress bar follows the analysis, then the results appear in plain words:

- **Critical positions**: a scale drawing of the deck with the vehicles where they do the most harm to each girder.
- **Search replay**: the search played as an animation on your bridge's real influence surfaces.
- **Girder diagrams**: bending moment, shear and deflection along one girder or all of them, for each load case.
- **3D model**: the deck mesh, girders and braces, with forces drawn on the girders.
- **Export critical loads CSV**: the maximum-moment critical position as a static load case (wheels as point loads with impact and lane reduction, lane and footpath loads as area loads), to check in any finite element program.

The web app lives in `web/` and only uses Setu's public functions.
