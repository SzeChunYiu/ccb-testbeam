# Deployed-geometry layer inventory (#844 CCB-844-GEOM, partial)

Data-driven layer inventory from the deployed krakow MC truth
(`geant4/data/output_krakow_1M.root`, 1,279,440 Sci_bar hits). Resolves the
audit's "verify 8 B bars + 4 A bars" question directly from the geometry the
production MC actually used.

## Verified: 8 B + 4 A — MATCHES steering

`Sci_bar_LayerID1` is the arm (1 = B, 2 = A); `Sci_bar_LayerID` is the layer
within the arm.

| arm | layers | LayerID range |
|---|--:|---|
| **B** | **8** | 0–7 |
| **A** | **4** | 0–3 |

`verify_8B_4A.matches_steering = true`. Full per-layer depth (global Z), transverse
extent, hit count, and mean Edep in `layer_inventory.json`
(script: `scripts/single_stave/geom_layer_inventory.py`).

## Truth-level stopping/penetration profile (bonus)
The per-layer hit count falls monotonically with depth in the B arm — the direct
penetration signature (particles progressively stop):

```
B layer 0: 290,753 hits   ...   B layer 7: 34,565 hits
```

This is the truth-level stopping profile the #844 stopping-depth study compares
against data. It is a clean truth reference; the data/MC closure still needs the
detector-response chain (thresholds, saturation, trigger mimic) applied.

## Still needed for full CCB-844 (BLOCKED_COMPUTE — needs ROOT/VGM + response)
- Hash the deployed geometry ROOT + enumerate **volumes/materials/densities** via
  ROOT/VGM (this inventory is layer-structure only, from hit truth).
- **Material-budget** ray-trace (areal density per component) — overlap-freedom ≠
  fidelity.
- Apply detector response + trigger mimic and compare **selected/digitized** MC to
  data with χ²/ndf + likelihood GoF. Do NOT reuse the 11.12 g/cm² estimate as a
  calibrated answer.

See `docs/contracts/GEOMETRY_READOUT_MAPPING_CONTRACT.md` for the mapping contract
this inventory feeds.
