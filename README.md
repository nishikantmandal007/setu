# setu

Setu finds the worst IRC:6 traffic position for a bridge.

Instead of running an FEA for every vehicle position, it calculates an
influence surface once and then searches the vehicle positions efficiently.

## Install

Python 3.12+.

```bash
pip install -r requirements.txt
````

## Run

There's a 35 m plate-girder example:

```bash
PYTHONPATH=. python examples/plate_girder_35m.py
```

Or use it from Python:

```python
from examples.plate_girder_35m import BRIDGE
from src.services.bridge_geometry import build_bridge_model
from src.services.influence_surface import InfluenceSolver
from src.services.critical_position import find_critical_position

model = build_bridge_model(BRIDGE)

surface = InfluenceSolver(model.as_deck_model()).for_girder_moment(
    "midspan moment",
    model.midspan_element_of_girder(2),
)

worst = find_critical_position(
    surface,
    BRIDGE.cross_section,
    span_m=BRIDGE.span_m,
)

print(worst.describe())
```

To draw the result:

```bash
PYTHONPATH=. python examples/draw_the_answer.py
```

## Structure

```text
src/
├── models/       bridge inputs and properties
├── services/     geometry, FEA, influence surfaces, vehicle search
└── rules/        IRC:6 rules

examples/         example bridges and scripts
```

```
```
