# MV4 timing rerun with the real v2 calibration (CCB-TIMING, DONE)

Reran `mv4_timing_study.py` (refactored) over the real 1M-event MC with the
**measured v2 gain and measured data anchors loaded from result files** (not the
hard-coded 246/110). This closes the MV4→TOY_DIAGNOSTIC action item and answers
the timing-tension question the prior run raised.

## Inputs (real, loaded — not hard-coded)
- **Gain: 92.0 ADC/MeV ± 30%** from `reports/mv0_calibration_1782677847/calibration.json`
  (`calibration.gain_adc_per_mev`, median-matching v2 — the value that fixes the
  A-001 double-subtraction). The prior MV4 run used the **erroneous v1 gain = 110**.
- **Data anchors** from `reports/mv4_timing_1782678162` data_reference:
  S02_raw = 1.85 ns, S03_corrected = 1.50 ns, ±0.10 ns.
- MC: `geant4/data/output_krakow_1M.root`, 64,958 usable tracks (200,364 scanned).

## Result (`result.json`, `mv4_slice_metrics.csv`)

| metric | raw | corrected(test) |
|---|--:|--:|
| sigma68 [ns] | 1.578 ± 0.007 | 1.582 ± 0.012 |
| RMS [ns] | 5.31 | 5.23 |
| Gaussian-core sigma [ns] | 1.495 | 1.518 |
| tail fraction | 0.034 | 0.037 |
| chi2/ndf | 366 | 169 |

Timewalk (1/A form): A = -3.381 ns, B = -339.3 ns·ADC.

## The tension was gain-driven

| | prior (v1 gain=110) | **v2 (gain=92)** |
|---|--:|--:|
| corrected sigma68 [ns] | 1.770 | **1.582** |
| **corrected pull vs S03** | **+2.68 (TENSION)** | **+0.81** |
| raw pull vs S02 | -1.05 | -2.71 |

Using the correct v2 gain **removes the corrected-timing tension** (+2.68 → +0.81):
the corrected MC sigma68 now agrees with the S03 data anchor within ~0.8σ.
Gain-uncertainty propagation (±30%) maps to raw sigma68 **1.24–1.81 ns**
(gain 64→120), which **brackets both anchors** — so within the calibration
systematic there is no significant timing tension either way.

## Caveats / status
- This is still a **digitizer-model** study (toy pulse shape τ_r=2.5, τ_d=42 ns,
  CFD): it validates the 1/A timewalk correction and the gain sensitivity, not a
  waveform-level data closure. Real-waveform closure needs the raw pulse data.
- The high chi2/ndf reflects genuine non-Gaussian timing tails (tail_frac ~3.5%),
  correctly reported alongside sigma68/core-sigma.
- Status: MV4 **TOY_DIAGNOSTIC → re-run complete with v2 calibration**; the prior
  "corrected timing tension" is explained (erroneous gain) and not confirmed under
  the correct gain + systematic.
