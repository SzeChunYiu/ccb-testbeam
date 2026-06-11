# P10j: Tail-surrogate live-time control atlas

- **Ticket:** `1781061067.698.6c8a6921`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** `ceea30624304ef9c2a3d99b6502836736be54a3a`
- **Config:** `configs/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.json`

## 0. Question

Where do learned tail surrogates improve aligned waveform reconstruction while failing live-time or pile-up-transfer controls, and which support cells should be accepted, retained only as diagnostics, or vetoed?

The preregistered decision metric is a vector: q MSE, tail MSE, template-implied timing sigma68, live10/tau_eff transfer error, high-minus-low secondary-fraction transfer, accepted support fraction, control false-pass rate, and ML-minus-traditional run-block deltas. Lower is better for all loss metrics.

## 1. Reproduction from raw ROOT

| quantity                            |   expected |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses     |  640737    |    640737    |       0 |       0     | True   |
| analysis selected rows              |  377362    |    377362    |       0 |       0     | True   |
| S10b traditional template live10 ns |     124.79 |       124.79 |       0 |       1e-06 | True   |

The selected-pulse count is rebuilt by reading `HRDv` from the raw B-stack ROOT files, subtracting the median of samples 0-3, and selecting B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC. The S10b live10 anchor is recomputed with the frozen S10c/S10b template script before any P10j model is scored.

## 2. Methods

Let `y_i(t)` be the CFD20-aligned, amplitude-normalized waveform on the grid `t in {-3,...,14}` samples. The full-waveform reconstruction loss is

`qMSE_i(m) = |V_i|^{-1} sum_{t in V_i} (y_i(t) - yhat_{im}(t))^2`,

and the tail loss is the same sum restricted to `t >= 2`. Timing is the robust width `sigma68 = (Q84(e_t) - Q16(e_t))/2` of `e_t = 10 ns * (CFD20(yhat) - CFD20(y))`. The live-time proxy is the last post-peak grid point above 10 percent of the normalized peak, and `tau_eff = live10 / ln(10)`. The secondary-fraction proxy is the positive late-tail excess, `max(sum_{t>=5} y(t) - 0.45 sum_{t>=2} y(t), 0) / sum_{t>=2} y(t)`. It is a waveform-control proxy, not pile-up truth.

Traditional baseline: frozen empirical median templates binned by stave, amplitude, current stratum, and saturation proxy, with stave-amplitude and stave fallbacks. This is intentionally strong because it has explicit amplitude, asymmetric-tail, current, and saturation handles.

ML/NN methods: ridge and gradient-boosted trees use local pulse scalars and one-hot stave/current features; the MLP uses the same tabular features; the 1D-CNN receives an aligned waveform with the tail (`t>=2`) knocked out plus the same tabular features; the new architecture is a live-time/control-gated CNN/GBT ensemble that falls back to the empirical template if the CNN/GBT live10 or secondary proxy moves too far from the empirical control.

All primary methods are leave-one-run-out over the 21 analysis runs. Hyperparameters are fixed in the config. Confidence intervals are non-parametric bootstraps over held-out run blocks, preserving event pairing across methods.

## 3. Head-to-head benchmark

| method                                |   n_runs |   n_rows |   q_template_mse |   tail_mse |   timing_sigma68_ns |   live10_abs_error_ns |   tau_eff_abs_error_ns |   secondary_abs_error |
|:--------------------------------------|---------:|---------:|-----------------:|-----------:|--------------------:|----------------------:|-----------------------:|----------------------:|
| gradient_boosted_trees_tail_surrogate |       21 |    13351 |        0.0847503 |   0.148129 |            0.343518 |               25.7414 |                11.1794 |             0.0544518 |
| ridge_tail_surrogate                  |       21 |    13351 |        0.0845539 |   0.150854 |            0.607912 |               24.6721 |                10.715  |             0.0513776 |
| mlp_tail_surrogate                    |       21 |    13351 |        0.102692  |   0.185571 |            1.20403  |               24.7135 |                10.7329 |             0.0575359 |
| cnn_tail_knockout_surrogate           |       21 |    13351 |        0.105894  |   0.189761 |            0.952818 |               25.2656 |                10.9727 |             0.0541012 |
| control_gated_cnn_gbt_ensemble        |       21 |    13351 |        0.15791   |   0.24487  |            0.486434 |               23.8499 |                10.3579 |             0.0491394 |
| traditional_empirical_template        |       21 |    13351 |        0.16946   |   0.272606 |            0.109313 |               27.1579 |                11.7945 |             0.0501366 |

ML-minus-traditional deltas with 95 percent run-block CIs:

| method                                | metric              |   delta_vs_traditional |       ci_low |      ci_high |
|:--------------------------------------|:--------------------|-----------------------:|-------------:|-------------:|
| cnn_tail_knockout_surrogate           | q_template_mse      |           -0.0635664   | -0.0721838   | -0.0539897   |
| cnn_tail_knockout_surrogate           | tail_mse            |           -0.082845    | -0.0955211   | -0.0705596   |
| cnn_tail_knockout_surrogate           | live10_abs_error_ns |           -1.89236     | -2.59539     | -1.1032      |
| cnn_tail_knockout_surrogate           | secondary_abs_error |            0.00396465  |  0.00118026  |  0.00736146  |
| cnn_tail_knockout_surrogate           | timing_sigma68_ns   |            0.843504    |  0.687772    |  1.03248     |
| control_gated_cnn_gbt_ensemble        | q_template_mse      |           -0.0115506   | -0.0140251   | -0.00895006  |
| control_gated_cnn_gbt_ensemble        | tail_mse            |           -0.0277365   | -0.0347427   | -0.0206081   |
| control_gated_cnn_gbt_ensemble        | live10_abs_error_ns |           -3.30804     | -3.64725     | -3.03291     |
| control_gated_cnn_gbt_ensemble        | secondary_abs_error |           -0.000997202 | -0.00175762  |  4.87152e-05 |
| control_gated_cnn_gbt_ensemble        | timing_sigma68_ns   |            0.377121    |  0.30346     |  0.47211     |
| gradient_boosted_trees_tail_surrogate | q_template_mse      |           -0.0847101   | -0.0942412   | -0.0748718   |
| gradient_boosted_trees_tail_surrogate | tail_mse            |           -0.124478    | -0.138807    | -0.107722    |
| gradient_boosted_trees_tail_surrogate | live10_abs_error_ns |           -1.4165      | -1.94985     | -0.892653    |
| gradient_boosted_trees_tail_surrogate | secondary_abs_error |            0.00431526  |  0.00330939  |  0.00532973  |
| gradient_boosted_trees_tail_surrogate | timing_sigma68_ns   |            0.234204    |  0.201865    |  0.266423    |
| mlp_tail_surrogate                    | q_template_mse      |           -0.066768    | -0.0837029   | -0.0453461   |
| mlp_tail_surrogate                    | tail_mse            |           -0.0870352   | -0.110026    | -0.0552291   |
| mlp_tail_surrogate                    | live10_abs_error_ns |           -2.44439     | -2.97753     | -1.8412      |
| mlp_tail_surrogate                    | secondary_abs_error |            0.0073993   |  0.00304062  |  0.0143855   |
| mlp_tail_surrogate                    | timing_sigma68_ns   |            1.09471     |  0.91112     |  1.34692     |
| ridge_tail_surrogate                  | q_template_mse      |           -0.0849065   | -0.0949456   | -0.0736725   |
| ridge_tail_surrogate                  | tail_mse            |           -0.121752    | -0.138283    | -0.107389    |
| ridge_tail_surrogate                  | live10_abs_error_ns |           -2.48581     | -2.97822     | -1.94075     |
| ridge_tail_surrogate                  | secondary_abs_error |            0.00124104  | -0.000206266 |  0.00280463  |
| ridge_tail_surrogate                  | timing_sigma68_ns   |            0.498599    |  0.4621      |  0.53922     |

The winner named in `result.json` is **gradient_boosted_trees_tail_surrogate** by the preregistered primary ordering: minimum tail MSE, then live10 error, then secondary-fraction error. Its tail MSE is 0.148129 with CI [0.124878, 0.171745].

## 4. Live-time and pile-up transfer controls

| method                                |   predicted_high_minus_low_secondary_fraction |   observed_high_minus_low_secondary_fraction |   delta_error |      ci_low |      ci_high |   n_high_runs |   n_low_runs |
|:--------------------------------------|----------------------------------------------:|---------------------------------------------:|--------------:|------------:|-------------:|--------------:|-------------:|
| cnn_tail_knockout_surrogate           |                                  -0.0295375   |                                   -0.0308366 |    0.00129911 | -0.0357345  | -0.0233634   |            12 |            2 |
| control_gated_cnn_gbt_ensemble        |                                  -0.0102417   |                                   -0.0308366 |    0.0205949  | -0.0152769  | -0.00491054  |            12 |            2 |
| gradient_boosted_trees_tail_surrogate |                                  -0.00572554  |                                   -0.0308366 |    0.0251111  | -0.00987275 | -0.00164065  |            12 |            2 |
| mlp_tail_surrogate                    |                                  -0.0360367   |                                   -0.0308366 |   -0.00520009 | -0.0497454  | -0.0222719   |            12 |            2 |
| ridge_tail_surrogate                  |                                  -0.0161443   |                                   -0.0308366 |    0.0146923  | -0.0193149  | -0.0130744   |            12 |            2 |
| sentinel_amplitude_only_ridge         |                                  -0.00636962  |                                   -0.0308366 |    0.024467   | -0.00869657 | -0.00399802  |            12 |            2 |
| sentinel_run_only_ridge               |                                  -0.000751473 |                                   -0.0308366 |    0.0300852  | -0.00156998 | -5.61716e-05 |            12 |            2 |
| sentinel_shuffled_current_ridge       |                                  -0.00203498  |                                   -0.0308366 |    0.0288017  | -0.0121741  |  0.00790468  |            12 |            2 |
| sentinel_shuffled_live10_ridge        |                                  -0.00426025  |                                   -0.0308366 |    0.0265764  | -0.00888523 |  0.000500323 |            12 |            2 |
| traditional_empirical_template        |                                  -0.00426025  |                                   -0.0308366 |    0.0265764  | -0.00893111 |  0.000389268 |            12 |            2 |

The high-minus-low secondary-fraction table uses only Sample-I high-current and low-current held-out runs. This deliberately limits the control to the current contrast for which both a low and high current regime exist in the raw run plan.

Sentinel false-pass audit:

| sentinel                        | passes_tail_mse   | passes_live10   | passes_secondary_delta   | false_pass   |
|:--------------------------------|:------------------|:----------------|:-------------------------|:-------------|
| sentinel_amplitude_only_ridge   | True              | True            | True                     | True         |
| sentinel_shuffled_current_ridge | True              | True            | False                    | False        |
| sentinel_run_only_ridge         | True              | False           | False                    | False        |
| sentinel_shuffled_live10_ridge  | False             | True            | False                    | False        |

The reported `control_false_pass_rate` is `0.25`. A sentinel false pass means a deliberately impoverished or shuffled control met the same tail/live/secondary gates as a real model, so any action-label promotion must be treated cautiously.

## 5. Action/support atlas

| method                                | action_label    |    n |   total |   support_fraction |
|:--------------------------------------|:----------------|-----:|--------:|-------------------:|
| cnn_tail_knockout_surrogate           | accept          | 2301 |   13351 |           0.172347 |
| cnn_tail_knockout_surrogate           | diagnostic_only | 6714 |   13351 |           0.502884 |
| cnn_tail_knockout_surrogate           | veto            | 4336 |   13351 |           0.32477  |
| control_gated_cnn_gbt_ensemble        | accept          | 3921 |   13351 |           0.293686 |
| control_gated_cnn_gbt_ensemble        | diagnostic_only | 2330 |   13351 |           0.174519 |
| control_gated_cnn_gbt_ensemble        | veto            | 7100 |   13351 |           0.531795 |
| gradient_boosted_trees_tail_surrogate | accept          | 3702 |   13351 |           0.277283 |
| gradient_boosted_trees_tail_surrogate | diagnostic_only | 5945 |   13351 |           0.445285 |
| gradient_boosted_trees_tail_surrogate | veto            | 3704 |   13351 |           0.277432 |
| mlp_tail_surrogate                    | accept          | 1409 |   13351 |           0.105535 |
| mlp_tail_surrogate                    | diagnostic_only | 8196 |   13351 |           0.613887 |
| mlp_tail_surrogate                    | veto            | 3746 |   13351 |           0.280578 |
| ridge_tail_surrogate                  | accept          | 3458 |   13351 |           0.259007 |
| ridge_tail_surrogate                  | diagnostic_only | 6459 |   13351 |           0.483784 |
| ridge_tail_surrogate                  | veto            | 3434 |   13351 |           0.257209 |

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
/home/billy/anaconda3/bin/python scripts/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.py --config configs/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.json
```
