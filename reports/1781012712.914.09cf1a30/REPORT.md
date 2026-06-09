# P08a: penetration-depth weak-label PID null test

**Ticket:** 1781012712.914.09cf1a30  
**Worker:** testbeam-laptop-4  
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`

## Reproduction First
Before weak-labeling or modeling, the raw ROOT scan reproduced the S00 selected
B-stave pulse count exactly:

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

## Weak Labels
These are not truth PID labels. They are frozen topology/charge-consistency
proxies:

- `terminal_b2_like`: B2 selected, zero downstream selected staves, downstream charge
  fraction <= 0.08.
- `penetrating_like`: B2 selected, at least 2 downstream selected staves, downstream
  charge fraction >= 0.12.

The held-out benchmark uses 19,606 balanced events across 32 runs. Runs
with too few held-out examples in either class are listed in `result.json`.

## Run-Held-Out Benchmark
All scores below are leave-one-run-out predictions with run-block bootstrap 95%
CIs. The traditional score chooses among tail/total, area/peak, a train-only B2
`q_template`, and a DeltaE-like amplitude-vector score inside each training
fold. The ML score is a histogram-gradient-boosted classifier over raw normalized B2 waveform samples,
B2 hand-shape features, and train-only PCA latents; it excludes run id, event
order, downstream presence/depth, stave id, and total charge.

| method | ROC AUC | AP | purity at 80% weak-penetrator efficiency |
|---|---:|---:|---:|
| traditional frozen cuts | 1.000 [1.000, 1.000] | 1.000 | 1.000 |
| ML raw/PCA waveform HGB | 0.848 [0.833, 0.861] | 0.776 | 0.598 |

Paired run-block bootstrap for ML minus traditional ROC AUC is **-0.152**
with 95% CI **[-0.166, -0.139]**.

## Leakage Hunt
| probe | ROC AUC | AP | interpretation |
|---|---:|---:|---|
| charge/depth logistic | 1.000 | 1.000 | Forbidden ceiling: includes depth and presence fields used directly by the weak-label definition. |
| run-only logistic | 0.448 | 0.303 | Strict leave-one-run-out run-id sentinel; unseen held-out runs collapse to the intercept. |
| group/event-order logistic | 0.602 | 0.426 | Sample group plus event-order sentinel for run-family/rate-drift confounding. |
| shuffled-label HGB | 0.489 | 0.368 | Same HGB pipeline with shuffled training labels; should fall near chance. |
| ML-minus-traditional paired run bootstrap | -0.152 |  | Positive values favor ML; CI is stored in result.json. |
| all-data P01b latent logistic | 0.703 | 0.580 | Diagnostic only; P01b release encoder was fit on all selected pulses and is not used for the main claim. |

The charge/depth sentinel is intentionally near-perfect because the weak labels
are defined from penetration topology. Run/group/event-order performance
quantifies Sample-I/Sample-II and rate-drift confounding. The benchmark is
B2-event-level, so stave id is constant by construction rather than available
as a feature. The shuffled-label HGB is the software leakage guardrail.

## Verdict
This is a null/guardrail result, not a PID claim. The weak labels are reproducible
and useful for stress-testing, but the charge/depth sentinel dominates the task.
The B2 waveform ML model does not establish stable PID-like information beyond
the topology and charge proxies; adoption should wait for calibrated S14/S15
energy or external truth labels.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08a_1781012712_914_09cf1a30_penetration_weak_pid.py --config configs/p08a_1781012712_914_09cf1a30.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `scoreboard.csv`, `leakage_checks.csv`,
`heldout_run_label_counts.csv`, `traditional_candidate_scan.csv`, and
`ml_fixed_hgb_folds.csv`.
