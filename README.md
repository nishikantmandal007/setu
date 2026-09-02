# setu

Setu finds the worst legal IRC:6 traffic position for a bridge response without
running one finite-element analysis for every trial vehicle location. It solves
one influence surface, then uses vectorised response evaluation and dynamic
programming to search vehicles along the span and across each carriageway.

## Install

Python 3.12 or later is required.

```bash
pip install -r requirements.txt
```

## Run an analysis

The included 35 m plate-girder bridge is a complete working example:

```bash
PYTHONPATH=. python examples/plate_girder_35m.py
```

For application code, build a bridge, obtain an influence surface, and pass it
to the function-first search API:

```python
from examples.plate_girder_35m import BRIDGE
from src.services.bridge_geometry import build_bridge_model
from src.services.influence_surface import InfluenceSolver
from src.services.critical_position import find_critical_position

model = build_bridge_model(BRIDGE)
surface = InfluenceSolver(model.as_deck_model()).for_girder_moment(
    "midspan moment", model.midspan_element_of_girder(2)
)
worst = find_critical_position(surface, BRIDGE.cross_section, span_m=BRIDGE.span_m)
print(worst.describe())
```

To draw the result:

```bash
PYTHONPATH=. python examples/draw_the_answer.py
```

## Module map

- `src.models.bridge`: bridge inputs and section properties
- `src.services.bridge_geometry`: mesh, finite-element geometry, and dead loads
- `src.services.influence_surface`: influence interpolation and analysis
- `src.services.vehicle_placement`: efficient vehicle-placement searches
- `src.rules.irc6`: IRC:6 rules
- `src.services.drawing`: drawing functions
