# P10l: Tail-handle phase-drift null benchmark

- **Ticket ID:** `1781068158.1584.4e8d411c`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** `9bca5060a4ccbf76a8fad6f921b95547aecca494`
- **Monte Carlo:** none

## 0. Question

Do the P10h/P10e explicit tail and CFD handles fail because CFD phase distributions drift between run families, or because learned conditional template models are intrinsically unstable after amplitude, stave, q-template support, saturation proxy, current family, and run-family support are matched?

The pre-registered primary metric is held-out run-mean q-template MSE on CFD20-aligned normalized waveforms. Secondary metrics are tail MSE, live10 shift, template-fit timing sigma68/full RMS, accepted support fraction, and false-pass rate under shuffled-target, phase-shuffled, and family-label sentinels.

## 1. Reproduction Gate

The selected B-stave pulse table was rebuilt from raw `HRDv` waveforms before any modeling.

| quantity                        |   expected |   reproduced |   delta | pass   |
|:--------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| analysis selected rows          |     377362 |       377362 |       0 | True   |

## 2. Methods and Estimands

Split: run-family holdout. `holdout_sample_i` trains on run 64 and evaluates runs 44-57; `holdout_sample_ii` trains on runs 31-42 and evaluates runs 58-63 and 65. Every uncertainty interval in the main tables bootstraps held-out runs, not rows.

A selected waveform is baseline-subtracted, divided by peak amplitude, and interpolated onto the CFD20-relative grid `g`. For pulse `i` and method `m`, the primary loss is

`MSE_i(m) = |V_i|^{-1} sum_{j in V_i} (y_ij - yhat_ij(m))^2`,

where `V_i` is the finite aligned-sample set. The run-level score is the within-run mean, and the fold score is the unweighted mean over held-out runs. Tail residuals use the aligned tail sum on samples with relative grid >=2; tail MSE is the run mean of the squared tail residual. The live10 endpoint is the last post-peak grid sample above 10% amplitude, converted with the 10 ns sample period. Template timing residuals scan shifts from -1.5 to +1.5 samples and report `sigma68 = (Q84 - Q16)/2` plus full RMS.

Traditional comparator: frozen S01 empirical stave/amplitude-bin median templates plus train-only explicit-handle median residual tables. The handle table keys are amplitude region, stave, rise width, CFD phase region, tail-shape region, saturation proxy, and current family. Sparse full cells fall back to a looser handle table, then to S01.

ML/NN panel: standardized ridge, ExtraTrees, shallow stochastic gradient-boosted trees, tabular MLP, 1D-CNN over the normalized waveform plus tabular handles, and the new `phase_gated_cnn_new`, which multiplies convolutional channels by a learned sigmoid gate from the phase/tail handle vector. All methods exclude run id, event id, and target leakage features.

## 3. Head-to-Head Benchmark

`result.json` names **ridge** as the winner by lowest held-out q-template MSE among non-control methods. Its mean q-template MSE is `0.0691821`.

| method                                | class                   |   q_template_mse | fold_q_ci95                                                                   |   tail_mse |   tail_abs |   timing_sigma68_ns |
|:--------------------------------------|:------------------------|-----------------:|:------------------------------------------------------------------------------|-----------:|-----------:|--------------------:|
| ridge                                 | ml_linear               |        0.0691821 | holdout_sample_i [0.06369, 0.085107]; holdout_sample_ii [0.059042, 0.066012]  |    2.36457 |   1.0169   |             2.09821 |
| extra_trees                           | ml_tree_control         |        0.0764005 | holdout_sample_i [0.069534, 0.095612]; holdout_sample_ii [0.062544, 0.073963] |    3.66479 |   0.956213 |             1.65179 |
| gradient_boosted_trees                | ml_tree                 |        0.0890433 | holdout_sample_i [0.083425, 0.10793]; holdout_sample_ii [0.075785, 0.08617]   |    4.94112 |   1.31521  |             2.27679 |
| phase_shuffled_gradient_boosted_trees | sentinel                |        0.0892466 | holdout_sample_i [0.083707, 0.10833]; holdout_sample_ii [0.075885, 0.08619]   |    4.93218 |   1.31469  |             2.27679 |
| phase_gated_cnn_new                   | new_neural_architecture |        0.114958  | holdout_sample_i [0.12708, 0.15041]; holdout_sample_ii [0.084766, 0.093931]   |    6.63892 |   1.33266  |             5.08929 |
| mlp                                   | neural_tabular          |        0.122806  | holdout_sample_i [0.13157, 0.15577]; holdout_sample_ii [0.095391, 0.10463]    |    9.35657 |   1.58897  |             3.39286 |
| cnn_1d                                | neural_waveform         |        0.127991  | holdout_sample_i [0.14069, 0.16799]; holdout_sample_ii [0.090059, 0.10772]    |    8.05161 |   1.47428  |             4.82143 |
| handle_residual                       | traditional_strong      |        0.136973  | holdout_sample_i [0.12621, 0.16466]; holdout_sample_ii [0.12114, 0.13059]     |    9.72335 |   1.70711  |             2.32143 |
| family_label_sentinel                 | sentinel                |        0.151972  | holdout_sample_i [0.15768, 0.18414]; holdout_sample_ii [0.12349, 0.13733]     |   14.5682  |   2.12054  |             3.21429 |
| shuffled_target_extra_trees           | sentinel                |        0.156349  | holdout_sample_i [0.16256, 0.18924]; holdout_sample_ii [0.12708, 0.14093]     |   15.1746  |   2.21834  |             4.28571 |
| s01_empirical                         | traditional_base        |        0.185187  | holdout_sample_i [0.18438, 0.21535]; holdout_sample_ii [0.15694, 0.17814]     |   14.9774  |   2.22811  |             3.73036 |

The same head-to-head q-template MSE ranking is plotted in `fig_head_to_head_q_mse.png`.

Fold-level deltas relative to the traditional explicit-handle baseline:

| fold              |   n_eval |   handle_residual_q_mse | handle_residual_q_mse_ci                   |   ridge_q_mse |   delta_ridge_minus_handle_q_mse | delta_ridge_minus_handle_q_mse_ci            |   gradient_boosted_trees_q_mse |   delta_gradient_boosted_trees_minus_handle_q_mse | delta_gradient_boosted_trees_minus_handle_q_mse_ci   |   mlp_q_mse |   delta_mlp_minus_handle_q_mse | delta_mlp_minus_handle_q_mse_ci               |   cnn_1d_q_mse |   delta_cnn_1d_minus_handle_q_mse | delta_cnn_1d_minus_handle_q_mse_ci            |   phase_gated_cnn_new_q_mse |   delta_phase_gated_cnn_new_minus_handle_q_mse | delta_phase_gated_cnn_new_minus_handle_q_mse_ci   |
|:------------------|---------:|------------------------:|:-------------------------------------------|--------------:|---------------------------------:|:---------------------------------------------|-------------------------------:|--------------------------------------------------:|:-----------------------------------------------------|------------:|-------------------------------:|:----------------------------------------------|---------------:|----------------------------------:|:----------------------------------------------|----------------------------:|-----------------------------------------------:|:--------------------------------------------------|
| holdout_sample_i  |    17604 |                0.14836  | [0.12621366611856505, 0.16465755904060198] |     0.075919  |                       -0.0724414 | [-0.08050181369962006, -0.06318349999030663] |                      0.0972254 |                                        -0.0511351 | [-0.05752041354149741, -0.04292625312914011]         |    0.145532 |                    -0.00282797 | [-0.010710130923900807, 0.006968112570768272] |       0.156804 |                        0.00844367 | [0.0028465873711216163, 0.015072425595097317] |                   0.140655  |                                    -0.00770589 | [-0.015842409212340935, 0.0009202935385029089]    |
| holdout_sample_ii |    13749 |                0.125585 | [0.12114000458679011, 0.130588924266325]   |     0.0624452 |                       -0.0631394 | [-0.06649964754671389, -0.0606805901848391]  |                      0.0808612 |                                        -0.0447234 | [-0.04884149480211004, -0.041040958891475784]        |    0.10008  |                    -0.0255045  | [-0.027436810862207648, -0.0234886853299489]  |       0.099177 |                       -0.0264076  | [-0.03319442271546141, -0.018168339648923983] |                   0.0892622 |                                    -0.0363225  | [-0.03847143319556772, -0.03346620158797544]      |

## 4. Phase-Drift Null and Support Regions

A phase-drift explanation predicts that removing CFD phase information from the learned model should erase most gains and that gains should concentrate in a few phase cells. The phase-shuffled gradient-boosted sentinel tests this directly: training phase values and phase-region labels are permuted inside the training fold while all other supports are preserved.

| fold              | train_eval_run_overlap   |   train_eval_key_overlap | uses_run_or_event_features   | extra_trees_beats_handle_q_ci   | shuffled_target_beats_real   | phase_shuffled_beats_gbt   | family_label_sentinel_beats_real   |   false_pass_rate_under_sentinels | leakage_alarm   |
|:------------------|:-------------------------|-------------------------:|:-----------------------------|:--------------------------------|:-----------------------------|:---------------------------|:-----------------------------------|----------------------------------:|:----------------|
| holdout_sample_i  | []                       |                        0 | False                        | True                            | False                        | False                      | False                              |                          0.333333 | False           |
| holdout_sample_ii | []                       |                        0 | False                        | True                            | False                        | False                      | False                              |                          0.333333 | False           |

Most handle-favorable region summaries by weighted q-template MSE delta:

| dimension         | region            |   n_cells |   n_eval |   mean_delta_handle_minus_s01_q_mse |   mean_delta_extra_trees_minus_handle_q_mse |   mean_delta_extra_trees_minus_handle_timing_abs_ns |   handle_win_cell_fraction |   extra_trees_q_win_cell_fraction |
|:------------------|:------------------|----------:|---------:|------------------------------------:|--------------------------------------------:|----------------------------------------------------:|---------------------------:|----------------------------------:|
| amp_region        | a1000_1500        |        80 |     3750 |                          -0.247908  |                                  -0.284636  |                                           -1.23272  |                   0.575    |                          0.7625   |
| tail_shape_region | tail_compact      |       210 |    10408 |                          -0.112402  |                                  -0.179892  |                                           -1.19657  |                   0.547619 |                          0.82381  |
| rise_width_region | rise_narrow       |       190 |     9396 |                          -0.0924109 |                                  -0.15372   |                                           -1.27463  |                   0.510526 |                          0.978947 |
| stave             | B2                |       269 |    15203 |                          -0.0858377 |                                  -0.0847598 |                                           -1.32315  |                   0.69145  |                          0.862454 |
| cfd_phase_region  | phase_mid         |       173 |     8517 |                          -0.0701706 |                                  -0.0673623 |                                           -0.84302  |                   0.549133 |                          0.843931 |
| current_family    | high_20nA         |       253 |    15099 |                          -0.0642868 |                                  -0.083174  |                                           -1.17112  |                   0.55336  |                          0.881423 |
| run_family        | sample_i_analysis |       253 |    15099 |                          -0.0642868 |                                  -0.083174  |                                           -1.17112  |                   0.55336  |                          0.881423 |
| saturation_region | unsaturated       |       479 |    23506 |                          -0.0634859 |                                  -0.0850569 |                                           -0.843354 |                   0.530271 |                          0.832985 |

Least handle-favorable region summaries:

| dimension         | region          |   n_cells |   n_eval |   mean_delta_handle_minus_s01_q_mse |   mean_delta_extra_trees_minus_handle_q_mse |   mean_delta_extra_trees_minus_handle_timing_abs_ns |   handle_win_cell_fraction |   extra_trees_q_win_cell_fraction |
|:------------------|:----------------|----------:|---------:|------------------------------------:|--------------------------------------------:|----------------------------------------------------:|---------------------------:|----------------------------------:|
| stave             | B8              |        63 |     2240 |                        -0.000576442 |                                  -0.0670142 |                                           -1.1971   |                  0.0634921 |                          0.984127 |
| tail_shape_region | tail_long       |       130 |     6608 |                        -0.00324808  |                                  -0.0218234 |                                           -1.95899  |                  0.5       |                          1        |
| saturation_region | boundary        |        52 |     2786 |                        -0.00374477  |                                  -0.0248206 |                                           -1.94993  |                  0.5       |                          1        |
| amp_region        | a6800_10000     |        53 |     2939 |                        -0.00562109  |                                  -0.0321944 |                                           -2.80708  |                  0.54717   |                          0.962264 |
| saturation_region | saturated_proxy |        21 |     1110 |                        -0.00628833  |                                  -0.0355173 |                                           -3.81757  |                  0.428571  |                          0.904762 |
| stave             | B6              |        93 |     3934 |                        -0.00752664  |                                  -0.0548345 |                                           -0.697833 |                  0.333333  |                          0.741935 |
| amp_region        | a2200_3200      |        97 |     4904 |                        -0.0114858   |                                  -0.0334652 |                                           -0.453528 |                  0.402062  |                          0.773196 |
| amp_region        | a4700_6800      |       101 |     4801 |                        -0.0154555   |                                  -0.0361092 |                                           -0.812851 |                  0.39604   |                          0.970297 |

## 5. Falsification

Pre-registration: ML is considered to beat the strong traditional baseline only if the ML-minus-handle q-template MSE bootstrap CI is wholly below zero in a run-held-out fold and sentinel false-pass controls do not beat their matched real models. The multiple-comparison family contains five primary learned challengers to the handle baseline: ridge, gradient-boosted trees, MLP, 1D-CNN, and phase-gated CNN; p-values or sign tests should therefore be interpreted with that five-way search in mind.

False-pass sentinel rates by fold are recorded in `leakage_checks.csv`; the maximum observed rate is `0.333`. A leakage alarm would have falsified any adoption claim.

## 6. Systematics and Caveats

- **Benchmark/selection:** all methods use identical held-out rows per fold, but row caps make this a support-balanced benchmark rather than a full-population production fit.
- **Data leakage:** train and evaluation runs are disjoint; event numbers, run ids, and target residuals are not used as features. Sentinel models explicitly test shuffled targets, phase shuffling, and family labels.
- **Metric misuse:** q-template MSE is a waveform-template metric, not a physics truth label. Timing sigma68 and RMS are template-fit diagnostics, not external time-of-flight truth.
- **Post-hoc selection:** the model panel, primary metric, run bootstrap unit, and sentinel alarms follow the claimed ticket and are fixed in the config/script.
- **Raw-data limitation:** the reduced ROOT bundle lacks external beam-current scalers and truth labels, so phase drift is inferred from waveform-handle support rather than a calibrated external phase monitor.

## 7. Findings and Next Steps

Explicit handle residuals have limited promotable support: at least one fold improves over S01 by q-template CI, but support is region-specific. The learned panel has at least one CI win over the traditional handle method; the benchmark winner is ridge, subject to the sentinel audit. No sentinel alarm fired under the predeclared target-shuffle, phase-shuffle, and family-label controls.

Queued follow-up candidate: P10m freeze phase-gated tail template and test downstream timing/charge consumers. Expected information gain: It would decide whether the P10l waveform-template winner improves independent pair-timing and charge-consumer outcomes after freezing the model, instead of only improving q-template reconstruction.

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `fold_run_metrics.csv`, `fold_summary.csv`, `support_map.csv`, `support_region_summary.csv`, `model_diagnostics.csv`, `handle_occupancy.csv`, `leakage_checks.csv`, and `fig_head_to_head_q_mse.png`.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.py --config configs/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.yaml
```
