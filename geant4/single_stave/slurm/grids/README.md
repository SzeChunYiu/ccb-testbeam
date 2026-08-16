# SiPM sensitivity grids (SIPM-P2-001)

One-knob-at-a-time sweep grids for the single-stave Geant4 sim with the
integrated clean-room `ccb-sipm-core`. Every grid is **regenerated** by
`generate_points.py`; the committed `points_<knob>.csv` are the default
emission. Override any grid with `CCB_GRID_<NAME="v0 v1 ..."` before running
the generator.

## Knob catalogue

| knob | channel | target | unit | default grid | rationale |
|------|---------|--------|------|--------------|-----------|
| `pde_scale` | cli | `--pde-scale` | x PDE table | 0.6 0.8 1.0 1.2 1.4 | +/-40% spans the S13360-3050CS OV range + per-device PDE spread (~25-50% peak) |
| `collection_efficiency` | cli | `--collection-efficiency` | frac | 0.5 0.7 0.85 0.95 1.0 | post-transport collection efficiency in [0,1]; 0.5 = poor, 1.0 = ideal |
| `recovery_time` | env | `CCB_SIPM_RECOVERY_TIME_NS` | ns | 5 15 30 60 100 | microcell RC recovery (S13360-3050CS tens of ns) |
| `dark_count` | env | `CCB_SIPM_DARK_COUNT_RATE_HZ` | Hz | 0 1e5 5e5 1e6 2e6 | dark-count rate; 0 = cold, 2 MHz = hot/irradiated |
| `crosstalk` | env | `CCB_SIPM_CROSSTALK_PROB` | prob | 0 0.03 0.06 0.10 0.15 | prompt crosstalk; ~3% typ, swept 0-15% |
| `afterpulse` | env | `CCB_SIPM_AFTERPULSE_FAST_PROB` | prob | 0 0.01 0.03 0.05 0.08 | fast afterpulse; ~1% nominal, 0-8% irradiated |
| `window_end` | env | `CCB_SIPM_WINDOW_END_NS` | ns | 50 100 250 500 1000 | integration window; signal completeness vs dark noise |
| `birks_kB` | cli | `--birks-kB` | mm/MeV | 0 0.08 0.126 0.17 0.22 | Birks constant; 0 = no quench, 0.126 nominal, 0.22 heavy |
| `reflectivity` | cli | `--reflectivity-scale` | x TiO2 | 0.6 0.8 0.9 1.0 1.05 | TiO2 reflectivity; 0.6 degraded - 1.05 upper tolerance |
| `attenuation` | cli | `--attenuation-scale` | x len | 0.5 0.75 1.0 1.5 2.0 | Y-11 attenuation-length scale; 0.5 high loss - 2.0 low loss |
| `far_end` | cli | `--far-end` | mode | absorb open mirror instrumented | far-end boundary; near/far light splitting |
| `sipm_n_cells` | cli | `--sipm-n-cells` | cells | 1600 2500 3600 4900 6400 | microcell count (saturation); S13360-3050CS = 3600 |

The representative operating point for every sweep is the `ccb-sipm-core`
`ModelConfig::RepresentativeS13360_3050CS` + `AppConfig` defaults (PDE scale 1,
collection_efficiency 1, recovery 30 ns, dark 0.5 MHz, crosstalk 3%, afterpulse 1%,
window 250 ns, Birks 0.126, etc.).

## Defaults provenance

- ADC mapping: `adc[i] = clip(baseline + analog_pe/adc_lsb_pe, 0, 2^adc_bits-1)`
  with baseline 200, adc_lsb_pe 0.01, 12 bits -> clip ceiling 3895 above
  baseline. The representative 100 MeV testbeam point **saturates** the ADC, so
  the campaign beam point is chosen (see campaign SUMMARY) to keep the default
  ADC in its linear range; 100 MeV saturation is reported as a finding.
- Events/point: `CCB_CAMPASSIGN_NEVENTS` (default 60) — a sensitivity scan, not
  production. Each 100 MeV proton event already yields O(1e2) detected PE.

## Regenerating

```bash
python3 generate_points.py                       # all knobs, default ranges
CCB_GRID_CROSSTALK="0 0.05 0.1 0.2" \
  python3 generate_points.py --knobs crosstalk     # custom crosstalk grid
```

## Paired multi-seed design (#984 / AF-036)

`generate_points.py` emits a **common-random-number** grid: each replicate seed
is reused at every knob value. Labels encode `knob=value__rep=<seed>`. See
`PAIRED_SEED_DESIGN.json` for the explicit `(knob, value, replicate_seed)`
triples. Analyzers must estimate nuisance-response uncertainty from seed-level
paired effects, not only per-event SEM.
