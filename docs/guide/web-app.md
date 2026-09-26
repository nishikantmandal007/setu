# Web app

A local page that runs the full analysis and shows the results in plain words, with animations and plots.

```bash
uv run --with flask python web/app.py              # then open http://localhost:5000
```

Open http://localhost:5000, fill in the bridge and press **Analyse**. A progress bar follows the analysis, then the results appear in plain words:

- **Critical positions**: a scale drawing of the deck with the vehicles where they do the most harm to each girder.
- **Search replay**: the search played as an animation on your bridge's real influence surfaces.
- **Girder diagrams**: bending moment, shear and deflection along one girder or all of them, for each load case.
- **3D model**: the deck mesh, girders and braces, with forces drawn on the girders.
- **Export CSV for MIDAS**: the critical load case as point and area loads, to check in another program.

The web app lives in `web/` and only uses Setu's public functions.
