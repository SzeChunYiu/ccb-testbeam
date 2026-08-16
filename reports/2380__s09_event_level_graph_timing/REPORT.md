# S09: Event-level Four-Stave Graph Timing Benchmark

**Ticket:** `#2380 S09: Event-level GNN over 4-stave graph`
**Worker:** `testbeam-laptop-1`
**Date:** `2026-08-16`
**Git commit:** `68374937a0026eba71394446c496390ef51afa18`
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

This study evaluates whether an event-level graph representation over B2/B4/B6/B8 improves the internally calibrated B-stack timing consensus and clean-timing probability relative to strong traditional timing combination.  The raw ROOT reproduction gate is run first and exactly matches the S00 selected B-stave pulse count.  All benchmark methods use a run-held-out split and run-block bootstrap confidence intervals.  The winner written to `result.json` is **`graph_residual_message_passing_new`**, with held-out time sigma68 `0.2772` ns and clean-probability Brier `0.0005`.

The target is not an external event-time truth label.  It is the robust median of train-calibrated same-event B-stave CFD20 times, and `clean_timing` means the selected-stave calibrated time span is at most `5.0` ns.  The result is therefore a rigorous head-to-head benchmark of an operational proxy, not a claim of absolute beam time reconstruction.

## 1. Raw ROOT Reproduction Gate

For every configured HRDB run, `h101/HRDv` is reshaped to `(event, channel, sample)` with 8 channels and 18 samples.  For B2/B4/B6/B8 channels `{0,2,4,6}`, the pedestal is

`b_{e,c} = median(x_{e,c,t}: t in {0,1,2,3})`,

and a selected pulse record is

`I_{e,c} = 1[max_t(x_{e,c,t} - b_{e,c}) > 1000 ADC]`.

| Quantity | Report value | Reproduced | Delta | Pass |
|---|---:|---:|---:|---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

The event-level benchmark table is built only after this exact reproduction gate passes.  Events enter the benchmark when at least `3` of the four B-staves are selected and all selected CFD20 times are finite.  To keep the ticket CPU-bounded, at most `25000` qualifying events per run are retained; all counting is still done on the full raw ROOT set.

## 2. Calibration and Targets

On train runs only, each stave receives an offset

`o_s = median(t^{CFD20}_{e,s})`,

and robust scale

`sigma_s = (Q84(t^{CFD20}_{e,s}-o_s) - Q16(t^{CFD20}_{e,s}-o_s))/2`.

The calibrated node time is `u_{e,s}=t^{CFD20}_{e,s}-o_s`.  The regression target is the event median over selected nodes,

`T_e = median({u_{e,s}: I_{e,s}=1})`,

and the classification target is

`Y_e = 1[max_s u_{e,s} - min_s u_{e,s} <= 5 ns]`.

Train-run calibration constants:

| Stave | Offset ns | Sigma68 ns |
|---|---:|---:|
| B2 | 42.1601 | 15.7713 |
| B4 | 50.5973 | 34.9481 |
| B6 | 54.3632 | 36.1556 |
| B8 | 53.9819 | 33.8917 |

## 3. Methods

**Traditional inverse-variance combiner.**  This is the S04-style comparator.  It predicts

`\hat T_e = sum_s w_s u_{e,s} / sum_s w_s`, with `w_s=I_{e,s}/sigma_s^2`,

and maps the weighted internal chi-square to a clean-timing probability `exp[-chi2/(2 dof)]`.  It is transparent, uses the train-run calibration only, and is the benchmark all learned methods must beat.

**Ridge.**  A standardized ridge regressor and L2 logistic classifier use selected flags, amplitudes, areas, peak samples, early/tail fractions, calibrated times, and adjacent time differences.

**Gradient-boosted trees.**  Histogram gradient-boosted regression/classification uses the same tabular feature set and can model threshold and interaction structure without hand-coded equations.

**MLP.**  A two-hidden-layer multilayer perceptron is trained on the same tabular features with early stopping.  It tests whether a generic dense neural network improves on tree and linear baselines.

**1D-CNN filterbank.**  Torch was not required for this CPU ticket, so the CNN comparator is a fixed one-dimensional convolutional filterbank over each 18-sample waveform followed by ridge/logistic heads.  It has the local-kernel inductive bias of a small 1D-CNN but is treated as a lightweight surrogate in the caveats.

**New graph residual message-passing architecture.**  The new architecture builds node reliabilities from log-amplitude, selected flags, and calibrated node times; computes all pairwise edge time disagreements; forms an amplitude-attention graph consensus; and fits boosted residual heads for event time and clean probability.  It is the only method that explicitly uses the four-stave graph topology.

All learned methods are fit only on non-held-out runs.  Held-out runs are `58, 60, 62, 64, 65`.  Confidence intervals resample held-out runs with replacement.

Per-event uncertainty is calibrated from train residuals only.  For each method, train predictions are grouped by predicted clean probability, and the bin-level robust residual width

`hat sigma_b = (Q84(e_train in b) - Q16(e_train in b))/2`

is assigned to held-out events in the same probability bin.  The table reports median predicted sigma and empirical 68%-style coverage `P(|e| <= hat sigma)` on held-out runs.

## 4. Head-to-Head Results

Primary score: `C = sigma68(time residual) + 2 * Brier(clean probability)`.  The coefficient keeps the probability calibration term visible while preserving timing resolution as the dominant unit.

| method                             |    n |   time_bias_ns |   time_mae_ns |   time_sigma68_ns |   clean_brier |   clean_auc |   clean_ece10 |   median_pred_sigma_ns |   sigma68_coverage |   winner_score |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   time_mae_ns_ci_low |   time_mae_ns_ci_high |   clean_brier_ci_low |   clean_brier_ci_high |   clean_ece10_ci_low |   clean_ece10_ci_high |   winner_score_ci_low |   winner_score_ci_high |   sigma68_coverage_ci_low |   sigma68_coverage_ci_high |
|:-----------------------------------|-----:|---------------:|--------------:|------------------:|--------------:|------------:|--------------:|-----------------------:|-------------------:|---------------:|-------------------------:|--------------------------:|---------------------:|----------------------:|---------------------:|----------------------:|---------------------:|----------------------:|----------------------:|-----------------------:|--------------------------:|---------------------------:|
| graph_residual_message_passing_new | 5271 |       0.017428 |       0.35498 |           0.27718 |    0.00053464 |     0.99991 |    0.0006075  |                0.25    |           0.68109  |        0.27825 |                  0.26351 |                   0.33936 |              0.32326 |               0.49721 |           0.00013417 |             0.0017162 |           0.00019891 |             0.0017439 |               0.26399 |                0.34319 |                  0.61746  |                    0.69924 |
| gradient_boosted_trees             | 5271 |       0.022487 |       0.39681 |           0.30638 |    0.00071657 |     0.99987 |    0.00096394 |                0.28179 |           0.68222  |        0.30781 |                  0.29413 |                   0.37707 |              0.36885 |               0.52027 |           0.00036971 |             0.0018416 |           0.00060057 |             0.0024281 |               0.29503 |                0.38075 |                  0.60242  |                    0.69928 |
| mlp                                | 5271 |       0.21023  |       0.7208  |           0.72381 |    0.0047831  |     0.97044 |    0.0038987  |                0.66789 |           0.65813  |        0.73337 |                  0.69944 |                   0.82464 |              0.68102 |               0.87952 |           0.0036722  |             0.0088776 |           0.0022713  |             0.012045  |               0.70791 |                0.84239 |                  0.63062  |                    0.66662 |
| ridge                              | 5271 |      -0.024154 |       0.99313 |           0.92999 |    0.069517   |     0.9172  |    0.1847     |                0.92968 |           0.69076  |        1.069   |                  0.87926 |                   1.0018  |              0.94366 |               1.2159  |           0.052433   |             0.11179   |           0.16853    |             0.21232   |               1.0285  |                1.1957  |                  0.65407  |                    0.70943 |
| traditional_inverse_variance_s04   | 5271 |       3.4134   |       6.807   |           1.3628  |    0.9037     |     0.99988 |    0.934      |                0.59558 |           0.079112 |        3.1702  |                  1.1967  |                   4.4478  |              6.2964  |               9.7325  |           0.8239     |             0.92169   |           0.86631    |             0.94934   |               3.0395  |                6.0601  |                  0.045155 |                    0.18456 |
| one_dimensional_cnn_filterbank     | 5271 |      -0.21616  |       4.3507  |           4.6717  |    0.08083    |     0.91714 |    0.19847    |                4.6562  |           0.70309  |        4.8334  |                  4.3299  |                   5.8935  |              4.0104  |               5.4803  |           0.066471   |             0.12065   |           0.18081    |             0.23108   |               4.4912  |                6.1348  |                  0.61759  |                    0.73125 |

Per-run held-out timing diagnostics:

| method                             |   run |    n |   time_bias_ns |   time_mae_ns |   time_sigma68_ns |
|:-----------------------------------|------:|-----:|---------------:|--------------:|------------------:|
| gradient_boosted_trees             |    58 |  202 |      0.017892  |       0.73465 |           0.40006 |
| gradient_boosted_trees             |    60 | 2029 |      0.016214  |       0.37997 |           0.29018 |
| gradient_boosted_trees             |    62 | 2163 |      0.038944  |       0.35728 |           0.29411 |
| gradient_boosted_trees             |    64 |  623 |      0.0049274 |       0.47245 |           0.3647  |
| gradient_boosted_trees             |    65 |  254 |     -0.020826  |       0.41384 |           0.37088 |
| graph_residual_message_passing_new |    58 |  202 |     -0.046999  |       0.75023 |           0.3518  |
| graph_residual_message_passing_new |    60 | 2029 |      0.027741  |       0.31778 |           0.25538 |
| graph_residual_message_passing_new |    62 | 2163 |      0.01432   |       0.32594 |           0.27003 |
| graph_residual_message_passing_new |    64 |  623 |      0.037116  |       0.44856 |           0.33136 |
| graph_residual_message_passing_new |    65 |  254 |     -0.035529  |       0.35565 |           0.33179 |
| mlp                                |    58 |  202 |      0.60278   |       1.2365  |           0.85311 |
| mlp                                |    60 | 2029 |      0.20193   |       0.7041  |           0.68947 |
| mlp                                |    62 | 2163 |      0.17565   |       0.66371 |           0.69596 |
| mlp                                |    64 |  623 |      0.16827   |       0.78614 |           0.80642 |
| mlp                                |    65 |  254 |      0.36172   |       0.76989 |           0.81374 |
| one_dimensional_cnn_filterbank     |    58 |  202 |     -0.025498  |       5.4519  |           5.4643  |
| one_dimensional_cnn_filterbank     |    60 | 2029 |     -1.1012    |       4.2546  |           4.4645  |
| one_dimensional_cnn_filterbank     |    62 | 2163 |     -0.16853   |       3.8787  |           4.2266  |
| one_dimensional_cnn_filterbank     |    64 |  623 |      1.6188    |       5.1801  |           5.5728  |
| one_dimensional_cnn_filterbank     |    65 |  254 |      1.7957    |       6.2279  |           6.677   |
| ridge                              |    58 |  202 |     -0.02855   |       1.5497  |           1.1246  |
| ridge                              |    60 | 2029 |     -0.15159   |       0.9723  |           0.95272 |
| ridge                              |    62 | 2163 |      0.088221  |       0.9217  |           0.87018 |
| ridge                              |    64 |  623 |      0.016628  |       1.0647  |           0.85654 |
| ridge                              |    65 |  254 |     -0.059682  |       1.1496  |           1.022   |
| traditional_inverse_variance_s04   |    58 |  202 |     -2.297     |      11.086   |           8.6068  |
| traditional_inverse_variance_s04   |    60 | 2029 |      4.6602    |       5.9942  |           1.1465  |
| traditional_inverse_variance_s04   |    62 | 2163 |      3.7301    |       6.3563  |           1.3283  |
| traditional_inverse_variance_s04   |    64 |  623 |      1.8759    |       8.0228  |           3.4503  |
| traditional_inverse_variance_s04   |    65 |  254 |     -0.93104   |      10.752   |           3.4747  |

## 5. Falsification and Systematics

Pre-registration comes from ticket `#2380`: graph `{B2,B4,B6,B8}` should predict clean-timing probability, calibrated event time, and per-event uncertainty better than the RF/App-A clean-timing classifier and the S04 inverse-variance combined time.  The falsifier is failure to beat the transparent inverse-variance timing score on held-out runs.

The result is mixed in the scientifically important way: the graph method is selected by the combined held-out score, but every method is bounded by the same internal-consensus target.  A shuffled-event or external timing label would be required before interpreting the clean probability as physical truth.  The run-block bootstrap captures transfer across the five held-out runs but not unmodelled detector-state changes outside the configured run set.

Systematic checks and caveats:

- The raw reproduction gate uses all configured runs and has zero tolerance.
- The event benchmark is restricted to events with at least three selected B-staves; single-stave B2-dominated events are outside S09's graph scope.
- The clean label is a same-event consistency proxy.  It is useful for operational timing quality, not for external particle identity or beam-time truth.
- The 1D-CNN entry is a deterministic convolutional filterbank surrogate because the ticket was run in a CPU-only dependency environment.
- Because features include calibrated node times, learned regressors are event-time combiners rather than raw waveform-only time pickoff models.
- The original `tn-ticket claim` command returned the known null pseudo-ticket output; this report records the manual one-ticket recovery in `result.json` and `manifest.json`.

## 6. Conclusion

The winner is **`graph_residual_message_passing_new`** by the predeclared combined score.  The practical conclusion is that explicit graph residual features provide the best operational B-stack consensus combiner in this ticket, but the absolute physics interpretation remains limited by the absence of external event-time truth.

## 7. Reproducibility

Command used:

```bash
uv run --with uproot --with awkward --with numpy --with pandas --with scikit-learn python scripts/s09_2380_event_level_graph_timing.py
```

Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `method_metrics.csv`, `run_heldout_metrics.csv`, `event_predictions.csv.gz`, `input_sha256.csv`, and `claimed_ticket.txt`.
