# MV0 — Data-driven ADC gain scan

- status: **GATED / MARGINAL DATA/MC PROXY**
- generated: 2026-07-25T16:34:26.765973+00:00
- MC: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root` (48,300 events read)
- data: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz` (377,362 analysis pulses)

This rerun is a source-specific data/MC calibration proxy. It is not an authorized
production calibration and does not supersede canonical `CL-013` without an exact
input manifest, current producer/configuration hashes, accepted selection transfer,
and an uncertainty model under `BLK-MV0-001`.

## Reproduce

```text
mv0_calibrate_from_data.py --mc <root> --data-csv <csv.gz> \
    --truth-npz <npz> --out <dir> --max-events 200000
```

## Key metrics

| quantity | value |
|---|---|
| scan-selected gain | **110.0 ADC/MeV** |
| implied gain (medians) | 131.8 ADC/MeV |
| edep_tot*G variant best gain | 150.0 ADC/MeV |
| pedestal estimate (median baseline) | 6758.5 ADC |
| KS (data vs MC) | 0.10773131550396098 |
| chi2 / ndf (20 bins, [0,7000]) | 49778.92412646382 / 17 = 2928.1720074390482 |
| amp_min cut | 1000.5 ADC |

## Methodology

- Data pulse = peak height (`amplitude_adc`) of one stave channel in one event;
  groups containing `analysis`.
- MC pulse = per-event, per-stave summed B-arm EDep (LayerID→stave) multiplied by
  gain; this is treated as a single-channel analogue of a data pulse.
- Gain is selected by minimizing a two-sample KS statistic after applying the data
  amplitude threshold to the MC proxy.
- `edep_tot*G` pools energy across staves and is not the same observable.

## Comparison to data (global percentiles, ADC)

| percentile | data | MC×G |
|---|---:|---:|
| p5 | 1443 | 2414 |
| p25 | 3081 | 2991 |
| p50 | 5085 | 4383 |
| p75 | 7234 | 6937 |
| p95 | 8815 | 9173 |

## Per-stave KS at the scan-selected gain

| stave | n_data | n_mc | data p50 | MC p50 | KS | implied gain |
|---|---:|---:|---:|---:|---:|---:|
| B2 | 329635 | 47324 | 5698 | 5522 | 0.197 | 114.1 |
| B4 | 27680 | 26047 | 2926 | 3564 | 0.341 | 90.9 |
| B6 | 14242 | 17634 | 2799 | 4904 | 0.603 | 64.1 |
| B8 | 5805 | 12397 | 3142 | 4488 | 0.424 | 78.1 |

## Verdict

- Global KS=0.108 -> **MARGINAL** under this script's own thresholds.
- The very large chi-square per degree of freedom and strongly varying per-stave
  implied gains demonstrate unresolved shape and transfer mismatch.
- The 110 ADC/MeV scan output may be used only to reproduce this Cluster D toy
  chain; it is not an authorized production calibration.

## Open questions

- Data `amplitude_adc` is a peak height, while MC uses integrated EDep×gain.
- The selected CSV and ROOT files are referenced by absolute path and are not
  content-addressed by this report.
- The combined sample does not establish per-sample or per-run transfer.
- Birks quenching and waveform shaping are not closed.
