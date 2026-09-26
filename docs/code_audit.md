# Code audit — values against the code text (26 Sep 2026)

I checked every value in `setu/irc6/irc_constants.py`, `setu/irc6/vehicles.py` and `setu/models/materials.py` against the printed code. Sources:
- IRC:6-2017
- IRC:22-2015
- IRC:SP:114-2018
- IRC:5-2015 (for one value)

**Result:** one mismatch, now fixed. Points open to interpretation are in the findings ledger.

## Mismatch fixed

| Value | setu had | Code | Clause | Fix |
|---|---|---|---|---|
| 70R wheeled, centre-to-centre of the wheel lines | 2.06 m | 2.79 − 0.86 = **1.93 m** | IRC:6 Fig. 1 (2.79 m over the tyres, 0.86 m tyre groups) | `vehicles.py`; test `test_70r_wheel_lines_are_centred_on_their_tyre_groups`. The 2.06 m value belongs to the 70R tracked vehicle (2.90 − 0.84). |

This moves the losing 70R arrangements only. On the golden deck the Class A cases still govern, so the only pinned number that changed is the sum over all cases in `test_golden_values.py`.

## Checked and matching

| Group | Values | Clause |
|---|---|---|
| Vehicles | Class A axles 2.7/2.7/11.4/11.4/6.8×4 t at 1.1/3.2/1.2/4.3/3.0/3.0/3.0 m, gauge 1.8 m, 18.5 m nose to tail; 70R wheeled 100 t on 7 axles at 3.96/1.52/2.13/1.37/3.05/1.37 m, 30 m from the rear axle to the next front axle (28.28 m between bodies); 70R tracked 2 × 35 t on 4.57 × 0.84 m tracks, gauge 2.06 m, 90 m nose to tail | IRC:6 204.1, Figs. 1 and 3 |
| Transverse placement | Class A lane 2.3 m, 0.15 m kerb clearance, 1.2 m gap (0.4 m floor); 70R 2.9 m wide, 1.2 m clearance | IRC:6 204.3, Table 3 |
| Lanes | Table 6 widths 5.3/9.6/13.1/16.6/20.1/23.6 m; below 4.25 m not loaded | IRC:6 Table 6, 6A; IRC:5 104.3 |
| Lane reduction | 1, 1, 0.9, 0.8 | IRC:6 205, Table 8 |
| Residual UDL | 500 kg/m² below 5.3 m | IRC:6 Table 6 note |
| Footway | 400 kg/m²; P′ for 7.5–30 m; P″ above 30 m; width factor (16.5 − W)/15 | IRC:6 206.1, 206.3 |
| Fatigue truck | 12/14/14 t at 4.5/1.4 m; tyres 310 mm, pairs 710 mm, 2390 mm overall; 150 mm off the kerb; 50% impact | IRC:6 204.6, Fig. 7 |
| Impact | Fig. 9 steel curve; 25% up to 9 m; tracked 10% with 5–9 m transition; 70R wheeled curve from 23 m | IRC:6 208 |
| Wind | Table 12 speeds and pressures at 33 m/s; G = 2.0; C_D 2.2 single, 2(1 + c/20d) ≤ 4 for several girders; longitudinal 25%; C_L 0.75; live load C_D 1.2 over 3 m at 1.5 m; no live load above 36 m/s; 1.2 for funnelling | IRC:6 209.1–209.3.7 |
| Braking | 20% first train, 10% following, 5% for lanes beyond two, 1.2 m above the road | IRC:6 211.2, 211.3 |
| Load factors | Tables B.2 (ULS basic, seismic) and B.3 (rare, frequent, quasi-permanent), both leading and accompanying | IRC:6 Annex B |
| Temperature | Metallic +15/−10 °C; α = 12 × 10⁻⁶; Table 15B profile, h1 = 0.6h, h2 = 0.4 m | IRC:6 215.2–215.4 |
| Seismic zones | Z = 0.10/0.16/0.24/0.36 | SP:114 Table 4.2 |
| Importance | 1.0/1.2/1.5 | SP:114 Table 4.3 |
| Directions | 100/30/30; vertical Z × 2/3 | SP:114 4.2.1–4.2.3 |
| Live load in seismic | 20% without impact, perpendicular to traffic and vertical only | SP:114 4.6 (p. 30) |
| Ah | (Z/2)(Sa/g)/(R/I) | SP:114 5.2.1 (p. 34) |
| Spectrum | Fig. 5.1(a): 2.5 up to 0.40/0.55/0.67 s, then 1.00/1.36/1.67 ÷ T, then 0.25/0.34/0.42 past 4 s; 2.5 when no period is worked out | SP:114 5.2.1 (p. 36) |
| Minimum Ah | 0.011/0.017/0.025/0.038 | SP:114 5.4, Table 5.2 (p. 39) |
| Modular ratio | m = Es/Ecm ≥ 7.5 short term; Es/(Kc·Ecm) ≥ 15 long term, Kc = 0.5 | IRC:22 604.3 |

## Open to interpretation (in the ledger)

- Kerbs 0.6 m or wider take the footway load (IRC:6 206.4). setu loads only strips named as footpaths.
- Annex B.3 note 3 says wind and temperature need not act together. setu combines both, which is conservative.
- SP:114 4.2.1 asks for vertical seismic in zones II and III when checking bearings and stability. setu applies it only in zones IV and V.
- For the vertical seismic case, SP:114 gives a vertical period formula (Eq. 4.1). setu uses the 2.5 plateau, which is conservative.
