# Study report: P03f - B4-B6 pair asymmetry closure

- **Ticket:** 1781034869.1093.1ffd40cb
- **Author:** testbeam-laptop-3
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one run out across sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.json`

## Question

P03d repeatedly identified B4-B6 as the unstable pair.  This follow-up asks whether the offset is adequately described by a geometry/TOF constant, by train-derived template-phase bias, or by a per-stave waveform-calibration mismatch that requires learned waveform corrections.

## Raw-ROOT reproduction gate

The selected-pulse count gate was rerun directly from raw ROOT before model training.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimand and equations

For event `i` and stave `s`, the train-template phase pickoff is `t_is`.  The nominal TOF-corrected time is

`tau_is = t_is - x_s v_TOF`, with `x_s` fixed by the 2 cm B-stack spacing and `v_TOF = 0.078 ns/cm`.

The raw B4-B6 asymmetry target is

`r_i = tau_i,B4 - tau_i,B6`.

The traditional pair corrections predict a train-derived pair bias `f_pair(x_i)` and form `e_i = r_i - f_pair(x_i)`.  The ML/NN arms instead fit per-stave residual corrections `g_s(z_is)` from that stave's waveform and pulse-shape features, then evaluate `e_i = (tau_i,B4 - g_B4(z_i,B4)) - (tau_i,B6 - g_B6(z_i,B6))` on the held-out run.  The primary closure score is

`C = sqrt(median(e)^2 + sigma68(e)^2)`, where `sigma68 = (q84 - q16)/2`.

This score treats a pure median offset and an irreducible pair spread as jointly relevant: a geometry-only explanation should drive the median term down but cannot reduce `sigma68`; a waveform-calibration explanation should also reduce the width on held-out runs.

## Methods

- `template_phase_nominal`: no correction after the fixed 2 cm geometry TOF term.
- `geometry_offset_median`: subtracts the train-run median B4-B6 residual, the direct geometry/TOF-offset test.
- `template_phase_bias_table`: a train-only 3x3 median lookup table in B4-B6 template-SSE and amplitude-ratio bins.
- `ridge_waveform`: per-stave ridge regression on normalized waveform samples plus pulse-shape scalars.
- `gradient_boosted_trees`: per-stave histogram gradient boosting on the same waveform feature table.
- `mlp_waveform`: per-stave two-layer neural MLP on standardized waveform and pulse-shape features.
- `cnn_1d_pair`: per-stave 1D convolution over waveform samples plus scalar side features.
- `sample_attention`: a new per-stave sample-attention regressor with scalar pulse context.

All template shapes, offset tables, scalers, regressors, and neural nets are fitted without the held-out run.  Event id, run id, event order, and held-out residuals are excluded from model inputs.

## Held-out run benchmark

|   heldout_run | method                    | family      |   n_events |    median_ns |   sigma68_ns |   closure_score_ns |   closure_ci_low |   closure_ci_high |
|--------------:|:--------------------------|:------------|-----------:|-------------:|-------------:|-------------------:|-----------------:|------------------:|
|            58 | geometry_offset_median    | traditional |         73 |  0           |     0.37     |            0.37    |          0       |           1       |
|            58 | template_phase_bias_table | traditional |         73 |  0           |     0.37     |            0.37    |          0       |           1       |
|            58 | ridge_waveform            | ml          |         73 |  2.05456     |     0.4707   |            2.10779 |          1.97798 |           2.25819 |
|            58 | sample_attention          | new_nn      |         73 |  2.23187     |     0.619477 |            2.31624 |          2.22813 |           2.47384 |
|            58 | gradient_boosted_trees    | ml          |         73 |  2.2075      |     1.01884  |            2.43128 |          2.27112 |           2.76725 |
|            58 | cnn_1d_pair               | nn          |         73 |  2.30312     |     0.812865 |            2.44235 |          2.28221 |           2.5782  |
|            58 | mlp_waveform              | nn          |         73 | -4.54635     |     0.369944 |            4.56137 |          4.54635 |           4.65503 |
|            58 | template_phase_nominal    | baseline    |         73 | -4.54635     |     0.37     |            4.56138 |          4.54635 |           4.65503 |
|            59 | geometry_offset_median    | traditional |        763 |  0           |     1        |            1       |          1       |           1.25    |
|            59 | template_phase_bias_table | traditional |        763 |  0           |     1        |            1       |          1       |           1.25    |
|            59 | ridge_waveform            | ml          |        763 |  1.99996     |     1.0122   |            2.24151 |          2.17991 |           2.30049 |
|            59 | gradient_boosted_trees    | ml          |        763 |  2.10384     |     0.939411 |            2.30405 |          2.26835 |           2.33644 |
|            59 | cnn_1d_pair               | nn          |        763 |  2.16792     |     0.966656 |            2.37367 |          2.30385 |           2.44232 |
|            59 | sample_attention          | new_nn      |        763 |  2.68127     |     0.94861  |            2.84413 |          2.79257 |           2.89606 |
|            59 | mlp_waveform              | nn          |        763 | -4.47902     |     1.00212  |            4.58976 |          4.58764 |           4.6501  |
|            59 | template_phase_nominal    | baseline    |        763 | -4.48464     |     1        |            4.59478 |          4.59478 |           4.65559 |
|            60 | geometry_offset_median    | traditional |        808 |  0           |     1        |            1       |          0.75    |           1.22    |
|            60 | template_phase_bias_table | traditional |        808 |  0           |     1        |            1       |          0.75    |           1.25    |
|            60 | sample_attention          | new_nn      |        808 |  1.7866      |     0.8997   |            2.00035 |          1.94736 |           2.05454 |
|            60 | ridge_waveform            | ml          |        808 |  1.89566     |     0.87902  |            2.08955 |          2.0401  |           2.15105 |
|            60 | gradient_boosted_trees    | ml          |        808 |  1.9507      |     1.03042  |            2.20613 |          2.15739 |           2.2684  |
|            60 | cnn_1d_pair               | nn          |        808 |  2.08237     |     0.968811 |            2.29671 |          2.24451 |           2.35609 |
|            60 | mlp_waveform              | nn          |        808 | -4.32468     |     0.996815 |            4.43808 |          4.3882  |           4.49196 |
|            60 | template_phase_nominal    | baseline    |        808 | -4.32786     |     1        |            4.44189 |          4.39236 |           4.44189 |
|            61 | geometry_offset_median    | traditional |        933 |  0.5         |     1.25     |            1.34629 |          1.11803 |           1.34629 |
|            61 | template_phase_bias_table | traditional |        933 |  0.5         |     1.25     |            1.34629 |          1.11803 |           1.34629 |
|            61 | sample_attention          | new_nn      |        933 |  2.50438     |     0.952748 |            2.67949 |          2.61856 |           2.77126 |
|            61 | gradient_boosted_trees    | ml          |        933 |  2.61516     |     1.0171   |            2.80599 |          2.72595 |           2.91037 |
|            61 | cnn_1d_pair               | nn          |        933 |  2.7503      |     1.07991  |            2.95472 |          2.88249 |           3.06152 |
|            61 | ridge_waveform            | ml          |        933 |  2.73979     |     1.26648  |            3.01834 |          2.89448 |           3.1371  |
|            61 | mlp_waveform              | nn          |        933 | -4.12243     |     1.2551   |            4.30926 |          4.24936 |           4.76049 |
|            61 | template_phase_nominal    | baseline    |        933 | -4.12917     |     1.25     |            4.31423 |          4.24854 |           4.79497 |
|            62 | geometry_offset_median    | traditional |        807 |  0           |     1.01     |            1.01    |          0.75    |           1.25    |
|            62 | template_phase_bias_table | traditional |        807 |  0           |     1.01     |            1.01    |          0.75    |           1.25    |
|            62 | ridge_waveform            | ml          |        807 |  1.99739     |     0.975602 |            2.22292 |          2.15564 |           2.28209 |
|            62 | sample_attention          | new_nn      |        807 |  2.0937      |     0.900633 |            2.27919 |          2.20318 |           2.33978 |
|            62 | gradient_boosted_trees    | ml          |        807 |  2.10144     |     0.961931 |            2.31114 |          2.27025 |           2.3668  |
|            62 | cnn_1d_pair               | nn          |        807 |  2.22877     |     0.925523 |            2.4133  |          2.34891 |           2.48023 |
|            62 | mlp_waveform              | nn          |        807 | -4.54965     |     1.01257  |            4.66096 |          4.61211 |           4.71777 |
|            62 | template_phase_nominal    | baseline    |        807 | -4.55262     |     1.01     |            4.66331 |          4.61399 |           4.72111 |
|            63 | geometry_offset_median    | traditional |        370 |  0           |     1        |            1       |          0.75    |           1.25    |
|            63 | template_phase_bias_table | traditional |        370 |  0           |     1        |            1       |          0.75    |           1.25    |
|            63 | ridge_waveform            | ml          |        370 |  1.89004     |     0.983146 |            2.13045 |          2.03167 |           2.23935 |
|            63 | gradient_boosted_trees    | ml          |        370 |  2.00245     |     1.04074  |            2.25675 |          2.18297 |           2.34023 |
|            63 | sample_attention          | new_nn      |        370 |  2.14858     |     1.06484  |            2.39797 |          2.31443 |           2.49596 |
|            63 | cnn_1d_pair               | nn          |        370 |  2.22501     |     1.0265   |            2.45038 |          2.38217 |           2.58024 |
|            63 | mlp_waveform              | nn          |        370 | -4.52296     |     1.00053  |            4.6323  |          4.58485 |           4.6925  |
|            63 | template_phase_nominal    | baseline    |        370 | -4.52498     |     1        |            4.63416 |          4.58672 |           4.69446 |
|            65 | geometry_offset_median    | traditional |         66 |  7.10543e-15 |     1.15     |            1.15    |          0.5     |           1.65    |
|            65 | template_phase_bias_table | traditional |         66 |  7.10543e-15 |     1.15     |            1.15    |          0.5     |           1.6025  |
|            65 | ridge_waveform            | ml          |         66 |  1.89675     |     1.16051  |            2.22361 |          2.03555 |           2.496   |
|            65 | sample_attention          | new_nn      |         66 |  2.14945     |     1.06059  |            2.39686 |          2.10918 |           2.57214 |
|            65 | gradient_boosted_trees    | ml          |         66 |  2.09822     |     1.17482  |            2.40473 |          2.16046 |           2.59569 |
|            65 | cnn_1d_pair               | nn          |         66 |  2.12078     |     1.23784  |            2.4556  |          2.04913 |           2.75604 |
|            65 | mlp_waveform              | nn          |         66 | -4.54954     |     1.1461   |            4.69168 |          4.57332 |           4.82077 |
|            65 | template_phase_nominal    | baseline    |         66 | -4.55437     |     1.15     |            4.69731 |          4.58173 |           4.79503 |

## Pooled run-block bootstrap

| method                    |   n_events |   median_ns |   sigma68_ns |   closure_score_ns |   closure_ci_low |   closure_ci_high |
|:--------------------------|-----------:|------------:|-------------:|-------------------:|-----------------:|------------------:|
| geometry_offset_median    |       3820 |     0       |      1.25    |            1.25    |          1       |           1.25    |
| template_phase_bias_table |       3820 |     0       |      1.25    |            1.25    |          0.75    |           1.25    |
| ridge_waveform            |       3820 |     2.0688  |      1.12982 |            2.3572  |          2.11169 |           2.69709 |
| gradient_boosted_trees    |       3820 |     2.1385  |      1.07715 |            2.39446 |          2.2488  |           2.59933 |
| sample_attention          |       3820 |     2.27123 |      1.01317 |            2.48696 |          2.14098 |           2.75542 |
| cnn_1d_pair               |       3820 |     2.27895 |      1.04643 |            2.50771 |          2.34128 |           2.751   |
| mlp_waveform              |       3820 |    -4.52162 |      1.20238 |            4.67876 |          4.44886 |           4.71105 |
| template_phase_nominal    |       3820 |    -4.52498 |      1.21172 |            4.68442 |          4.44189 |           4.71747 |

## Asymmetry diagnostics

|   heldout_run |   raw_median_ns |   raw_sigma68_ns |   raw_closure_score_ns |   template_shift_diff_corr |   log_amp_diff_corr |   waveform_sse_diff_corr |
|--------------:|----------------:|-----------------:|-----------------------:|---------------------------:|--------------------:|-------------------------:|
|            58 |        -4.54635 |             0.37 |                4.56138 |                          1 |           0.414531  |               -0.707248  |
|            59 |        -4.48464 |             1    |                4.59478 |                          1 |           0.0820746 |                0.0189339 |
|            60 |        -4.32786 |             1    |                4.44189 |                          1 |          -0.0118972 |                0.0471061 |
|            61 |        -4.12917 |             1.25 |                4.31423 |                          1 |           0.141854  |               -0.0351453 |
|            62 |        -4.55262 |             1.01 |                4.66331 |                          1 |           0.141287  |                0.0181931 |
|            63 |        -4.52498 |             1    |                4.63416 |                          1 |           0.112304  |                0.0398353 |
|            65 |        -4.55437 |             1.15 |                4.69731 |                          1 |          -0.0918235 |                0.0129741 |

Per-run winners:

|   heldout_run | method                 |   closure_score_ns |
|--------------:|:-----------------------|-------------------:|
|            58 | geometry_offset_median |            0.37    |
|            59 | geometry_offset_median |            1       |
|            60 | geometry_offset_median |            1       |
|            61 | geometry_offset_median |            1.34629 |
|            62 | geometry_offset_median |            1.01    |
|            63 | geometry_offset_median |            1       |
|            65 | geometry_offset_median |            1.15    |

## Systematics and leakage controls

The dominant systematic is run-to-run non-stationarity: run 58 and run 65 have small B4-B6 samples, so their CIs are broad and run-block intervals are quoted alongside event bootstrap intervals.  A second systematic is target circularity: models learn a residual of the template-phase measurement, not an external truth time.  Therefore a winner demonstrates predictive closure of the observed B4-B6 asymmetry, not an absolute detector-time calibration.  The geometry-offset arm is intentionally strong for median closure, while waveform models are required to improve the width term to support the calibration-mismatch interpretation.

Leakage controls are stored in `leakage_checks.csv`; train/held-out event-id overlap is zero in every fold.  ML/NN features are per-stave normalized waveforms, pulse-shape scalars, and stave one-hot only.

## Verdict

`result.json` names `geometry_offset_median` as the winner by pooled closure score.  The result verdict is `traditional_offset_or_template_bias_wins`.

The constant geometry offset arm is the direct TOF-shift test.  If it removes most of the median but a waveform method wins the closure score, the residual B4-B6 signature is not just a fixed geometry offset; it contains transferable waveform-calibration structure.  If the geometry or template table wins, the evidence favors a low-dimensional offset/template-bias explanation over a learned per-stave waveform mismatch.

Queued follow-up proposal:

- `P03k: B-stack geometry-offset matrix from run-held-out pair closures` - Fit a single train-run B2/B4/B6/B8 stave-position offset matrix from all raw ROOT pair residuals, then test on held-out runs whether one geometry model closes every pair better than per-stave ridge, gradient-boosted trees, MLP, 1D-CNN, and sample-attention corrections with run-block bootstrap CIs. This would confirm or falsify the P03f interpretation that B4-B6 is mostly a fixed geometry/TOF offset rather than a waveform-calibration mismatch.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.py --config configs/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.json
```

Artifacts: `reproduction_match_table.csv`, `heldout_run_metrics.csv`, `pooled_run_block_summary.csv`, `heldout_predictions.csv`, `asymmetry_diagnosis.csv`, `winner_by_run.csv`, `ridge_cv.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
