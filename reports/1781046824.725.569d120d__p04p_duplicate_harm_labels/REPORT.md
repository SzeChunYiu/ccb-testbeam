# P04p: duplicate-readout charge harm labels

- **Study ID:** P04p
- **Ticket ID:** 1781046824.725.569d120d
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT `HRDv` branches only.
- **Config:** `configs/p04p_1781046824_725_569d120d_duplicate_harm_labels.json`
- **Git commit:** `c31b40fdadff23272b13e3824e769f518c53b38e`

## 0. Question

Can duplicate-readout odd-channel targets identify B2 events where an even-channel template/saturation correction harms charge or timing closure before that correction is used by energy or PID consumers?

## 1. Reproduction

The raw gate is evaluated before any B2-only filtering or odd-target cleaning. It uses the median of samples 0-3 as the per-channel baseline and counts every B2/B4/B6/B8 even-channel pulse with peak amplitude above 1000 ADC.

| quantity                                  |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulse records        |         640737 |       640737 |       0 |           0 | True   |
| P07 Sample-II analysis B2 selected pulses |          88213 |        88213 |       0 |           0 | True   |

## 2. Traditional Method

For event i with even waveform x_i(t), odd duplicate charge y_i, and estimator z_i, the charge closure model is a train-run Huber log-polynomial calibration

`log E[y_i | z_i] = beta_0 + beta_1 log z_i + beta_2 (log z_i)^2 + epsilon_i`,

fit separately inside each leave-one-evaluation-run-out fold. Four non-ML estimators were frozen before model fitting: raw peak, raw positive integral, adaptive-template scale, and a template-only saturation scale that only replaces the raw peak when B2 peak exceeds the saturation proxy. Timing closure is the even CFD20 time minus the odd CFD20 time after subtracting the train-run median offset for the same correction.

| method              |      n |   charge_bias_median_frac |   charge_res68_abs_frac |   timing_abs68_ns |   timing_tail_frac_gt5ns |
|:--------------------|-------:|--------------------------:|------------------------:|------------------:|-------------------------:|
| adaptive_template   | 100107 |                0.0465327  |               0.136246  |         0.487664  |                0.122017  |
| raw_integral        | 100107 |               -0.00469454 |               0.0220078 |         8.21323   |                0.0255883 |
| raw_peak            | 100107 |                0.0172178  |               0.140287  |         0.0802783 |                0.101258  |
| template_saturation | 100107 |                0.01785    |               0.139671  |         0.0918433 |                0.10136   |

The harm label is positive when the production template/saturation correction exceeds the raw-integral closure by at least 5 percentage points in absolute charge error, or worsens the absolute timing residual by at least 1 ns, or has a large template/integral shift in a saturation-support region while charge closure worsens. These labels are targets for training only; the deployed veto features are even-channel summaries.

## 3. ML/NN Methods

All classifiers use a run-held-out split over runs 58-65. Features are the normalized 18-sample even B2 waveform plus even-only support summaries: peak, charge, dynamic-range saturation proxy, baseline excursion, pretrigger RMS, tail/late/early fractions, half-width, plateau count, template scale, template loss, and template/peak log shift. Run id, event id, odd samples, odd charge, and odd time are excluded.

The benchmark includes ridge (`RidgeClassifier` with standardized features), gradient-boosted trees (`HistGradientBoostingClassifier`), MLP (`MLPClassifier`), a PyTorch 1D-CNN, and a new waveform-gated residual tabular network (`wavegate_resnet`) that gates the convolutional waveform embedding by support variables before classification. The shuffled-label sentinel uses the same boosted-tree feature interface.

## 4. Head-to-head Benchmark

A method flags harmful corrections; accepted events are those not flagged. Closure metrics below are computed on accepted events using the same production template/saturation charge and timing residuals. CIs are run-block bootstraps over evaluation runs.

| method                 |   precision |   recall |   accepted_coverage |   accepted_charge_res68_frac |   accepted_timing_abs68_ns |   calibration_ece |   primary_rank |
|:-----------------------|------------:|---------:|--------------------:|-----------------------------:|---------------------------:|------------------:|---------------:|
| gradient_boosted_trees |    0.84233  | 0.94007  |            0.501643 |                    0.0390245 |                  0.0391437 |        0.075071   |              1 |
| mlp                    |    0.943251 | 0.956713 |            0.547085 |                    0.0405507 |                  0.0451776 |        0.00744074 |              2 |
| traditional_rule       |    0.70378  | 0.320702 |            0.796518 |                    0.0785412 |                  0.0380768 |        0.131582   |              3 |
| shuffled_target_gbt    |    0        | 0        |            1        |                    0.111669  |                  0.073175  |        0.0980031  |              4 |
| cnn_1d                 |    0.674114 | 0.879536 |            0.417383 |                    0.0433475 |                  0.0331645 |        0.134831   |              5 |
| ridge                  |    0.671963 | 0.867545 |            0.423487 |                    0.0447361 |                  0.0359249 |        0.168429   |              6 |
| wavegate_resnet        |    0.713003 | 0.840477 |            0.473623 |                    0.0469932 |                  0.0361622 |        0.104288   |              7 |

**Winner:** `gradient_boosted_trees`. The winner is selected by the pre-registered lexicographic criterion: among methods with accepted coverage >= 0.50, minimize accepted charge res68; break ties by timing abs68 and then calibration ECE.

## 5. Falsification

Pre-registration from the ticket: harm-label precision/recall, accepted coverage, charge res68/bias, timing abs68/tail fraction, calibration error, and ML-minus-traditional harm-rate deltas with run-block bootstrap 95% CIs. The explicit falsification test is the shuffled-target sentinel: if it matched the best real model within uncertainty, the claimed waveform/support signal would be rejected.

| method                 |   harm_rate_delta_vs_traditional | ci95                                         |   n_runs |
|:-----------------------|---------------------------------:|:---------------------------------------------|---------:|
| ridge                  |                         0.373031 | [0.34655577502045576, 0.4036440340971456]    |        8 |
| gradient_boosted_trees |                         0.294874 | [0.27435884210700306, 0.3201099155471602]    |        8 |
| mlp                    |                         0.249433 | [0.22620003536426728, 0.2780356976623097]    |        8 |
| cnn_1d                 |                         0.379134 | [0.3397830062489803, 0.4125973441915553]     |        8 |
| wavegate_resnet        |                         0.322895 | [0.2928548322370162, 0.35730388825638826]    |        8 |
| shuffled_target_gbt    |                        -0.203482 | [-0.22821093871135006, -0.17593741867795384] |        8 |

The shuffled-target sentinel has the expected low recall and does not win the closure criterion.

## 6. Threats to Validity

- **Benchmark/selection:** the baseline is not a strawman: it sees peak, integral, adaptive-template scale, template loss, saturation proxy, baseline excursion, and q-template shift, all without odd-target leakage.
- **Data leakage:** every calibration, template, and classifier excludes the held-out run. Odd duplicate variables are used only to define labels and evaluate closure, never as classifier features.
- **Metric misuse:** the report includes label metrics and accepted closure metrics; a high-recall veto that rejects too much data is penalized by the coverage gate.
- **Post-hoc selection:** thresholds and the winner criterion are fixed in the script/config before observing the generated tables. Multiple model attempts are exposed in the same benchmark, and the shuffled-label sentinel is retained.

## 7. Provenance Manifest

`manifest.json` records input ROOT checksums, command, seed, environment, and output hashes.

## 8. Findings and Caveats

The winning harm veto is gradient_boosted_trees: accepted charge res68 0.0390 at coverage 0.502, precision 0.842, recall 0.940, and timing abs68 0.039 ns. The traditional rule gives charge res68 0.0785 at coverage 0.797. The raw reproduction gate matched 640737 selected B-stave pulses exactly.

Systematic caveats: odd duplicate readout is an external closure target, not ground truth energy; the high-amplitude support is B2-only; run-block CIs cover run-to-run variation but not a future detector configuration; timing residuals depend on a CFD20 definition rather than a full pulse fit. The method is therefore a production veto/abstention diagnostic, not an absolute correction-quality oracle.

One follow-up was appended: `1781143765.834.683c6144` / P04q cross-stave harm-veto transfer validation. Its expected information gain is to decide whether the P04p B2 veto is a reusable correction policy or a B2-local saturation artifact by rerunning the same raw ROOT reproduction, run-held-out harm-label benchmark, and odd-duplicate closure metrics for B4/B6/B8 with cross-stave holdout.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04p_1781046824_725_569d120d_duplicate_harm_labels.py --config configs/p04p_1781046824_725_569d120d_duplicate_harm_labels.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `correction_method_metrics.csv`, `harm_method_metrics.csv`, `harm_method_by_run.csv`, `harm_rate_deltas.csv`, `leakage_checks.json`, and `prediction_sanity_by_run.csv`.
