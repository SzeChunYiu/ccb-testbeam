# P13b rare-atom bootstrap promotion threshold

- **Study ID:** P13b
- **Ticket:** `1781055420.689.3cc21a6b`
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-11
- **Depends on:** S03/S10/S16/P04/P07/P09/P12 rare-atom families, S00 raw selected-pulse gate
- **Input checksum(s):** see `input_sha256.csv`
- **Git commit:** `1ab2cbba1d3af27f118958d06aa7df6a3b1576a5`
- **Config:** `configs/p13b_1781055420_689_3cc21a6b_rare_atom_bootstrap_promotion_threshold.json`

## Abstract

This study converts the project's recurring low-count pulse atoms into a promotion decision: promote a rare atom to a steering variable, defer it as a diagnostic-only observation, or reject it as a control failure.  The raw B-stack selected-pulse count is reproduced exactly from ROOT before any modeling.  The benchmark winner stored in `result.json` is **gradient_boosted_trees**, with promotion utility 1.014 [0.829, 1.141], false-promotion rate on nominal controls 0.000, and average precision 0.912.

## 0. Question

What minimum support, run stability, endpoint safety, and control-passing criteria are required before rare pulse atoms such as delayed peaks, saturation-boundary cells, baseline excursions, dropout subclasses, q-template shifts, and S03f-style rare topologies may be used as steering variables?

## 1. Reproduction From Raw ROOT

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| S00 selected B-stave pulse records | 640737 | 640737 | 0 | 0 | True |

The reproduced number is obtained by scanning `HRDv` in each raw B-stack ROOT file, subtracting the median of samples 0--3 independently per channel, and counting all B2/B4/B6/B8 pulses with baseline-subtracted amplitude `A > 1000 ADC`.  This is the S00 gate used throughout the repository.

## 2. Traditional Promotion Method

For each atom `a`, stave `s`, and run `r`, let `n_{a,s,r}` be selected pulse support.  The global effective run count is

`N_eff(a,s) = (sum_r n_{a,s,r})^2 / sum_r n_{a,s,r}^2`.

The frozen transparent rule promotes an atom/stave pair only if all criteria pass: total support >= 80, `N_eff >= 4.0`, runs present >= 5, maximum single-run fraction <= 0.45, exact-binomial prevalence CI width <= 0.08, endpoint harm rate <= 0.22, harm-rate CI upper bound <= 0.34, and Sample-I/Sample-II support imbalance <= 0.35.  The scorecard probability used in the head-to-head benchmark is the product of normalized support, run-balance, CI-width, harm, and sample-balance factors, with nominal controls forced toward zero.

| atom | stave | n_total | runs_present | effective_runs | max_run_fraction | support_ci_width | harm_rate | harm_ci | traditional_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| saturation_boundary | B8 | 2467 | 32 | 9.31 | 0.179 | 0.0123 | 0.116 | [0.104, 0.129] | promote |
| saturation_boundary | B2 | 436614 | 33 | 19.50 | 0.104 | 0.0023 | 0.054 | [0.053, 0.055] | defer |
| secondary_delayed_peak | B2 | 137341 | 33 | 27.43 | 0.053 | 0.0019 | 0.339 | [0.337, 0.342] | defer |
| baseline_excursion | B2 | 23032 | 33 | 24.29 | 0.071 | 0.0009 | 0.896 | [0.892, 0.900] | defer |
| secondary_delayed_peak | B4 | 21144 | 33 | 12.23 | 0.145 | 0.0078 | 0.502 | [0.495, 0.509] | defer |
| rare_s03f_topology | B6 | 14820 | 33 | 10.38 | 0.156 | 0.0106 | 0.323 | [0.316, 0.331] | defer |
| rare_s03f_topology | B4 | 14681 | 33 | 10.35 | 0.157 | 0.0071 | 0.454 | [0.446, 0.462] | defer |
| dropout_subclass | B2 | 14633 | 33 | 23.02 | 0.080 | 0.0007 | 0.939 | [0.935, 0.943] | defer |
| qtemplate_shift_proxy | B2 | 13668 | 33 | 22.66 | 0.082 | 0.0007 | 0.964 | [0.961, 0.967] | defer |
| saturation_boundary | B4 | 10277 | 33 | 15.30 | 0.130 | 0.0062 | 0.127 | [0.121, 0.134] | defer |
| secondary_delayed_peak | B6 | 10095 | 33 | 11.52 | 0.147 | 0.0097 | 0.426 | [0.417, 0.436] | defer |
| delayed_peak | B2 | 6229 | 33 | 24.46 | 0.064 | 0.0005 | 0.187 | [0.177, 0.197] | defer |
| rare_s03f_topology | B8 | 5591 | 33 | 9.47 | 0.172 | 0.0159 | 0.397 | [0.385, 0.410] | defer |
| delayed_peak | B4 | 5433 | 33 | 27.30 | 0.052 | 0.0047 | 0.565 | [0.551, 0.578] | defer |
| secondary_delayed_peak | B8 | 4167 | 33 | 11.78 | 0.156 | 0.0148 | 0.493 | [0.477, 0.508] | defer |
| saturation_boundary | B6 | 4118 | 33 | 12.18 | 0.160 | 0.0070 | 0.109 | [0.100, 0.119] | defer |

Endpoint systematics are recorded as run-block bootstrap CIs over atom cells.  `charge_res68_proxy` is the within-cell spread of log amplitude, `charge_bias_abs_mean` is the absolute log-amplitude displacement from the nominal-control cell in the same run/stave, `pileup_excess_proxy` is secondary-peak fraction plus late-area fraction, and `qshape_abs_mean` is the mean absolute residual to the Sample-I calibration template.

| atom | stave | n_total | timing_tail_rate | timing_tail_ci | charge_res68_proxy | charge_res68_ci | charge_bias_abs_mean | pileup_excess_proxy | qshape_abs_mean | qshape_ci |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| saturation_boundary | B2 | 436614 | 0.010 | [0.008, 0.011] | 0.238 | [0.226, 0.255] | 1.161 | 0.986 | 0.088 | [0.079, 0.101] |
| secondary_delayed_peak | B2 | 137341 | 0.014 | [0.012, 0.017] | 0.390 | [0.376, 0.405] | 0.498 | 1.112 | 0.171 | [0.165, 0.178] |
| baseline_excursion | B2 | 23032 | 0.033 | [0.018, 0.050] | 0.591 | [0.581, 0.601] | 0.435 | 0.634 | 0.787 | [0.742, 0.827] |
| secondary_delayed_peak | B4 | 21144 | 0.113 | [0.080, 0.168] | 0.285 | [0.276, 0.298] | 0.428 | 1.193 | 0.218 | [0.209, 0.237] |
| rare_s03f_topology | B6 | 14820 | 0.143 | [0.101, 0.224] | 0.340 | [0.335, 0.351] | 0.502 | 1.144 | 0.214 | [0.203, 0.242] |
| rare_s03f_topology | B4 | 14681 | 0.144 | [0.102, 0.229] | 0.281 | [0.276, 0.288] | 0.322 | 1.150 | 0.242 | [0.230, 0.268] |
| dropout_subclass | B2 | 14633 | 0.023 | [0.016, 0.033] | 0.303 | [0.289, 0.313] | 0.264 | 0.234 | 1.625 | [1.563, 1.672] |
| qtemplate_shift_proxy | B2 | 13668 | 0.020 | [0.015, 0.026] | 0.288 | [0.279, 0.296] | 0.273 | 0.206 | 1.700 | [1.653, 1.740] |
| saturation_boundary | B4 | 10277 | 0.142 | [0.102, 0.208] | 0.171 | [0.166, 0.176] | 0.883 | 1.169 | 0.196 | [0.183, 0.219] |
| secondary_delayed_peak | B6 | 10095 | 0.103 | [0.075, 0.152] | 0.292 | [0.280, 0.308] | 0.526 | 1.182 | 0.200 | [0.193, 0.214] |
| delayed_peak | B2 | 6229 | 0.103 | [0.092, 0.115] | 0.465 | [0.455, 0.474] | 0.566 | 1.384 | 0.406 | [0.396, 0.413] |
| rare_s03f_topology | B8 | 5591 | 0.143 | [0.098, 0.236] | 0.346 | [0.340, 0.358] | 0.642 | 1.168 | 0.218 | [0.206, 0.244] |

## 3. ML/NN Methods

All methods are trained leave-one-run-out on atom x run x stave cells.  Scalar features include support, prevalence, exact-binomial CI width, effective run count, Sample-I/Sample-II balance, waveform endpoint summaries, q-shape residual, timing-span proxy, and stave indicators.  Identifier columns and labels are excluded.  The tested families are ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN over the mean normalized atom waveform, and a new support-gated CNN that multiplicatively gates the convolutional waveform embedding by the scalar support vector before classification.

The model target is a held-out cell passing the frozen endpoint criterion: rare atom, cell support >= 20, effective run support >= 2, harm rate <= 0.22, timing-tail rate <= 0.25, and Sample-I/Sample-II support imbalance <= 0.35.  This target is intentionally conservative; it is a promotion safety proxy, not a physics truth label.

## 4. Head-To-Head Benchmark

| method | method_variant | average_precision | promotion_utility | utility_ci | promotion_rate | false_promotion_control_rate | ece |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 0.912 | 1.014 | [0.829, 1.141] | 0.007 | 0.000 | 0.003 |
| traditional_support_scorecard | traditional_support_scorecard | 0.982 | 0.978 | [0.921, 0.997] | 0.000 | 0.000 | 0.016 |
| ridge | ridge_C3 | 0.536 | 0.673 | [0.429, 1.071] | 0.015 | 0.000 | 0.043 |
| support_gated_cnn_new | support_gated_cnn_new_width8 | 0.452 | 0.557 | [0.309, 0.910] | 0.041 | 0.008 | 0.108 |
| cnn_1d | cnn_1d_width8 | 0.137 | 0.264 | [0.156, 0.433] | 0.066 | 0.000 | 0.198 |
| mlp | mlp_hidden16 | 0.032 | -0.639 | [-0.891, -0.376] | 0.335 | 0.400 | 0.190 |

The winner is selected by the preregistered promotion utility `AP + 0.25 recall - 2 false_control - 0.25 ECE`, with 95% CIs from run-block bootstrap resampling.  This intentionally penalizes a method that finds many apparent rare atoms by also promoting nominal controls.

## 5. Falsification

- **Pre-registration:** compare a transparent atom-support scorecard against calibrated density/support and harm-risk models with leave-run-family-out or leave-run-out validation; metrics include promotion/pass/defer rate, effective sample size, CI width, q-template shift, support coverage/ECE, false-promotion rate under controls, and ML-minus-traditional deltas with bootstrap CIs.
- **Falsification test:** any model with false-promotion rate on nominal controls above 0.05, train/test run overlap, or identifier/label leakage is rejected even if AP is high.
- **Multiplicity:** 10 declared method variants were scanned and collapsed to 6 family winners; the final table reports family-level winners and uses a utility with a control penalty rather than choosing solely on AP.

## 6. Threats To Validity

- **Benchmark/selection:** the traditional baseline is deliberately strong and contains the explicit criteria a human would use before steering on a rare atom.
- **Data leakage:** folds are split by run; feature names exclude run/event identifiers and labels; the leakage table below verifies these invariants.
- **Metric misuse:** AP alone is insufficient for rare controls, so the primary utility includes false-promotion and calibration penalties.  Full pass/defer rates and CIs are stored in `method_summary.csv`.
- **Post-hoc selection:** atom thresholds are fixed in `configs/p13b_1781055420_689_3cc21a6b_rare_atom_bootstrap_promotion_threshold.json`; model-family winners are selected from the declared scan and reported with run-block bootstrap CIs.

| check | value | pass |
| --- | --- | --- |
| leave_one_run_out_train_test_overlap | 0 | True |
| scalar_feature_identifier_label_exclusion |  | True |
| nominal_control_present_for_false_promotion | 130 | True |
| all_best_predictions_finite | 1 | True |

## 7. Provenance Manifest

`manifest.json` records the raw input checksums, code commit, runtime environment, command, random seed, and output hashes.  The analysis command was:

```bash
/home/billy/anaconda3/bin/python scripts/p13b_1781055420_689_3cc21a6b_rare_atom_bootstrap_promotion_threshold.py --config configs/p13b_1781055420_689_3cc21a6b_rare_atom_bootstrap_promotion_threshold.json
```

## 8. Findings And Criteria

The promotion criteria implied by the winning benchmark are: keep a minimum total atom/stave support of 80 pulses, require at least five runs and effective run count of four, reject cells dominated by one run, reject exact-binomial support intervals wider than 0.08, and enforce a harm-rate upper CI below 0.34.  Atoms that fail any criterion should remain diagnostic-only, even when an ML model assigns high support probability.

No follow-up ticket is appended here: the result is primarily a governance threshold for existing rare-atom studies, and the obvious extensions are already represented by the active S03/S10/S16/P04/P07/P09/P12 atom ledgers.

## 9. Reproducibility

Runtime in this execution was `193.26` s.  Output artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `atom_run_cells.csv`, `atom_support_ledger.csv`, `endpoint_systematics_by_atom.csv`, `atom_mean_waveforms.npy`, `heldout_fold_metrics.csv`, `heldout_promotion_predictions.csv`, `method_summary.csv`, `leakage_checks.csv`, bounded `pulse_atom_assignments_sample.csv`, and three PNG figures.

