# MV0 -- Data-Driven ADC Gain Calibration

- status: **PRODUCTION**
- generated: 2026-07-25T16:34:26.765973+00:00
- MC: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root` (48300 events read)
- data: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz` (377362 analysis pulses)

## Reproduce
```
mv0_calibrate_from_data.py --mc <root> --data-csv <csv.gz> \
    --truth-npz <npz> --out <dir> --max-events 200000
```

## Key metrics
| quantity | value |
|---|---|
| best-fit gain | **110.0 ADC/MeV** |
| implied gain (medians) | 131.8 ADC/MeV |
| edep_tot*G variant best gain | 150.0 ADC/MeV |
| pedestal estimate (median baseline) | 6758.5 ADC |
| KS (data vs MC) | 0.1077 |
| chi2 / ndf (20 bins, [0,7000]) | 49778.9 / 17 = 2928.17 |
| amp_min cut | 1000.5 ADC |

## Methodology
- Data pulse = peak height (`amplitude_adc`) of one stave channel in one event; groups containing `analysis`.
- MC pulse = per-event, per-stave summed B-arm EDep (LayerID->stave) * gain; the single-channel analogue of a data pulse.
- Gain found by minimizing the KS statistic between MC*G and data pulse-height distributions (grid then fine scan); MC pulses below the data amp_min are cut to match selection.
- `edep_tot*G` per-track variant reported for transparency; it pools energy across staves and so is NOT a single-channel pulse analogue (recovers a different, lower gain).

## Comparison to data (global percentiles, ADC)
| pctl | data | MC*G |
|---|---|---|
| p5 | 1443 | 2414 |
| p25 | 3081 | 2991 |
| p50 | 5085 | 4383 |
| p75 | 7234 | 6937 |
| p95 | 8815 | 9173 |

## Per-stave KS at best gain
| stave | n_data | n_mc | data p50 | MC p50 | KS | implied gain |
|---|---|---|---|---|---|---|
| B2 | 329635 | 47324 | 5698 | 5522 | 0.197 | 114.1 |
| B4 | 27680 | 26047 | 2926 | 3564 | 0.341 | 90.9 |
| B6 | 14242 | 17634 | 2799 | 4904 | 0.603 | 64.1 |
| B8 | 5805 | 12397 | 3142 | 4488 | 0.424 | 78.1 |

## MC verdict
- Global KS=0.108 -> **MARGINAL** (PASS<0.10, MARGINAL<0.20).
- Calibrated gain 110 ADC/MeV written to calibration.json; downstream digitizer studies (MV4 timing) read this card.

## Open questions
- Data amplitude_adc is peak height; MC uses integrated EDep*G (shape factor absorbed into gain). A full shaped-waveform peak (MV4 digitizer) would refine the gain definition.
- MC is a single beam configuration; per-sample (I/II) data split not separately reproducible here -- combined-analysis data used as target.
- Birks quenching is off in the digitizer config; residual high-amplitude tension may indicate quenching is needed for the most-ionizing (deuteron) pulses.
