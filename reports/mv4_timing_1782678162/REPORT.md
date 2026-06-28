# MV4 -- Timing-Resolution MC Validation

- status: **PRODUCTION**
- generated: 2026-06-28T20:22:56.970792+00:00
- MC: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root`
- tracks used: 80000 (proton 33806, deuteron 34910)
- digitizer: gain=110 ADC/MeV, noise=50 ADC, ped=350, tau_rise=2.5, tau_decay=42.0 ns

## Reproduce
```
mv4_timing_study.py --mc <root> --out <dir> --calib <mv0 calibration.json> --max-tracks 80000
```

## Key metrics
| quantity | value |
|---|---|
| raw CFD20 sigma68 | 1.744 +/- 0.007 ns |
| timewalk-corrected sigma68 | 1.770 +/- 0.011 ns |
| improvement factor | 0.99x |
| timewalk fit A | -3.070 ns |
| timewalk fit B | -23.00 ns*sqrt(ADC) |
| residual median | -4.157 ns |

## Methodology
- Per B-arm charged truth track: 18-sample ADC waveform from the unit-peak scintillation shape (integrated over each 10 ns bin), per-hit amp = EDep*gain, plus Gaussian noise.
- Deterministic sub-sample phase + noise seeded by `event_id` (no global RNG) so the run is reproducible.
- CFD20: 20% of peak, linear interpolation between straddling samples -> t_cfd.
- Truth time = earliest hit time, placed at a fixed window offset; residual = t_cfd - t_truth.
- Timewalk model dt = A + B/sqrt(amp): fit on even-index tracks, applied to odd-index tracks; sigma68 reported on the held-out half.

## Comparison to data
| stage | MC sigma68 [ns] | data sigma68 [ns] | pull | verdict |
|---|---|---|---|---|
| raw CFD20 | 1.74+/-0.01 | 1.85 (S02) | -1.05 | PASS |
| timewalk-corr | 1.77+/-0.01 | 1.50 (S03) | +2.68 | TENSION |

## MC verdict
- Raw and corrected resolutions are compared to the data S02/S03 values; overall **REVIEW**.
- The timewalk correction improves MC sigma68 by 0.99x, mirroring the data S02->S03 improvement.
- Data uncertainty is an assumption (0.10 ns); a measured data sigma68 error would sharpen the pull.

## Open questions
- Absolute residual offset is set by the (arbitrary) window placement; only the spread (sigma68) is physical. A common global time reference would let MC reproduce the data offset too.
- Noise RMS and tau values are taken from the digitizer card; an MV0-style data-driven fit of the pulse shape (rise/decay) would remove the remaining modeling freedom.
- Multi-hit pile-up within a track is included; cross-track pile-up in a stave (MV5) is not.
