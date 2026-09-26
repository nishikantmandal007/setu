# The big picture

Setu goes from a bridge description to design forces in five steps.

![How Setu works, in six steps: 1 bridge input; 2 model, a shell deck on steel girders; 3 dead load in construction stages; 4 influence surfaces, one solve per result; 5 worst traffic for every girder; 6 design values from IRC:6 Annex B. Steps 3 and 5 both feed step 6](../assets/diagrams/flow.svg){ .only-light .diagram }
![How Setu works, in six steps: 1 bridge input; 2 model, a shell deck on steel girders; 3 dead load in construction stages; 4 influence surfaces, one solve per result; 5 worst traffic for every girder; 6 design values from IRC:6 Annex B. Steps 3 and 5 both feed step 6](../assets/diagrams/flow-dark.svg){ .only-dark .diagram }

1. **Model.** The deck slab becomes a mesh of shell elements. The steel girders sit under it as beams, tied to the slab, with cross bracing between them. Each girder rests on a bearing at each end. The solver is [OpenSees](https://opensees.berkeley.edu/).
2. **Dead load.** Self weight, the wet slab, kerbs, barriers and surfacing are applied in the order they are built, because the section that carries them changes as the bridge is built. [Read more →](dead-load.md)
3. **Influence surfaces.** For every result it needs (the moment near midspan of girder 2, the shear at its support, and so on), Setu works out a map of the deck showing how much a 1 kN load at each point contributes. [Read more →](influence-surfaces.md)
4. **Worst traffic.** Code vehicles are rolled over each map, in every lane arrangement the code allows, to find the position that hurts most. [Read more →](worst-traffic.md)
5. **Design values.** Dead, traffic, wind, earthquake and temperature effects are factored and added in every IRC:6 combination. The largest is the design value. [Read more →](design-values.md)

## The words used in these pages

| Word | Plain meaning |
|---|---|
| **Girder** | One of the main steel beams running along the span. Girder 0 is at the left edge. |
| **x, z** | x runs along the span from the first bearing; z runs across the deck from the left edge. |
| **Influence surface** | A map of the deck: at each point, the effect a 1 kN load standing there has on one result. |
| **Critical position** | Where the vehicles must stand to make one result as large as possible. |
| **Composite** | Steel girder and concrete slab working together as one section. |
| **Limit state** | A situation the code checks: ULS (strength) or SLS (in service). |
| **Design value** | The largest factored result over all load combinations. |
