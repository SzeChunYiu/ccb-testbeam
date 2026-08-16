# S13: current-scaling and CWoLa architecture bakeoff

- **Ticket:** `#2388`
- **Worker:** `testbeam-laptop-3`
- **Data:** raw B-stack ROOT under `/home/billy/ccb-data/data/extracted/root/root`
- **Primary metric:** pooled out-of-block held-out current AUC, with run-bootstrap 95% CIs.
- **Winner:** `mlp` with AUC 0.6757 [0.5992, 0.7103].

## 1. Reproduce-first gate

Before any new model comparison, the S10/App. H low-current-trained pile-up score ratio was rerun from raw ROOT using the same B-stack pulse selection: per-channel baseline is the median of samples 0-3, and selected pulses require pedestal-subtracted amplitude greater than 1000 ADC in B2/B4/B6/B8.

| quantity                                             |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| S10 low-current-trained ML score high/low mean ratio |         1.297  |     1.29708  |  7.57958e-05 |       0.005 | True   |
| S10 low-current ML score mean                        |         0.1213 |     0.121349 |  4.91622e-05 |       0.002 | True   |
| S10 high-current ML score mean                       |         0.1574 |     0.157399 | -9.38868e-07 |       0.002 | True   |

The reproduced CWoLa-scale held-out AUC target is App. H `0.676`; the best new out-of-block AUC differs by -0.0003. The reproduced S10 low/high score means are 0.12135 and 0.15740.

## 2. Current-scaling observables

For each run, let \(N_r\) be events with at least one selected B-stack pulse and \(M_r\) a topology count. The raw current comparison reports \(f_r=M_r/N_r\), pooled by current with selected-event weights. The traditional current-scaling fit uses

\[ f(I)=f_0+kI, \qquad (f_0,k)=\arg\min_{f_0,k}\sum_r N_r\{f_r-(f_0+kI_r)\}^2 . \]

| metric                         |   low_rate_pct |   high_rate_pct |   high_over_low |   high_minus_low_pct |
|:-------------------------------|---------------:|----------------:|----------------:|---------------------:|
| downstream_per_selected_event  |        2.31244 |         3.34141 |         1.44497 |              1.02897 |
| multi_stave_per_selected_event |        1.55875 |         2.68063 |         1.71973 |              1.12188 |
| three_stave_per_selected_event |        0.4111  |         0.85379 |         2.07684 |              0.44269 |

| metric                         |   f0_pct |   k_pct_per_nA |   pred_2nA_pct |   pred_20nA_pct |   weighted_rmse_pct |
|:-------------------------------|---------:|---------------:|---------------:|----------------:|--------------------:|
| downstream_per_selected_event  | 2.19811  |      0.0571653 |        2.31244 |         3.34141 |            1.2819   |
| multi_stave_per_selected_event | 1.4341   |      0.0623265 |        1.55875 |         2.68063 |            1.07002  |
| three_stave_per_selected_event | 0.361912 |      0.0245939 |        0.4111  |         0.85379 |            0.335233 |

The downstream topology ratio reproduces the earlier S13b value near 1.445. The fold-local high-current downstream fractions span the same scale as the ticket's raw multi-stave comparison: the B-to-A block is the high-downstream 2.69-like regime, while the A-to-B block is closer to 1.19, exposing the run-composition systematic.

## 3. Model benchmark

All learned models receive normalized 18-sample waveform values and transparent pulse summaries: log amplitude, peak sample, area-over-peak, early/tail/late fractions, post-peak minimum fraction, negative-step count, width above 10% and 20% of peak, and final-sample fraction. Run, event number, current label, downstream topology, and event multiplicity are excluded. The strong traditional comparator is a train-only single-feature logistic score selected inside each fold; it is intentionally simple, auditable, and resistant to hidden topology leakage.

The ridge model is L2 logistic regression. The gradient-boosted-tree model is histogram gradient boosting. The MLP is a two-layer tabular network. The 1D-CNN convolves the normalized waveform and concatenates scalar summaries. The new `hybrid_residual_cnn_new` gates convolutional channels with scalar pulse-shape context and appends residual waveform moments, testing whether local pulse residuals add information beyond the standard CNN.

The two folds are run-block transfers: A-to-B trains on low run 46 plus high runs 44,45,48-51 and tests on low run 47 plus high runs 52-57; B-to-A reverses this. Bootstrap intervals resample held-out source runs with replacement.

| method                   |      auc |   auc_ci_low |   auc_ci_high |       ap |    brier |   score_high_over_low |   score_high_over_low_ci_low |   score_high_over_low_ci_high |   n_scored_pulses |
|:-------------------------|---------:|-------------:|--------------:|---------:|---------:|----------------------:|-----------------------------:|------------------------------:|------------------:|
| mlp                      | 0.675682 |     0.599179 |      0.710322 | 0.957525 | 0.277564 |               1.2963  |                     1.21009  |                       1.34118 |             43403 |
| hybrid_residual_cnn_new  | 0.669252 |     0.55769  |      0.718411 | 0.957612 | 0.259397 |               1.21767 |                     1.12739  |                       1.26213 |             43403 |
| gradient_boosted_trees   | 0.657182 |     0.637216 |      0.67673  | 0.955074 | 0.284605 |               1.35602 |                     1.31175  |                       1.39342 |             43403 |
| ridge                    | 0.646267 |     0.594894 |      0.677661 | 0.953916 | 0.270415 |               1.19872 |                     1.16239  |                       1.22562 |             43403 |
| one_dimensional_cnn      | 0.642911 |     0.616755 |      0.681997 | 0.954253 | 0.270926 |               1.18189 |                     1.14188  |                       1.2843  |             43403 |
| traditional_single_shape | 0.63296  |     0.34625  |      0.750053 | 0.941666 | 0.262164 |               1.07045 |                     0.980147 |                       1.10447 |             43403 |

Against the traditional comparator AUC 0.6330 [0.3463, 0.7501], the winner improves by 0.0427 AUC. This answers the ticket question narrowly: ML does add current-discrimination information beyond a transparent one-feature waveform baseline, but the gain is a weak-supervision diagnostic, not a calibrated pile-up fraction.

## 4. Fold diagnostics

| fold   | method                   |      auc |   auc_ci_low |   auc_ci_high |   score_high_over_low |    brier |   n_scored_pulses |
|:-------|:-------------------------|---------:|-------------:|--------------:|----------------------:|---------:|------------------:|
| A_to_B | mlp                      | 0.64741  |     0.622636 |      0.669007 |              1.29253  | 0.293016 |             22970 |
| A_to_B | one_dimensional_cnn      | 0.644448 |     0.626967 |      0.662125 |              1.18213  | 0.26398  |             22970 |
| A_to_B | gradient_boosted_trees   | 0.643921 |     0.622445 |      0.659524 |              1.36193  | 0.29306  |             22970 |
| A_to_B | hybrid_residual_cnn_new  | 0.628338 |     0.604719 |      0.655507 |              1.18923  | 0.280054 |             22970 |
| A_to_B | ridge                    | 0.617634 |     0.59136  |      0.646218 |              1.18652  | 0.278095 |             22970 |
| A_to_B | traditional_single_shape | 0.555229 |     0.520604 |      0.599448 |              1.08449  | 0.272598 |             22970 |
| B_to_A | mlp                      | 0.680089 |     0.651247 |      0.704706 |              1.25025  | 0.260194 |             20433 |
| B_to_A | gradient_boosted_trees   | 0.670059 |     0.637294 |      0.700842 |              1.34321  | 0.275101 |             20433 |
| B_to_A | one_dimensional_cnn      | 0.66734  |     0.640114 |      0.695239 |              1.24232  | 0.278734 |             20433 |
| B_to_A | ridge                    | 0.666197 |     0.633614 |      0.696732 |              1.21072  | 0.261782 |             20433 |
| B_to_A | hybrid_residual_cnn_new  | 0.665833 |     0.646541 |      0.684861 |              1.19706  | 0.236176 |             20433 |
| B_to_A | traditional_single_shape | 0.589668 |     0.568265 |      0.606856 |              0.999039 | 0.250433 |             20433 |

## 5. Systematics and caveats

The limiting systematic is current support: only runs 46 and 47 are low-current runs, so each transfer fold has a single low-current acquisition block. Run-bootstrap CIs preserve the source-run unit but cannot create missing low-current diversity. The high-current set also mixes topology regimes; this is why the transparent downstream ratio ranges from about 1.19 to 2.69 by block.

CWoLa labels are weak labels. A classifier can learn current-correlated morphology, trigger acceptance, or DAQ state rather than beam pile-up. For that reason, the result is interpreted as a current-shape discrimination benchmark. It should not be used as an event-level pile-up probability without external labels or a stricter nuisance-matched residual analysis.

The traditional \(f(I)\) fit has only two current settings, so it is a contrast summary rather than a validated response curve. The neural models are compact and regularized to match the available run support; larger architectures would mainly increase variance under this split.

## 6. Leakage and provenance

| fold   | check                      | value            | flag   | note                                                                      |
|:-------|:---------------------------|:-----------------|:-------|:--------------------------------------------------------------------------|
| A_to_B | train_test_run_overlap     | 0                | False  | Run split must be disjoint.                                               |
| A_to_B | forbidden_columns_used     | 0                | False  | Model features exclude run, eventno, current labels, and topology labels. |
| A_to_B | traditional_feature_choice | width_10_samples | False  | Train-only selected feature, sign=-1.0, train_auc=0.658.                  |
| B_to_A | train_test_run_overlap     | 0                | False  | Run split must be disjoint.                                               |
| B_to_A | forbidden_columns_used     | 0                | False  | Model features exclude run, eventno, current labels, and topology labels. |
| B_to_A | traditional_feature_choice | tail_fraction    | False  | Train-only selected feature, sign=1.0, train_auc=0.626.                   |

No forbidden identifier or target columns enter the model feature matrices. `input_sha256.csv` pins every raw ROOT file. `manifest.json` records command, git commit, software versions, random seed, input hashes, and output hashes.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s13_2388_current_cwola_architecture_bakeoff.py --config configs/s13_2388_current_cwola_architecture_bakeoff.json
```

Runtime: 133.6 s.
