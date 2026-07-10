# P10j: Independent acquisition-window live-time surrogate falsification

- **Ticket:** `1781182678.1624.461c5bb5`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-07-10
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** `50ef1d5e1900f4177bc00a933fd0475f8dd7bd5c`
- **Config:** `configs/p10j_1781182678_1624_461c5bb5_acquisition_window_livetime_falsification.json`

## 0. Question

Can tail-shape reconstruction winners predict independent acquisition-window handles, specifically live10, live20, and a delayed late-tail secondary-fraction proxy, beyond shuffled-live10 controls?

The preregistered decision metric is a vector: q MSE, tail MSE, template-implied timing sigma68, live10/live20/tau_eff transfer error, high-minus-low secondary-fraction transfer, accepted support fraction, control false-pass rate, and ML-minus-traditional run-block deltas. Lower is better for all loss metrics.

## 1. Reproduction from raw ROOT

| quantity                            |   expected |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses     |  640737    |    640737    |       0 |       0     | True   |
| analysis selected rows              |  377362    |    377362    |       0 |       0     | True   |
| S10b traditional template live10 ns |     124.79 |       124.79 |       0 |       1e-06 | True   |

The selected-pulse count is rebuilt by reading `HRDv` from the raw B-stack ROOT files, subtracting the median of samples 0-3, and selecting B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC. The S10b live10 anchor is recomputed with the frozen S10c/S10b template script before any P10j model is scored. The live20 and secondary-fraction controls are delayed/acquisition-window handles computed from the held-out raw pulse, not labels copied from a same-run fit.

## 2. Methods

Let `y_i(t)` be the CFD20-aligned, amplitude-normalized waveform on the grid `t in {-3,...,14}` samples. The full-waveform reconstruction loss is

`qMSE_i(m) = |V_i|^{-1} sum_{t in V_i} (y_i(t) - yhat_{im}(t))^2`,

and the tail loss is the same sum restricted to `t >= 2`. Timing is the robust width `sigma68 = (Q84(e_t) - Q16(e_t))/2` of `e_t = 10 ns * (CFD20(yhat) - CFD20(y))`. The live-time proxies are the last post-peak grid points above 10 and 20 percent of the normalized peak, with `tau_eff = live10 / ln(10)`. The secondary-fraction proxy is the positive late-tail excess, `max(sum_{t>=5} y(t) - 0.45 sum_{t>=2} y(t), 0) / sum_{t>=2} y(t)`. It is an acquisition-window falsification handle, not pile-up truth.

Traditional baseline: frozen empirical median templates binned by stave, amplitude, current stratum, and saturation proxy, with stave-amplitude and stave fallbacks. This is intentionally strong because it has explicit amplitude, asymmetric-tail, current, and saturation handles.

ML/NN methods: ridge and gradient-boosted trees use local pulse scalars and one-hot stave/current features; the MLP uses the same tabular features; the 1D-CNN receives an aligned waveform with the tail (`t>=2`) knocked out plus the same tabular features; the new architecture is a live-time/control-gated CNN/GBT ensemble that falls back to the empirical template if the CNN/GBT live10 or secondary proxy moves too far from the empirical control.

All primary methods are leave-one-run-out over the 21 analysis runs. Hyperparameters are fixed in the config. Confidence intervals are non-parametric bootstraps over held-out run blocks, preserving event pairing across methods.

## 3. Head-to-head benchmark

| method                                |   n_runs |   n_rows |   q_template_mse |   tail_mse |   timing_sigma68_ns |   live10_abs_error_ns |   live20_abs_error_ns |   tau_eff_abs_error_ns |   secondary_abs_error |
|:--------------------------------------|---------:|---------:|-----------------:|-----------:|--------------------:|----------------------:|----------------------:|-----------------------:|----------------------:|
| ridge_tail_surrogate                  |       21 |    11881 |        0.0887899 |   0.154422 |            0.586992 |               25.1881 |               28.166  |                10.939  |             0.0520577 |
| gradient_boosted_trees_tail_surrogate |       21 |    11881 |        0.0935609 |   0.157877 |            0.359291 |               26.377  |               30.6215 |                11.4554 |             0.0567097 |
| mlp_tail_surrogate                    |       21 |    11881 |        0.104246  |   0.182043 |            1.08155  |               25.266  |               27.9828 |                10.9729 |             0.0569533 |
| cnn_tail_knockout_surrogate           |       21 |    11881 |        0.128208  |   0.220821 |            1.63317  |               25.7774 |               26.9944 |                11.195  |             0.0538327 |
| control_gated_cnn_gbt_ensemble        |       21 |    11881 |        0.167129  |   0.256045 |            0.642035 |               24.2532 |               24.0678 |                10.533  |             0.0495284 |
| traditional_empirical_template        |       21 |    11881 |        0.174571  |   0.274572 |            0.109351 |               27.717  |               22.8649 |                12.0374 |             0.0511877 |

ML-minus-traditional deltas with 95 percent run-block CIs:

| method                                | metric              |   delta_vs_traditional |       ci_low |      ci_high |
|:--------------------------------------|:--------------------|-----------------------:|-------------:|-------------:|
| cnn_tail_knockout_surrogate           | q_template_mse      |           -0.0463629   | -0.0559357   | -0.0369811   |
| cnn_tail_knockout_surrogate           | tail_mse            |           -0.0537512   | -0.06763     | -0.0412197   |
| cnn_tail_knockout_surrogate           | live10_abs_error_ns |           -1.93962     | -2.4663      | -1.37873     |
| cnn_tail_knockout_surrogate           | live20_abs_error_ns |            4.12945     |  3.34699     |  5.01174     |
| cnn_tail_knockout_surrogate           | secondary_abs_error |            0.00264509  |  2.66955e-05 |  0.00526808  |
| cnn_tail_knockout_surrogate           | timing_sigma68_ns   |            1.52382     |  1.09173     |  2.05496     |
| control_gated_cnn_gbt_ensemble        | q_template_mse      |           -0.00744231  | -0.0094219   | -0.0053708   |
| control_gated_cnn_gbt_ensemble        | tail_mse            |           -0.0185271   | -0.0238493   | -0.0130414   |
| control_gated_cnn_gbt_ensemble        | live10_abs_error_ns |           -3.46381     | -3.73654     | -3.2563      |
| control_gated_cnn_gbt_ensemble        | live20_abs_error_ns |            1.20294     |  0.922601    |  1.47399     |
| control_gated_cnn_gbt_ensemble        | secondary_abs_error |           -0.00165922  | -0.00266478  | -0.000448651 |
| control_gated_cnn_gbt_ensemble        | timing_sigma68_ns   |            0.532684    |  0.430324    |  0.706938    |
| gradient_boosted_trees_tail_surrogate | q_template_mse      |           -0.08101     | -0.0911584   | -0.0719069   |
| gradient_boosted_trees_tail_surrogate | tail_mse            |           -0.116695    | -0.131346    | -0.100733    |
| gradient_boosted_trees_tail_surrogate | live10_abs_error_ns |           -1.34006     | -1.82924     | -0.782518    |
| gradient_boosted_trees_tail_surrogate | live20_abs_error_ns |            7.75657     |  7.14087     |  8.53952     |
| gradient_boosted_trees_tail_surrogate | secondary_abs_error |            0.00552199  |  0.00412029  |  0.00673505  |
| gradient_boosted_trees_tail_surrogate | timing_sigma68_ns   |            0.24994     |  0.211234    |  0.291612    |
| mlp_tail_surrogate                    | q_template_mse      |           -0.0703251   | -0.0828574   | -0.0590881   |
| mlp_tail_surrogate                    | tail_mse            |           -0.0925295   | -0.106448    | -0.0777558   |
| mlp_tail_surrogate                    | live10_abs_error_ns |           -2.45102     | -3.02793     | -1.83812     |
| mlp_tail_surrogate                    | live20_abs_error_ns |            5.11788     |  4.03242     |  6.16448     |
| mlp_tail_surrogate                    | secondary_abs_error |            0.0057656   |  0.00338564  |  0.00857293  |
| mlp_tail_surrogate                    | timing_sigma68_ns   |            0.972197    |  0.859318    |  1.18181     |
| ridge_tail_surrogate                  | q_template_mse      |           -0.085781    | -0.0983729   | -0.0739751   |
| ridge_tail_surrogate                  | tail_mse            |           -0.12015     | -0.137441    | -0.10248     |
| ridge_tail_surrogate                  | live10_abs_error_ns |           -2.52897     | -3.04753     | -2.02884     |
| ridge_tail_surrogate                  | live20_abs_error_ns |            5.30108     |  4.51531     |  6.1665      |
| ridge_tail_surrogate                  | secondary_abs_error |            0.000870045 | -0.000593208 |  0.00247612  |
| ridge_tail_surrogate                  | timing_sigma68_ns   |            0.477641    |  0.451709    |  0.505495    |

The winner named in `result.json` is **ridge_tail_surrogate** by the preregistered primary ordering: minimum tail MSE, then live10 error, live20 error, and secondary-fraction error. Its tail MSE is 0.154422 with CI [0.1263, 0.183915].

## 4. Acquisition-window and pile-up transfer controls

| method                                |   predicted_high_minus_low_secondary_fraction |   observed_high_minus_low_secondary_fraction |   delta_error |       ci_low |     ci_high |   n_high_runs |   n_low_runs |
|:--------------------------------------|----------------------------------------------:|---------------------------------------------:|--------------:|-------------:|------------:|--------------:|-------------:|
| cnn_tail_knockout_surrogate           |                                  -0.0349854   |                                   -0.0332305 |   -0.00175493 | -0.041597    | -0.0288733  |            12 |            2 |
| control_gated_cnn_gbt_ensemble        |                                  -0.0186034   |                                   -0.0332305 |    0.014627   | -0.025452    | -0.0114617  |            12 |            2 |
| gradient_boosted_trees_tail_surrogate |                                  -0.00746417  |                                   -0.0332305 |    0.0257663  | -0.0116578   | -0.00316459 |            12 |            2 |
| mlp_tail_surrogate                    |                                   0.00823035  |                                   -0.0332305 |    0.0414608  | -0.0136394   |  0.0300424  |            12 |            2 |
| ridge_tail_surrogate                  |                                  -0.00424573  |                                   -0.0332305 |    0.0289847  | -0.0166266   |  0.00812189 |            12 |            2 |
| sentinel_amplitude_only_ridge         |                                  -0.00820193  |                                   -0.0332305 |    0.0250285  | -0.0129141   | -0.0036615  |            12 |            2 |
| sentinel_run_only_ridge               |                                  -0.000111078 |                                   -0.0332305 |    0.0331194  | -0.000758477 |  0.0005933  |            12 |            2 |
| sentinel_shuffled_current_ridge       |                                  -0.0116201   |                                   -0.0332305 |    0.0216103  | -0.0191125   | -0.00432953 |            12 |            2 |
| sentinel_shuffled_live10_ridge        |                                  -0.00426824  |                                   -0.0332305 |    0.0289622  | -0.0095029   |  0.00103865 |            12 |            2 |
| traditional_empirical_template        |                                  -0.00426824  |                                   -0.0332305 |    0.0289622  | -0.00952316  |  0.00120605 |            12 |            2 |

The high-minus-low secondary-fraction table uses only Sample-I high-current and low-current held-out runs. This deliberately limits the control to the current contrast for which both a low and high current regime exist in the raw run plan.

Sentinel false-pass audit:

| sentinel                        | passes_tail_mse   | passes_live10   | passes_secondary_delta   | false_pass   |
|:--------------------------------|:------------------|:----------------|:-------------------------|:-------------|
| sentinel_amplitude_only_ridge   | True              | True            | False                    | False        |
| sentinel_shuffled_current_ridge | True              | True            | True                     | True         |
| sentinel_run_only_ridge         | True              | False           | False                    | False        |
| sentinel_shuffled_live10_ridge  | False             | True            | False                    | False        |

The reported `control_false_pass_rate` is `0.25`. A sentinel false pass means a deliberately impoverished or shuffled control met the same tail/live/secondary gates as a real model, so any action-label promotion must be treated cautiously.

## 5. Action/support atlas

| method                                | action_label    |    n |   total |   support_fraction |
|:--------------------------------------|:----------------|-----:|--------:|-------------------:|
| cnn_tail_knockout_surrogate           | accept          | 1181 |   11881 |          0.0994024 |
| cnn_tail_knockout_surrogate           | diagnostic_only | 4934 |   11881 |          0.415285  |
| cnn_tail_knockout_surrogate           | veto            | 5766 |   11881 |          0.485313  |
| control_gated_cnn_gbt_ensemble        | accept          | 2835 |   11881 |          0.238616  |
| control_gated_cnn_gbt_ensemble        | diagnostic_only | 2793 |   11881 |          0.235081  |
| control_gated_cnn_gbt_ensemble        | veto            | 6253 |   11881 |          0.526302  |
| gradient_boosted_trees_tail_surrogate | accept          | 3344 |   11881 |          0.281458  |
| gradient_boosted_trees_tail_surrogate | diagnostic_only | 4507 |   11881 |          0.379345  |
| gradient_boosted_trees_tail_surrogate | veto            | 4030 |   11881 |          0.339197  |
| mlp_tail_surrogate                    | accept          |  928 |   11881 |          0.0781079 |
| mlp_tail_surrogate                    | diagnostic_only | 7180 |   11881 |          0.604326  |
| mlp_tail_surrogate                    | veto            | 3773 |   11881 |          0.317566  |
| ridge_tail_surrogate                  | accept          | 2522 |   11881 |          0.212272  |
| ridge_tail_surrogate                  | diagnostic_only | 6420 |   11881 |          0.540359  |
| ridge_tail_surrogate                  | veto            | 2939 |   11881 |          0.24737   |

Cells are labelled `accept` only when q and tail losses improve over the empirical baseline and live10, timing, and secondary-fraction controls do not worsen beyond the preregistered tolerances. Cells with reconstruction gain but control failure are `diagnostic_only`; cells without tail gain are `veto`.

## 6. Systematics and caveats

- Benchmark/selection: the empirical baseline has amplitude, current, saturation, and fallback handles; it is not a strawman. The control-gated ensemble is evaluated on the same held-out rows as the other methods.
- Data leakage: folds exclude the held-out run before fitting templates or ML models. Primary feature sets exclude run id and event id. Run-only, amplitude-only, shuffled-live10, and shuffled-current models are labelled sentinels and excluded from winner selection.
- Metric misuse: q/tail MSE and template-implied timing sigma68 are waveform-transfer metrics. They do not replace downstream same-particle timing closure. The secondary fraction is a late-tail proxy, not direct pile-up truth.
- Post-hoc selection: method families, tolerances, run bootstrap, and action labels are fixed in the config. The new architecture is included because P10j explicitly asks for accept/diagnostic/veto support conversion.
- Statistical precision: the low-current current-control side contains only two held-out runs, so high-minus-low secondary CIs are honest but coarse.

## 7. Artifacts and reproducibility

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `method_summary.csv`, `method_delta_bootstrap.csv`, `secondary_transfer_bootstrap.csv`, `action_atlas.csv`, `action_support_summary.csv`, `sentinel_false_pass.csv`, `leakage_checks.csv`, `heldout_predictions.csv.gz`, `fold_summary.csv`, `input_sha256.csv`, and PNG figures.

Reproduce with:

```bash
/home/billy/anaconda3/bin/python scripts/p10j_1781182678_1624_461c5bb5_acquisition_window_livetime_falsification.py --config configs/p10j_1781182678_1624_461c5bb5_acquisition_window_livetime_falsification.json
```
