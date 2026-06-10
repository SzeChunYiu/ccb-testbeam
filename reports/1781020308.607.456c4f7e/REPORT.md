# P08b: charge-current matched waveform PID leakage null

**Ticket:** 1781020308.607.456c4f7e  
**Worker:** testbeam-laptop-1  
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
These are not truth PID labels. They are frozen residual weak labels made only
after exact matching on run, B2 charge bin, total-charge bin, event-current bin,
B2 saturation, pile-up width, depth proxy, and downstream topology. Within each
matched atom the bottom 25% of downstream charge fraction is
`low_downstream_residual_like`, and the top 25% is `high_downstream_residual_like`; atoms with fewer than
8 rows per class are rejected.

The strict matched support contains 2,200 atoms and 270,500
balanced weak-label rows before the run-held-out cap. The held-out benchmark
uses 28,664 rows across 33 runs. Runs with too few held-out examples
in either class are listed in `result.json`.

## Run-Held-Out Benchmark
All scores below are leave-one-run-out predictions with run-block bootstrap 95%
CIs. The traditional score chooses among tail/total, area/peak, a train-only B2
`q_template`, penetration-depth, downstream charge fraction, and DeltaE-like
amplitude-vector scores inside each training fold. The ML score is a
histogram-gradient-boosted classifier over residualized normalized B2 waveform
samples, B2 hand-shape features, and train-only PCA latents; the residualizer is
fit only on training-run nuisance variables.

| method | ROC AUC | AP | purity at 80% high-residual efficiency |
|---|---:|---:|---:|
| traditional frozen cuts | 0.922 [0.892, 0.944] | 0.847 | 0.874 |
| ML residualized waveform HGB | 0.632 [0.616, 0.648] | 0.643 | 0.549 |

Paired run-block bootstrap for ML minus traditional ROC AUC is **-0.290**
with 95% CI **[-0.323, -0.252]**.

## Leakage Hunt
| probe | ROC AUC | AP | interpretation |
|---|---:|---:|---|
| matched-nuisance-only logistic | 0.989 | 0.987 | Failure probe: uses only matched charge/current/depth/topology/saturation/pile-up bins plus event-order nuisance variables; high AUC means coarse matching still leaks. |
| forbidden downstream DeltaE logistic | 0.984 | 0.983 | Ceiling/leakage probe: includes downstream charge and penetration observables used to define the residual weak label. |
| run-only logistic | 0.500 | 0.500 | Strict leave-one-run-out run-id sentinel; unseen held-out runs collapse to the intercept. |
| group/event-order logistic | 0.501 | 0.499 | Sample group plus event-order sentinel for run-family/rate-drift confounding. |
| shuffled-label HGB | 0.496 | 0.496 | Same HGB pipeline with shuffled training labels; should fall near chance. |
| ML-minus-traditional paired run bootstrap | -0.290 |  | Positive values favor ML; CI is stored in result.json. |

The matched-nuisance sentinel is **not** near chance, so the matched atoms are
not sufficient to kill sub-bin charge/current leakage. The forbidden downstream
DeltaE sentinel is allowed to be high because it contains the downstream
residual used to define the weak label. Run/group/event-order performance
quantifies run-family/rate-drift confounding and is near chance here. The
benchmark is B2-event-level, so stave id is constant by construction. The
shuffled-label HGB is the software leakage guardrail.

## Verdict
This is a leakage finding, not a PID claim. The raw reproduction and
run-held-out machinery work, but the nuisance-only AUC is 0.989,
so P08/S15-style weak labels remain dominated by charge/current substructure
even after the coarse matched strata. The forbidden DeltaE AUC is
0.984, and residualized waveform ML is far below the deliberately
strong traditional leakage-aware baseline. No waveform PID adoption claim is
supported without S17 truth and tighter continuous matching.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.py --config configs/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `scoreboard.csv`, `leakage_checks.csv`,
`heldout_run_label_counts.csv`, `traditional_candidate_scan.csv`, and
`ml_fixed_hgb_folds.csv`.
