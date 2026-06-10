# P08b: calibration-backed PID weak-label upgrade

**Ticket:** 1781027807.3490.5cdd4b0b  
**Worker:** testbeam-laptop-1  
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`  
**Constraint:** no Monte Carlo and no truth PID claim.

## Reproduction First
Before any weak-labeling or modeling, the raw ROOT scan reproduced the S00
selected B-stave pulse count exactly:

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

## Calibrated Weak Labels
P08a used direct topology labels (`terminal_b2_like` versus
`penetrating_like`). Here the label is instead a calibrated range-energy
residual: PSTAR converts the nominal B2/B4/B6/B8 depth anchors to proton CSDA
energy anchors, a duplicate odd-readout charge quantile calibration is frozen
on the calibration runs, and the odd-readout energy residual is thresholded
inside each run/depth atom. The bottom 25% is `low_calibrated_range_energy_residual` and the top
25% is `high_calibrated_range_energy_residual`. This is still a weak label, not particle truth.

Labeled support: 289,626 rows from 122 run/depth atoms.
The held-out benchmark evaluates 29,134 balanced rows over 33 runs.

## Run-Held-Out Benchmark
All scores are leave-one-run-out predictions with held-out run-block bootstrap
95% CIs. Traditional uses calibrated even-readout charge-depth variables,
topology, saturation, and range-energy residual features. ML uses normalized B2
waveform samples, hand-shape summaries, and train-only PCA waveform latents.

| method | ROC AUC | AP | purity at 80% high-residual efficiency |
|---|---:|---:|---:|
| traditional calibrated charge-depth logistic | 0.986 [0.977, 0.992] | 0.983 | 0.989 |
| ML raw B2 waveform + PCA latent HGB | 0.986 [0.978, 0.993] | 0.987 | 0.995 |

Paired run-block bootstrap for ML minus traditional ROC AUC is **0.000**
with 95% CI **[-0.003, 0.004]**.

## P08a Comparison
P08a's topology-defined traditional score was AUC 1.000; the
P08a waveform ML score was AUC 0.848. Under this calibrated residual
label, a direct topology-only sentinel is AUC 0.809; the topology
AUC drop relative to P08a's traditional topology proxy is -0.191.
The waveform ML shift relative to P08a is 0.138. That quantifies the
P08a apparent PID signal as mostly topology-label leakage rather than stable
B2 waveform PID information.

## Leakage Hunt
| probe | ROC AUC | AP | interpretation |
|---|---:|---:|---|
| topology-only logistic | 0.809 | 0.740 | Direct P08a-style topology sentinel; high values would mean the calibrated label still leaks penetration topology. |
| even-charge calibration-proxy logistic | 0.985 | 0.983 | Duplicate-readout control: uses only the allowed even-readout version of the odd calibrated label source; high values mean the weak label is mostly charge-scale closure. |
| forbidden odd-energy-label logistic | 0.991 | 0.992 | Ceiling probe using the duplicate odd-readout calibrated residual that defines the weak label. |
| run-only logistic | 0.500 | 0.500 | Strict leave-one-run-out run-id sentinel; unseen held-out runs collapse to the intercept. |
| group/event-order logistic | 0.478 | 0.478 | Sample group plus event-order sentinel for run-family/rate-drift confounding. |
| shuffled-label waveform HGB | 0.488 | 0.475 | Same waveform HGB pipeline with shuffled training labels; should fall near chance. |
| ML-minus-traditional paired run bootstrap | 0.000 |  | Positive values favor waveform/latent ML; CI is stored in result.json. |

The forbidden odd-energy residual probe is expected to be high because it sees
the label source. The even-charge calibration-proxy sentinel explains why the
main AUCs are too good for PID adoption: the duplicate even readout carries the
same calibrated charge-scale residual as the odd weak-label source. The topology
sentinel is the key P08a leakage check, and the shuffled-label HGB is the
software leakage guardrail. The benchmark is B2-event-level, so stave id is
constant by construction.

## Verdict
The calibrated weak label removes the perfect topology shortcut seen in P08a,
but it does not create a PID adoption result. The very high traditional and ML
AUCs are explained by duplicate-readout charge-scale closure, not by independent
particle identity. The B2 waveform/PCA-latent ML result is reported as a
leakage-controlled weak-label stress test only.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py --config configs/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `scoreboard.csv`, `leakage_checks.csv`,
`calibrated_label_support.csv`, `weak_label_counts_by_run.csv`,
`heldout_run_label_counts.csv`, and `ml_fixed_hgb_folds.csv`.
