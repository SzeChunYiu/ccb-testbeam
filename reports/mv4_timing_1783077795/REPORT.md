# MV4 -- Timing-Resolution MC Validation

> **NOTE (EXTERNAL_REVIEW_2026-07-02.md):** all digitizer ADC/MeV gains are **RETRACTED**. The default gain used here only sets the amplitude/noise scale of the toy digitizer; **no ADC/MeV physics claim is made**.

- status: **REVIEW**
- generated: 2026-07-03T11:23:36.654308+00:00
- MC: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root`
- tracks used: 80000 (proton 34027, deuteron 35503)
- digitizer: gain=92 ADC/MeV, noise=50 ADC, ped=350, tau_rise=2.5, tau_decay=42.0 ns

## Reproduce
```
mv4_timing_study.py --mc <root> --out <dir> --calib <mv0 calibration.json> --max-tracks 80000
```

## Key metrics
| quantity | value |
|---|---|
| raw CFD20 sigma68 | 1.476 +/- 0.007 ns |
| timewalk-corrected sigma68 | 1.481 +/- 0.009 ns |
| improvement factor | 1.00x |
| timewalk fit A | -3.524 ns |
| timewalk fit B | 39.60 ns*ADC (1/A form) |
| residual median | -3.881 ns |

## Methodology
- Per B-arm charged truth track: 18-sample ADC waveform from the unit-peak scintillation shape (integrated over each 10 ns bin), per-hit amp = EDep*gain, plus Gaussian noise.
- Deterministic sub-sample phase + noise seeded by `event_id` (no global RNG) so the run is reproducible.
- CFD20: rising-edge constrained -- find the peak sample, scan backward from the peak for the last prev < thr <= cur crossing (thr = 20% of peak), linear interpolation -> t_cfd. (Fixed 2026-07-03: the old forward-from-sample-0 scan fired on pre-signal noise crossings.)
- Truth time = earliest hit time, placed at a fixed window offset; residual = t_cfd - t_truth.
- Timewalk model dt = A + B/amp (physical 1/A leading-edge form, MV4b fix 2026-07-01): fit on even-index tracks, applied to odd-index tracks; sigma68 reported on the held-out half.

## Comparison to data (unmatched -- see verdict)
- The MC residual is **single-trace** (t_cfd - t_truth); the data anchors are pooled two-stave **pair-difference** sigma68s. MC is converted to pair-equivalent via `mc_sigma * sqrt(2)` (assumes independent stave errors).
- Data anchor: raw CFD20 pair-difference sigma68 = 2.993 ns (S02 head_to_head_benchmark.csv, row cfd20_reference); ML-corrected reference = 1.50 ns (S03).
- The data sigma68 uncertainty is not measured, so **no pull is computed**; the ratio error below is the MC bootstrap error only.

| stage | MC single-trace [ns] | MC pair-equiv [ns] | data pair-diff [ns] | MC/data ratio |
|---|---|---|---|---|
| raw CFD20 | 1.476+/-0.007 | 2.087+/-0.009 | 2.993 (S02) | 0.697+/-0.003 |
| timewalk-corr | 1.481+/-0.009 | 2.094+/-0.012 | 1.50 (S03) | 1.396+/-0.008 |

## MC verdict
- **REVIEW — unmatched comparison (merged-track MC vs per-stave data; selection unmatched; gain retracted); matched per-stave rerun pending Phase 1 digitizer**
- The ratio quantifies agreement scale only; it is not a hypothesis test. A matched comparison requires a per-stave MC digitization with the data selection applied.

## Open questions
- Absolute residual offset is set by the (arbitrary) window placement; only the spread (sigma68) is physical. A common global time reference would let MC reproduce the data offset too.
- Noise RMS and tau values are taken from the digitizer card; an MV0-style data-driven fit of the pulse shape (rise/decay) would remove the remaining modeling freedom.
- Multi-hit pile-up within a track is included; cross-track pile-up in a stave (MV5) is not.
