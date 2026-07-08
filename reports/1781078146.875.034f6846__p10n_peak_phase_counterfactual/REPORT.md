# P10n: No-tail q-gain peak-phase counterfactual

- **Ticket:** `1781078146.875.034f6846`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-07-08
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** `c4544ad50b600acf3852b36752c03aecbaa4610e`
- **Config:** `configs/p10n_1781078146_875_034f6846_peak_phase_counterfactual.json`

## 0. Question

Are P10f-like no-tail conditional q-template gains physically carried by peak-phase/rising-edge information, or are they target-proximal artifacts that survive only because the benchmark lets models memorize shape-adjacent handles?

The decision metric is a vector: q-template MSE, q-tail MSE, template-implied timing residual width, live10/tau_eff transfer error, too-good trigger rate, and ML-minus-traditional run-block deltas. Lower is better for all loss and trigger-rate metrics.

## 1. Reproduction from raw ROOT

| quantity                            |   expected |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses     |  640737    |    640737    |       0 |       0     | True   |
| analysis selected rows              |  377362    |    377362    |       0 |       0     | True   |
| S10b traditional template live10 ns |     124.79 |       124.79 |       0 |       1e-06 | True   |

The selected-pulse count is rebuilt by reading `HRDv` from the raw B-stack ROOT files, subtracting the median of samples 0-3, and selecting B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC. This raw-ROOT gate is run before any P10n model is scored.

## 2. Methods

Let `y_i(t)` be the CFD20-aligned, amplitude-normalized waveform on the grid `t in {-3,...,14}` samples. The full-waveform reconstruction loss is

`qMSE_i(m) = |V_i|^{-1} sum_{t in V_i} (y_i(t) - yhat_{im}(t))^2`,

and the tail loss is the same sum restricted to `t >= 2`. Timing is the robust width `sigma68 = (Q84(e_t) - Q16(e_t))/2` of `e_t = 10 ns * (CFD20(yhat) - CFD20(y))`. The live-time proxy is the last post-peak grid point above 10 percent of the normalized peak, and `tau_eff = live10 / ln(10)`. A too-good trigger fires when a learned model halves the empirical q MSE while making template-implied timing more than the configured tolerance worse; this is an artifact screen, not a physics claim.

Traditional baseline: frozen empirical median templates binned by stave, amplitude, current stratum, saturation proxy, peak phase, and rising-edge proxy, with phase and stave-amplitude fallbacks. This is intentionally strong because it gives the classical comparator the same early-phase physical handles under run holdout.

ML/NN methods: ridge, gradient-boosted trees, and MLP use no-tail local scalars and one-hot stave/current features; the 1D-CNN receives the aligned waveform with `t>=2` zeroed plus the same tabular features. Peak-phase counterfactual controls shuffle the peak/rising-edge columns at scoring time. Rising-edge ablation controls refit without `peak_sample` and `area/amplitude`. The new architecture is a phase-stability gated CNN/GBT ensemble that falls back to the empirical template if early-phase control metrics move too far from the empirical control.

All primary methods are leave-one-run-out over the 21 analysis runs. Hyperparameters are fixed in the config. Confidence intervals are non-parametric bootstraps over held-out run blocks, preserving event pairing across methods.

## 3. Head-to-head benchmark

| method                                     |   n_runs |   n_rows |   q_template_mse |   tail_mse |   timing_sigma68_ns |   live10_abs_error_ns |   tau_eff_abs_error_ns |   secondary_abs_error |   too_good_trigger_rate |
|:-------------------------------------------|---------:|---------:|-----------------:|-----------:|--------------------:|----------------------:|-----------------------:|----------------------:|------------------------:|
| gradient_boosted_trees_no_tail_phase_model |       21 |    13351 |        0.0869173 |   0.149817 |            0.342629 |               25.7122 |               11.1667  |             0.0540467 |               0.0441575 |
| ridge_no_tail_phase_model                  |       21 |    13351 |        0.0861979 |   0.151647 |            0.625309 |               24.5938 |               10.6809  |             0.0511684 |               0.0460532 |
| phase_stability_gated_cnn_gbt_ensemble     |       21 |    13351 |        0.102608  |   0.176879 |            0.484553 |               21.2575 |                9.23201 |             0.0453447 |               0.0388642 |
| mlp_no_tail_phase_model                    |       21 |    13351 |        0.100239  |   0.180206 |            1.0954   |               24.6307 |               10.697   |             0.0546394 |               0.0743235 |
| traditional_empirical_template             |       21 |    13351 |        0.110747  |   0.196867 |            0.100773 |               23.8496 |               10.3578  |             0.0435833 |               0         |
| cnn_tail_knockout_no_tail_phase_model      |       21 |    13351 |        0.112511  |   0.197902 |            0.816792 |               24.7293 |               10.7398  |             0.0556071 |               0.0635773 |

ML-minus-traditional deltas with 95 percent run-block CIs:

| method                                     | metric                |   delta_vs_traditional |      ci_low |      ci_high |
|:-------------------------------------------|:----------------------|-----------------------:|------------:|-------------:|
| cnn_tail_knockout_no_tail_phase_model      | q_template_mse        |             0.0017643  | -0.00170723 |  0.00503727  |
| cnn_tail_knockout_no_tail_phase_model      | tail_mse              |             0.00103539 | -0.00492527 |  0.00743816  |
| cnn_tail_knockout_no_tail_phase_model      | live10_abs_error_ns   |             0.879652   |  0.132206   |  1.56757     |
| cnn_tail_knockout_no_tail_phase_model      | secondary_abs_error   |             0.0120239  |  0.00888592 |  0.014935    |
| cnn_tail_knockout_no_tail_phase_model      | too_good_trigger_rate |             0.0635773  |  0.0514624  |  0.0743357   |
| cnn_tail_knockout_no_tail_phase_model      | timing_sigma68_ns     |             0.716019   |  0.65759    |  0.80086     |
| gradient_boosted_trees_no_tail_phase_model | q_template_mse        |            -0.0238298  | -0.0276694  | -0.0198086   |
| gradient_boosted_trees_no_tail_phase_model | tail_mse              |            -0.0470499  | -0.0564882  | -0.0377661   |
| gradient_boosted_trees_no_tail_phase_model | live10_abs_error_ns   |             1.86255    |  1.0684     |  2.5888      |
| gradient_boosted_trees_no_tail_phase_model | secondary_abs_error   |             0.0104634  |  0.00826666 |  0.0128466   |
| gradient_boosted_trees_no_tail_phase_model | too_good_trigger_rate |             0.0441575  |  0.0337412  |  0.0544403   |
| gradient_boosted_trees_no_tail_phase_model | timing_sigma68_ns     |             0.241856   |  0.204645   |  0.27983     |
| mlp_no_tail_phase_model                    | q_template_mse        |            -0.0105083  | -0.0192663  |  0.00421046  |
| mlp_no_tail_phase_model                    | tail_mse              |            -0.0166608  | -0.0289908  | -0.000839772 |
| mlp_no_tail_phase_model                    | live10_abs_error_ns   |             0.781071   |  0.129059   |  1.4163      |
| mlp_no_tail_phase_model                    | secondary_abs_error   |             0.0110561  |  0.00813243 |  0.0141642   |
| mlp_no_tail_phase_model                    | too_good_trigger_rate |             0.0743235  |  0.0623726  |  0.0850216   |
| mlp_no_tail_phase_model                    | timing_sigma68_ns     |             0.994625   |  0.890178   |  1.10231     |
| phase_stability_gated_cnn_gbt_ensemble     | q_template_mse        |            -0.00813927 | -0.0107332  | -0.00555638  |
| phase_stability_gated_cnn_gbt_ensemble     | tail_mse              |            -0.0199872  | -0.0266478  | -0.0145162   |
| phase_stability_gated_cnn_gbt_ensemble     | live10_abs_error_ns   |            -2.59215    | -2.87963    | -2.33551     |
| phase_stability_gated_cnn_gbt_ensemble     | secondary_abs_error   |             0.00176143 |  0.00046158 |  0.00305385  |
| phase_stability_gated_cnn_gbt_ensemble     | too_good_trigger_rate |             0.0388642  |  0.0303428  |  0.0484043   |
| phase_stability_gated_cnn_gbt_ensemble     | timing_sigma68_ns     |             0.383781   |  0.327505   |  0.454728    |
| ridge_no_tail_phase_model                  | q_template_mse        |            -0.0245491  | -0.0288636  | -0.0203694   |
| ridge_no_tail_phase_model                  | tail_mse              |            -0.0452195  | -0.0552273  | -0.0359497   |
| ridge_no_tail_phase_model                  | live10_abs_error_ns   |             0.744124   |  0.00475024 |  1.42357     |
| ridge_no_tail_phase_model                  | secondary_abs_error   |             0.00758513 |  0.004948   |  0.0100177   |
| ridge_no_tail_phase_model                  | too_good_trigger_rate |             0.0460532  |  0.0382923  |  0.0535463   |
| ridge_no_tail_phase_model                  | timing_sigma68_ns     |             0.524536   |  0.487374   |  0.565554    |

The winner named in `result.json` is **ridge_no_tail_phase_model** by the primary ordering: minimum q-template MSE among non-sentinel methods, then tail MSE, then too-good trigger rate. Its q-template MSE is 0.0861979 with CI [0.0747804, 0.0978453].

## 4. Live-time and pile-up transfer controls

| method                                     |   predicted_high_minus_low_secondary_fraction |   observed_high_minus_low_secondary_fraction |   delta_error |       ci_low |      ci_high |   n_high_runs |   n_low_runs |
|:-------------------------------------------|----------------------------------------------:|---------------------------------------------:|--------------:|-------------:|-------------:|--------------:|-------------:|
| cnn_tail_knockout_no_tail_phase_model      |                                   -0.00894388 |                                   -0.0318105 |    0.0228666  | -0.0263917   |  0.00856929  |            12 |            2 |
| gradient_boosted_trees_no_tail_phase_model |                                   -0.00759557 |                                   -0.0318105 |    0.0242149  | -0.0113603   | -0.00387699  |            12 |            2 |
| mlp_no_tail_phase_model                    |                                    0.0115632  |                                   -0.0318105 |    0.0433737  | -0.0092884   |  0.0327614   |            12 |            2 |
| phase_stability_gated_cnn_gbt_ensemble     |                                   -0.011946   |                                   -0.0318105 |    0.0198645  | -0.0185302   | -0.00545159  |            12 |            2 |
| ridge_no_tail_phase_model                  |                                   -0.016572   |                                   -0.0318105 |    0.0152384  | -0.0237418   | -0.0091133   |            12 |            2 |
| sentinel_amplitude_only_ridge              |                                   -0.00810302 |                                   -0.0318105 |    0.0237074  | -0.0111692   | -0.0049673   |            12 |            2 |
| sentinel_gbt_peak_phase_swapped            |                                   -0.00918413 |                                   -0.0318105 |    0.0226263  | -0.0113513   | -0.00696946  |            12 |            2 |
| sentinel_gbt_rising_edge_ablation          |                                   -0.00823541 |                                   -0.0318105 |    0.023575   | -0.0134345   | -0.0032155   |            12 |            2 |
| sentinel_mlp_peak_phase_swapped            |                                    0.0177924  |                                   -0.0318105 |    0.0496029  | -0.00461484  |  0.0408297   |            12 |            2 |
| sentinel_mlp_rising_edge_ablation          |                                   -0.0122437  |                                   -0.0318105 |    0.0195668  | -0.0191105   | -0.00498719  |            12 |            2 |
| sentinel_ridge_peak_phase_swapped          |                                   -0.0202606  |                                   -0.0318105 |    0.0115499  | -0.0286759   | -0.0122105   |            12 |            2 |
| sentinel_ridge_rising_edge_ablation        |                                   -0.0219366  |                                   -0.0318105 |    0.00987387 | -0.0238023   | -0.0198488   |            12 |            2 |
| sentinel_run_only_ridge                    |                                   -3.6467e-05 |                                   -0.0318105 |    0.031774   | -0.000728554 |  0.000607125 |            12 |            2 |
| sentinel_shuffled_current_ridge            |                                   -0.0002558  |                                   -0.0318105 |    0.0315547  | -0.0114454   |  0.0108595   |            12 |            2 |
| sentinel_shuffled_live10_ridge             |                                   -0.0163662  |                                   -0.0318105 |    0.0154443  | -0.0184132   | -0.0137323   |            12 |            2 |
| traditional_empirical_template             |                                   -0.0163662  |                                   -0.0318105 |    0.0154443  | -0.018476    | -0.013759    |            12 |            2 |

The high-minus-low secondary-fraction table uses only Sample-I high-current and low-current held-out runs. This deliberately limits the control to the current contrast for which both a low and high current regime exist in the raw run plan.

Sentinel false-pass audit:

| sentinel                        | passes_tail_mse   | passes_live10   | passes_secondary_delta   | false_pass   |
|:--------------------------------|:------------------|:----------------|:-------------------------|:-------------|
| sentinel_amplitude_only_ridge   | True              | False           | True                     | False        |
| sentinel_shuffled_current_ridge | True              | False           | False                    | False        |
| sentinel_shuffled_live10_ridge  | False             | False           | True                     | False        |
| sentinel_run_only_ridge         | False             | False           | False                    | False        |

The reported `control_false_pass_rate` is `0`. A sentinel false pass means a deliberately impoverished or shuffled control met the same tail/live/secondary gates as a real model, so any action-label promotion must be treated cautiously.

## 5. Action/support atlas

| method                                     | action_label    |    n |   total |   support_fraction |
|:-------------------------------------------|:----------------|-----:|--------:|-------------------:|
| cnn_tail_knockout_no_tail_phase_model      | accept          | 2154 |   13351 |           0.161336 |
| cnn_tail_knockout_no_tail_phase_model      | diagnostic_only | 5495 |   13351 |           0.41158  |
| cnn_tail_knockout_no_tail_phase_model      | veto            | 5702 |   13351 |           0.427084 |
| gradient_boosted_trees_no_tail_phase_model | accept          | 2747 |   13351 |           0.205752 |
| gradient_boosted_trees_no_tail_phase_model | diagnostic_only | 5100 |   13351 |           0.381994 |
| gradient_boosted_trees_no_tail_phase_model | veto            | 5504 |   13351 |           0.412254 |
| mlp_no_tail_phase_model                    | accept          | 1561 |   13351 |           0.11692  |
| mlp_no_tail_phase_model                    | diagnostic_only | 6089 |   13351 |           0.456071 |
| mlp_no_tail_phase_model                    | veto            | 5701 |   13351 |           0.427009 |
| phase_stability_gated_cnn_gbt_ensemble     | accept          | 4522 |   13351 |           0.338701 |
| phase_stability_gated_cnn_gbt_ensemble     | diagnostic_only | 2414 |   13351 |           0.18081  |
| phase_stability_gated_cnn_gbt_ensemble     | veto            | 6415 |   13351 |           0.480488 |
| ridge_no_tail_phase_model                  | accept          | 2638 |   13351 |           0.197588 |
| ridge_no_tail_phase_model                  | diagnostic_only | 5473 |   13351 |           0.409932 |
| ridge_no_tail_phase_model                  | veto            | 5240 |   13351 |           0.39248  |

Cells are labelled `accept` only when q and tail losses improve over the empirical baseline and live10, timing, and secondary-fraction controls do not worsen beyond the preregistered tolerances. Cells with reconstruction gain but control failure are `diagnostic_only`; cells without tail gain are `veto`.

## 6. Systematics and caveats

- Benchmark/selection: the empirical baseline has amplitude, current, saturation, peak-phase, rising-edge, and fallback handles; it is not a strawman. The phase-gated ensemble is evaluated on the same held-out rows as the other methods.
- Data leakage: folds exclude the held-out run before fitting templates or ML models. Primary feature sets exclude run id and event id. Phase-swapped, rising-edge ablated, run-only, amplitude-only, shuffled-live10, and shuffled-current models are labelled sentinels and excluded from winner selection.
- Metric misuse: q/tail MSE and template-implied timing sigma68 are waveform-transfer metrics. They do not replace downstream same-particle timing closure. The secondary fraction is a late-tail proxy, not direct pile-up truth.
- Post-hoc selection: method families, tolerances, run bootstrap, and action labels are fixed in the config. The new architecture is included because P10n asks whether no-tail gains survive peak-phase/rising-edge controls.
- Statistical precision: the low-current current-control side contains only two held-out runs, so high-minus-low secondary CIs are honest but coarse.

## 7. Artifacts and reproducibility

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `method_summary.csv`, `method_delta_bootstrap.csv`, `secondary_transfer_bootstrap.csv`, `action_atlas.csv`, `action_support_summary.csv`, `sentinel_false_pass.csv`, `leakage_checks.csv`, `heldout_predictions.csv.gz`, `fold_summary.csv`, `input_sha256.csv`, and PNG figures.

Reproduce with:

```bash
/home/billy/anaconda3/bin/python scripts/p10n_1781078146_875_034f6846_peak_phase_counterfactual.py --config configs/p10n_1781078146_875_034f6846_peak_phase_counterfactual.json
```
