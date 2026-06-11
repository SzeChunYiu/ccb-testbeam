# P01k: event-block timing leakage atomizer

**Ticket:** `1781048235.687.33ce5940`
**Worker:** `testbeam-laptop-3`
**Date:** 2026-06-11
**Input:** raw B-stack ROOT under `data/root/root`
**Code:** `scripts/p01k_1781048235_687_33ce5940_event_block_timing_leakage_atomizer.py` with config `configs/p01k_1781048235_687_33ce5940_event_block_timing_leakage_atomizer.json`

## 0. Question
Which atomic nuisance coordinates let event-block shuffled controls recover the
nominal P01 residual-timing gain, and does any ML/NN model beat a strong
traditional hand-shape residual model under leave-one-run-out evaluation?

The pre-registered primary metric is the held-out event-block bootstrap
`sigma68` of same-event downstream B4/B6/B8 pair residuals. The decision rule is
lower `sigma68`; paired bootstrap intervals use the held-out event as the
resampling block.

## 1. Reproduction from raw ROOT
Before modelling, the script independently read `HRDv` from each raw B-stack
ROOT file, subtracted the median of samples 0-3, selected B2/B4/B6/B8 pulses
with amplitude greater than 1000 ADC, and counted selected pulses.

| quantity                      | report_value | reproduced | delta | tolerance | pass |
| ----------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses | 640737       | 640737     | 0     | 0         | True |

This exactly reproduces the canonical S00/P01 count. The sha256 digest of every
raw ROOT input is recorded in `input_sha256.csv`.

## 2. Methods
For pulse `i`, the CFD20 time is

`t_i = 10 ns * (k_i - 1 + (0.2 A_i - y_{i,k_i-1})/(y_{i,k_i} - y_{i,k_i-1}))`,

where `k_i` is the first sample above 20 percent of the pulse maximum. For each
downstream stave pulse, the residual-correction target was

`r_i = (t_i - x_s/v) - mean_{j in same event, j != i}(t_j - x_{s_j}/v)`,

with `v^-1 = 0.078 ns/cm` and `x_s` spaced by 2 cm for B4/B6/B8. Models predict
`r_i`; corrected times are `t_i - rhat_i`. Evaluation uses all three pairwise
differences per complete B4/B6/B8 event.

The strong traditional method is a ridge correction on engineered pulse-shape
features: pulse areas, tail fraction, widths, peak sample, rise/fall summaries,
log-amplitude, and stave one-hot. The ML/NN set is: raw-waveform ridge,
histogram gradient-boosted trees, an MLP, a 1D-CNN, and a new atom-gated 1D-CNN
whose convolution channels are multiplicatively gated by waveform-derived atom
features. Production models exclude run ID, event ID, event order, and
other-stave times.

Hyperparameters were selected independently inside each held-out run using
GroupKFold by training run and target MAE. Best CV rows by held-out run:

| heldout_run | model                        | param                                                                  | mae_ns |
| ----------- | ---------------------------- | ---------------------------------------------------------------------- | ------ |
| 42          | atom_gated_cnn               | channels=8                                                             | 1.531  |
| 42          | cnn_1d_waveform              | channels=16                                                            | 1.600  |
| 42          | gradient_boosted_trees       | l2_regularization=0.0,learning_rate=0.04,max_iter=90,max_leaf_nodes=15 | 1.497  |
| 42          | mlp_waveform                 | alpha=0.0003,hidden_layer_sizes=[64, 32]                               | 1.541  |
| 42          | ridge_raw_waveform           | alpha=100.0                                                            | 1.563  |
| 42          | traditional_hand_shape_ridge | alpha=100.0                                                            | 1.660  |
| 57          | atom_gated_cnn               | channels=16                                                            | 1.554  |
| 57          | cnn_1d_waveform              | channels=8                                                             | 1.592  |
| 57          | gradient_boosted_trees       | l2_regularization=0.0,learning_rate=0.04,max_iter=90,max_leaf_nodes=15 | 1.511  |
| 57          | mlp_waveform                 | alpha=0.0003,hidden_layer_sizes=[64, 32]                               | 1.585  |
| 57          | ridge_raw_waveform           | alpha=100.0                                                            | 1.562  |
| 57          | traditional_hand_shape_ridge | alpha=100.0                                                            | 1.659  |
| 64          | atom_gated_cnn               | channels=8                                                             | 1.546  |
| 64          | cnn_1d_waveform              | channels=8                                                             | 1.594  |
| 64          | gradient_boosted_trees       | l2_regularization=0.0,learning_rate=0.04,max_iter=90,max_leaf_nodes=15 | 1.473  |
| 64          | mlp_waveform                 | alpha=0.0003,hidden_layer_sizes=[64, 32]                               | 1.491  |
| 64          | ridge_raw_waveform           | alpha=100.0                                                            | 1.553  |
| 64          | traditional_hand_shape_ridge | alpha=100.0                                                            | 1.661  |
| 65          | atom_gated_cnn               | channels=16                                                            | 1.532  |
| 65          | cnn_1d_waveform              | channels=8                                                             | 1.597  |
| 65          | gradient_boosted_trees       | l2_regularization=0.0,learning_rate=0.04,max_iter=90,max_leaf_nodes=15 | 1.476  |
| 65          | mlp_waveform                 | alpha=0.0001,hidden_layer_sizes=[32]                                   | 1.551  |
| 65          | ridge_raw_waveform           | alpha=100.0                                                            | 1.564  |
| 65          | traditional_hand_shape_ridge | alpha=100.0                                                            | 1.659  |

## 3. Head-to-head Benchmark
All rows below are evaluated on the same held-out runs `42, 57, 64, 65`.
Intervals are 95 percent event-block bootstrap CIs.

| method                       | sigma68_ns | ci_low | ci_high | delta_vs_cfd20_ns | full_rms_ns | tail_abs_gt_5ns | n_events |
| ---------------------------- | ---------- | ------ | ------- | ----------------- | ----------- | --------------- | -------- |
| gradient_boosted_trees       | 1.863      | 1.737  | 1.958   | -1.325            | 4.103       | 0.048           | 408      |
| ridge_raw_waveform           | 1.911      | 1.824  | 1.995   | -1.277            | 4.482       | 0.038           | 408      |
| traditional_hand_shape_ridge | 1.957      | 1.874  | 2.058   | -1.232            | 4.455       | 0.053           | 408      |
| mlp_waveform                 | 1.981      | 1.870  | 2.068   | -1.208            | 4.210       | 0.063           | 408      |
| cnn_1d_waveform              | 1.982      | 1.889  | 2.057   | -1.206            | 4.145       | 0.037           | 408      |
| atom_gated_cnn               | 2.047      | 1.921  | 2.177   | -1.141            | 3.623       | 0.056           | 408      |
| CFD20                        | 3.188      | 3.060  | 3.321   | 0.000             | 5.678       | 0.259           | 408      |

By run:

| heldout_run | method                       | sigma68_ns | ci_low | ci_high | full_rms_ns | timing_eval_rows |
| ----------- | ---------------------------- | ---------- | ------ | ------- | ----------- | ---------------- |
| 42          | ridge_raw_waveform           | 1.621      | 1.439  | 1.963   | 2.448       | 204              |
| 42          | traditional_hand_shape_ridge | 1.727      | 1.522  | 1.947   | 2.632       | 204              |
| 42          | mlp_waveform                 | 1.945      | 1.632  | 2.189   | 2.792       | 204              |
| 42          | gradient_boosted_trees       | 1.950      | 1.584  | 2.299   | 2.931       | 204              |
| 42          | cnn_1d_waveform              | 2.020      | 1.699  | 2.254   | 2.700       | 204              |
| 42          | atom_gated_cnn               | 2.117      | 1.832  | 2.467   | 2.979       | 204              |
| 42          | CFD20                        | 3.305      | 3.032  | 3.533   | 3.931       | 204              |
| 57          | cnn_1d_waveform              | 1.911      | 1.724  | 2.119   | 2.606       | 192              |
| 57          | ridge_raw_waveform           | 1.912      | 1.675  | 2.136   | 2.531       | 192              |
| 57          | traditional_hand_shape_ridge | 1.965      | 1.737  | 2.223   | 2.652       | 192              |
| 57          | mlp_waveform                 | 1.991      | 1.756  | 2.379   | 2.782       | 192              |
| 57          | gradient_boosted_trees       | 2.044      | 1.840  | 2.342   | 2.740       | 192              |
| 57          | atom_gated_cnn               | 2.212      | 1.785  | 2.527   | 2.869       | 192              |
| 57          | CFD20                        | 3.265      | 2.814  | 3.632   | 4.013       | 192              |
| 64          | gradient_boosted_trees       | 1.744      | 1.575  | 1.882   | 5.079       | 630              |
| 64          | atom_gated_cnn               | 1.889      | 1.754  | 2.022   | 4.228       | 630              |
| 64          | mlp_waveform                 | 1.900      | 1.758  | 2.029   | 5.188       | 630              |
| 64          | cnn_1d_waveform              | 1.961      | 1.834  | 2.059   | 5.222       | 630              |
| 64          | ridge_raw_waveform           | 1.971      | 1.858  | 2.085   | 5.798       | 630              |
| 64          | traditional_hand_shape_ridge | 1.996      | 1.821  | 2.121   | 5.707       | 630              |
| 64          | CFD20                        | 3.147      | 2.968  | 3.328   | 6.884       | 630              |
| 65          | ridge_raw_waveform           | 1.877      | 1.577  | 2.086   | 2.196       | 198              |
| 65          | traditional_hand_shape_ridge | 1.980      | 1.743  | 2.157   | 2.264       | 198              |
| 65          | cnn_1d_waveform              | 1.982      | 1.666  | 2.213   | 2.317       | 198              |
| 65          | gradient_boosted_trees       | 1.989      | 1.677  | 2.247   | 2.420       | 198              |
| 65          | atom_gated_cnn               | 2.178      | 1.883  | 2.484   | 2.674       | 198              |
| 65          | mlp_waveform                 | 2.210      | 1.825  | 2.467   | 2.897       | 198              |
| 65          | CFD20                        | 2.993      | 2.704  | 3.406   | 4.119       | 198              |

Winner: **gradient_boosted_trees**, `sigma68 = 1.863 ns`
with 95 percent CI `[1.737, 1.958] ns`.

## 4. Event-block Shuffled Atomizer
For each held-out run, train targets were permuted as complete event blocks
before fitting atom-only ridge controls. These models should not carry physical
single-pulse timing information; high recovered gain means the coordinate can
transport run/event composition structure into the timing metric.

| atom                 | pooled_weighted_sigma68_ns | control_gain_ns | control_gain_fraction_of_nominal | max_fold_control_gain_fraction |
| -------------------- | -------------------------- | --------------- | -------------------------------- | ------------------------------ |
| stave+topology       | 2.036                      | 1.152           | 0.869                            | 0.954                          |
| run_family+stave     | 2.036                      | 1.152           | 0.869                            | 0.954                          |
| stave                | 2.036                      | 1.152           | 0.869                            | 0.954                          |
| stave+amplitude      | 2.037                      | 1.152           | 0.869                            | 0.925                          |
| peak_phase           | 3.149                      | 0.039           | 0.030                            | 0.104                          |
| event_block+topology | 3.167                      | 0.022           | 0.016                            | 0.000                          |
| event_block          | 3.167                      | 0.022           | 0.016                            | 0.000                          |
| topology             | 3.167                      | 0.022           | 0.016                            | 0.000                          |
| run_family           | 3.167                      | 0.022           | 0.016                            | 0.000                          |
| anomaly              | 3.168                      | 0.020           | 0.015                            | 0.025                          |
| dropout              | 3.214                      | -0.025          | -0.019                           | 0.019                          |
| baseline             | 3.237                      | -0.049          | -0.037                           | -0.023                         |

Atoms crossing the warning fraction `0.60`:
**stave+topology, run_family+stave, stave, stave+amplitude**.

## 5. Falsification and Systematics
The falsification test was pre-registered in the ticket: event-block,
per-coordinate shuffled controls must not recover most of the nominal gain. A
control-gain fraction above 0.6 is treated as a failure for physical
interpretation of the corresponding coordinate. The primary model comparison
uses a single pre-registered metric, but six model families and seventeen atom
controls were tried; the report therefore treats model ranking and atom ranking
as exploratory unless bootstrap intervals are well separated.

Systematic checks:

| check                       | value | pass_all | detail                                                                         |
| --------------------------- | ----- | -------- | ------------------------------------------------------------------------------ |
| production_feature_audit    | 0     | True     | production models exclude run id, event id, event order, and other-stave times |
| train_heldout_event_overlap | 0     | True     | event IDs are run-local and heldout run is excluded                            |
| train_heldout_run_overlap   | 0     | True     | leave-one-run-out split                                                        |

Residual risks are the small number of complete held-out events in runs 42, 57,
and 65; imperfect representation of baseline/saturation atoms because the raw
scanner stores baseline-subtracted normalized waves; and the fact that
event-block shuffled targets diagnose leakage-like composition recovery, not a
specific hardware causal pathway by themselves.

## 6. Caveats
The atom-gated CNN is intentionally small to keep the laptop study reproducible;
it is not a claim that this is the globally optimal neural architecture. The
best traditional and neural methods are close relative to the bootstrap width,
so practical preference should include stability and leakage-control behavior,
not only the point estimate. No Monte Carlo truth is used.

## 7. Verdict and Hypothesis
The benchmark winner is `gradient_boosted_trees`. The atomizer indicates that the
largest shuffled-control recovery is carried by `stave+topology`.
The working hypothesis is that part of the P01/P01f timing gain is transported
by run-family/event-block/topology composition interacting with waveform shape,
rather than by a purely local pulse-time correction. A decisive follow-up should
force atom-matched train/evaluation strata and require the event-block shuffled
control to collapse toward CFD20 while the nominal model retains its gain.

## 8. Reproducibility
Run:

```bash
/home/billy/anaconda3/bin/python scripts/p01k_1781048235_687_33ce5940_event_block_timing_leakage_atomizer.py --config configs/p01k_1781048235_687_33ce5940_event_block_timing_leakage_atomizer.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`,
`model_fold_summary.csv`, `model_pooled_summary.csv`, `model_cv.csv`,
`atom_leakage_by_fold.csv`, `atom_leakage_summary.csv`,
`heldout_pair_residuals.csv`, and the three `fig_*.png` plots.
