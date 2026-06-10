# P08c: topology-matched B2 waveform PID null

**Ticket:** 1781027807.3536.50af30a5  
**Worker:** testbeam-laptop-2  
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`  
**Constraint:** no Monte Carlo and no truth PID claim.

## Reproduction First
The raw ROOT scan reproduced the selected-pulse gate before matching or modeling:

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

Using the same raw scan and P08a fold logic, the P08a B2 waveform ML AUC reproduces
as **0.848** versus the reported **0.848** (delta
+0.0000). The reproduced P08a traditional topology-proxy AUC is
**1.000**.

## Matching
P08a labels were frozen: `terminal_b2_like` has B2 selected with zero downstream
selected staves and downstream charge fraction <= 0.08; `penetrating_like` has
B2 selected with at least two downstream selected staves and downstream charge
fraction >= 0.12. P08c matched these labels before model training by exact bins
in run family, log B2 amplitude, log total selected charge, and within-run event
order. The matched benchmark has **174** events across **12**
held-out runs with positive fraction **0.500**.

Post-match balance:

| covariate        |   negative_mean |   positive_mean |   standardized_mean_difference |
|:-----------------|----------------:|----------------:|-------------------------------:|
| log_b2_amplitude |        7.85105  |        7.85273  |                     0.00419807 |
| log_total_charge |        9.78505  |        9.7791   |                    -0.0109444  |
| event_fraction   |        0.490712 |        0.491557 |                     0.00272863 |

## Run-Held-Out Benchmark
All rows are leave-one-run-out predictions with run-block bootstrap 95% CIs.
The traditional method is a train-fold hand-shape logistic score using B2
summary features plus a train-only q-template projection. The ML method uses
normalized B2 waveform samples, the same hand-shape features, and train-only PCA
latents in a histogram-gradient-boosted classifier. Both exclude run id, event
id, downstream topology, total charge, and matching-cell labels.

| method | ROC AUC | AP | purity at 80% weak-penetrator efficiency |
|---|---:|---:|---:|
| traditional hand-shape logistic | 0.988 [0.976, 0.999] | 0.984 | 0.972 |
| ML residual waveform PCA HGB | 0.990 [0.972, 0.999] | 0.991 | 1.000 |
| matched nuisance-only logistic | 0.514 [0.483, 0.551] | 0.519 | 0.489 |
| shuffled-label HGB | 0.497 [0.388, 0.607] | 0.521 | 0.500 |

ML minus traditional AUC is **+0.002** with paired run-block 95% CI
**[-0.012, +0.018]**.

## Leakage Hunt
| probe | ROC AUC | AP | value | interpretation |
|---|---:|---:|---:|---|
| matched nuisance logistic | 0.514 | 0.519 |  | Uses only matched run-family, B2-amplitude, total-charge, and event-order proxies; high AUC means matching did not remove nuisance information. |
| run-only logistic | 0.500 | 0.500 |  | Strict leave-one-run-out run-id sentinel; unseen held-out runs collapse to the intercept. |
| match-cell logistic | 0.500 | 0.500 |  | Uses only the exact matching cell; high AUC means residual cell imbalance remains. |
| shuffled-label HGB | 0.497 | 0.521 |  | Same ML pipeline with shuffled training labels; should stay near chance. |
| matched covariate max abs SMD |  |  | 0.0109 | Post-match standardized mean-difference maximum across log B2 amplitude, log total charge, and event fraction. |
| P08a waveform AUC reproduction | 0.848 | 0.776 | 0.0000 | Raw ROOT reproduction of the upstream P08a waveform number before P08c matching. |
| too-good trigger |  |  | 1.0000 | Triggers when a waveform result exceeds the pre-set AUC threshold or nuisance-only AUC remains high; all leakage probes above are gating checks. |

## Verdict
P08a's B2 waveform separation survives this strict calipered topology match,
but only on a small support island. After matching on run family, B2 amplitude,
total charge, and event order, the B2 waveform ML AUC is **0.990**,
while the traditional hand-shape score is **0.988** and the
nuisance-only sentinel is **0.514**. The too-good trigger is
therefore real and was checked against nuisance-only, run-only, match-cell, and
shuffled-label controls. This remains a support-limited weak-label result, not
event-level PID: the calipered benchmark keeps only 174 events and
still needs external truth or a calibrated non-topology label before adoption.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08c_1781027807_3536_50af30a5_topology_matched_pid_null.py --config configs/p08c_1781027807_3536_50af30a5_topology_matched_pid_null.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `p08a_reproduction/scoreboard.csv`,
`matching_cells.csv`, `matched_balance_smd.csv`, `scoreboard.csv`,
`leakage_checks.csv`, `heldout_run_label_counts.csv`, and
`oof_prediction_preview.csv`.
