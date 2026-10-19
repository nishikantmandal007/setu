# Web app

```bash
uv run python web/main.py
```

Open http://localhost:5000, enter the bridge inputs and press **Analyse**.
Under **Plate girder section**, select **Use individual sections** to enter each girder left to right.
Braking height defaults to **Standard IRC:6 — 1.2 m above road surface**;
**Custom height above deck top** enables a height input measured from the concrete slab top.

The progress screen shows a percentage ring, stage title, current task, operation counts and errors.
Its six stages show:

- **Dead load stages**: construction loads and applied/solved status.
- **Influence surfaces**: a heatmap with minimum, maximum and units.
- **Searching traffic**: the worst layout or a braking result with two direction buttons.
- **Fatigue truck**: truck positions A and B and their stress range.
- **Checking in OpenSees**: influence-surface predictions beside direct solves.
- **Preparing the plots**: the load-combination count.

Traffic progress counts searches, braking checks and combination batches separately.

The results include:

- **Deflection**: traffic and total deflection, limits L/800 and L/600, and pass/fail.
  **See design forces & fatigue stress** shows demands; label tooltips explain each quantity.
- **Check bridge inputs**: geometry, materials, effective slab widths and dead deflection by stage.
- **Traffic positions**: place/girder tabs, deck plan, expandable vehicle table, legend and two critical-load CSV exports.
  The readout shows the girder, response and lane reduction; deflection excludes footway load (IRC:22).
- **Search replay**: vehicles alone, then setu's best lane arrangements, rolled along the span.
  Use the player, charts and braking toggle; braking has two direction buttons.
- **Girder diagrams** and **3D model**: load-case, girder and force controls.
- **Wind, earthquake & temperature**: load shares, site values and temperature stresses.
- **Detailed results by girder**: combination selection, design forces, load shares and fatigue stresses.

The web app lives in `web/` and uses Setu's public functions.
Restart the web process after backend changes.
