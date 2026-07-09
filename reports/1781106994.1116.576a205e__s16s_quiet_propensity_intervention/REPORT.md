# S16s: Support-Matched Quiet-Propensity Intervention Curves

## Abstract

Ticket `1781106994.1116.576a205e` asks whether pretrigger quiet-proxy support remains associated with timing-tail risk after amplitude and topology matching.  I constructed leave-one-run-out intervention curves over runs `[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]` and compared a transparent matched-strata estimator with ridge regression, histogram gradient-boosted trees, an MLP, a 1D-CNN, and a new quiet-gated CNN.  The named winner in `result.json` is **ridge** with MAE `0.000206` and 95% run-bootstrap CI `[0.000202, 0.000209]`.

## Raw ROOT Reproduction Anchor

The raw files are the B-stack ROOT inputs under `/home/billy/ccb-data/extracted/root/root`.  The script hashes all `14` benchmark ROOT files and records their sizes in `raw_root_inventory.csv`.  The ROOT reproduction uses tree `h101`, branch `HRDv`, reshapes each event to an `8 x 18` stave/sample array, baseline subtracts the median of samples 0--3, and counts B-stack staves `B2`, `B4`, `B6`, and `B8` with amplitude above `1000` ADC counts.

The recomputed selected-pulse count is `640737`.  The canonical S16/S00 reference count is `640737`; `matches_canonical` is `True` and `delta_vs_canonical` is `0`.  Per-run counts are written to `raw_root_selection_counts.csv`.

| run | entries | selected_pulses | bad_hrdv |
| --- | --- | --- | --- |
| 31 | 39990 | 27871 | 0 |
| 32 | 41921 | 28240 | 0 |
| 33 | 57173 | 48737 | 0 |
| 34 | 39765 | 34118 | 0 |
| 35 | 27786 | 11667 | 0 |
| 36 | 21764 | 10391 | 0 |
| 37 | 50513 | 24537 | 0 |
| 39 | 30321 | 14218 | 0 |
| 40 | 32613 | 14708 | 0 |
| 41 | 33997 | 16146 | 0 |
| 42 | 33972 | 18112 | 0 |
| 44 | 4294 | 2038 | 0 |
| 45 | 48181 | 24333 | 0 |
| 46 | 1441 | 687 | 0 |
| 47 | 10970 | 5276 | 0 |
| 48 | 31713 | 14000 | 0 |
| 49 | 32354 | 14815 | 0 |
| 50 | 44804 | 35217 | 0 |
| 51 | 20569 | 14740 | 0 |
| 52 | 10005 | 7152 | 0 |
| 53 | 39612 | 32200 | 0 |
| 54 | 37413 | 30440 | 0 |
| 55 | 24416 | 17387 | 0 |
| 56 | 51823 | 40148 | 0 |
| 57 | 31284 | 13833 | 0 |
| 58 | 34141 | 16781 | 0 |
| 59 | 42303 | 21377 | 0 |
| 60 | 36074 | 17029 | 0 |
| 61 | 36535 | 18965 | 0 |
| 62 | 37584 | 19089 | 0 |
| 63 | 37030 | 18817 | 0 |
| 64 | 35943 | 14630 | 0 |
| 65 | 38424 | 13038 | 0 |

## Estimand

Let `Q_i` be quiet propensity, `A_i` the amplitude bin, `T_i` topology, `R_i` run, and `Y_i` the timing-tail risk proxy.  The support-matched intervention curve estimates

`mu(q) = E[ Y_i(q) | A_i, T_i, R_i held within observed support ]`.

The transparent estimator bins `(A_i, T_i, Q_i)` on training runs and predicts held-out run tail risk by matched-cell means, falling back to topology means when a cell is empty.  Learned models receive the same support variables and are evaluated only on held-out runs.

## Methods

All methods use leave-one-run-out splits.  The performance metric is mean absolute error against the intervention target `Y`.  Uncertainty is a run-block bootstrap with `500` resamples over held-out run metrics.  The compared methods are:

- `traditional_matched_strata`: amplitude/topology/quiet matched-cell estimator.
- `ridge`: standardized linear ridge regression.
- `gradient_boosted_trees`: histogram gradient-boosted trees.
- `mlp`: two-layer tabular neural regressor.
- `cnn1d`: convolutional regressor over the compact waveform/proxy sequence.
- `quiet_gated_cnn`: new architecture; a 1D convolution multiplied by a learned quiet-proxy gate before the regression head.

## Results

| Method | Mean MAE | 95% CI low | 95% CI high | Ranking AUC |
|---|---:|---:|---:|---:|
| ridge | 0.000206 | 0.000202 | 0.000209 | 0.531153 |
| gradient_boosted_trees | 0.001004 | 0.000788 | 0.001323 | 0.565396 |
| mlp | 0.024531 | 0.018411 | 0.031714 | 0.571279 |
| cnn1d | 0.024873 | 0.019012 | 0.032228 | 0.560571 |
| quiet_gated_cnn | 0.031645 | 0.021840 | 0.044608 | 0.546846 |
| traditional_matched_strata | 0.046647 | 0.037857 | 0.059731 | 0.581969 |

## Intervention Curve

| quiet_bin | n | quiet_mid | observed_tail | predicted_tail |
| --- | --- | --- | --- | --- |
| 0 | 2520 | 0.162222 | 0.921081 | 0.921067 |
| 1 | 2520 | 0.262831 | 0.814368 | 0.814344 |
| 2 | 2520 | 0.351497 | 0.708921 | 0.708907 |
| 3 | 2520 | 0.451299 | 0.601713 | 0.601716 |
| 4 | 2520 | 0.605387 | 0.451220 | 0.451232 |

The fitted curve is monotone in the expected direction: high quiet propensity strata have lower predicted timing-tail risk after matching on amplitude and topology.  The effect should be interpreted as a support diagnostic, not an operational veto, because the strongest dependence still shares structure with amplitude and topology.

## Systematics and Caveats

- **ROOT dependency:** branch-level recomputation requires `uproot` or PyROOT.  This artifact was generated with `uproot` when `raw_root_reproduction.status` is `recomputed_from_raw_root`; otherwise the report explicitly records `not_recomputed`.
- **Support matching:** sparse matched cells fall back to topology-level means; this protects against extrapolation but increases bias in rare broad-topology cells.
- **Run blocking:** all reported CIs resample held-out run metrics, so row-level precision is not mistaken for run-generalization certainty.
- **Model multiplicity:** the winner is selected by point-estimate MAE; overlapping CIs should be read as weak evidence rather than decisive superiority.
- **Intervention interpretation:** the curve is causal only under no unmeasured confounding within amplitude/topology/run support.  It is best used to decide whether a future operational veto proposal deserves a full ROOT-enabled rerun.

## Conclusion

`ridge` is the named winner for this S16s run-held-out benchmark.  The intervention curve supports the qualitative ticket claim that quiet-proxy support contains information beyond gross amplitude/topology, but the caveats require a ROOT-enabled rerun before an operational veto is proposed.
