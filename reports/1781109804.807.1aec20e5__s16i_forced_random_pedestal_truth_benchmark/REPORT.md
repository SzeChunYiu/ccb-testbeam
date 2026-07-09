# S16i: Forced-Random Pedestal Provenance and Pretrigger Fallback Benchmark

## Abstract

Ticket `1781109804.807.1aec20e5` asks whether pretrigger quiet-proxy support remains associated with timing-tail risk after amplitude and topology matching.  I constructed leave-one-run-out intervention curves over runs `[58, 59, 60, 61, 62, 63, 64, 65]` and compared a transparent matched-strata estimator with ridge regression, histogram gradient-boosted trees, an MLP, a 1D-CNN, and a new quiet-gated CNN.  The named winner in `result.json` is **ridge** with MAE `0.000358` and 95% run-bootstrap CI `[0.000355, 0.000361]`.

The direct forced/random pedestal truth audit found `0` forced/random/pedestal keyword ROOT files and `0` HRDB files with `TRIGGER != 1` in the accessible B-stack mirror.  Therefore the benchmark below is explicitly a physics-event pretrigger fallback benchmark, not a direct electronics-pedestal validation.  The machine-readable audit is in `root_trigger_inventory.csv` and `forced_random_source_inventory.csv`.

| Provenance audit item | Value |
|---|---:|
| B-stack HRDB ROOT files scanned | 53 |
| ROOT files with `TRIGGER` inventory rows | 53 |
| Unique trigger codes observed | [1] |
| Files with non-beam trigger code | 0 |
| Forced/random keyword files | 0 |
| Forced/random keyword ROOT files | 0 |
| Dedicated forced/random pedestal ROOT found | False |

## Raw ROOT Reproduction Anchor

The raw files are the B-stack ROOT inputs under `/home/billy/ccb-data/extracted/root/root`.  The script hashes all `8` benchmark ROOT files and records their sizes in `raw_root_inventory.csv`.  The ROOT reproduction uses tree `h101`, branch `HRDv`, reshapes each event to an `8 x 18` stave/sample array, baseline subtracts the median of samples 0--3, and counts B-stack staves `B2`, `B4`, `B6`, and `B8` with amplitude above `1000` ADC counts.

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

Let `Z_i` denote the unobserved true forced/random pedestal-source label.  The provenance audit establishes that `Z_i` is not observed in the accessible ROOT mirror.  The fallback endpoint is therefore the train-fold pretrigger/tail support target `Y_i`, built from same-event pretrigger shape, amplitude, topology, and run metadata.  This makes the analysis a validation of an operational fallback score, not a causal claim about true non-beam pedestal events.

Let `Q_i` be quiet propensity, `A_i` the amplitude bin, `T_i` topology, `R_i` run, and `Y_i` the timing-tail risk proxy.  The support-matched intervention curve estimates

`mu(q) = E[ Y_i(q) | A_i, T_i, R_i held within observed support ]`.

The transparent estimator bins `(A_i, T_i, Q_i)` on training runs and predicts held-out run tail risk by matched-cell means, falling back to topology means when a cell is empty.  Learned models receive the same support variables and are evaluated only on held-out runs.

## Methods

All methods use leave-one-run-out splits.  The performance metric is mean absolute error against the intervention target `Y`.  Uncertainty is a run-block bootstrap with `500` resamples over held-out run metrics.  The compared methods are:

- `traditional_s16f_scorecard`: amplitude/topology/quiet matched-cell estimator.
- `ridge`: standardized linear ridge regression.
- `gradient_boosted_trees`: histogram gradient-boosted trees.
- `mlp`: two-layer tabular neural regressor.
- `cnn1d`: convolutional regressor over the compact waveform/proxy sequence.
- `pretrigger_gated_cnn`: new architecture; a 1D convolution multiplied by a learned quiet-proxy gate before the regression head.

## Results

| Method | Mean MAE | 95% CI low | 95% CI high | Ranking AUC |
|---|---:|---:|---:|---:|
| ridge | 0.000358 | 0.000355 | 0.000361 | 0.551917 |
| gradient_boosted_trees | 0.000809 | 0.000756 | 0.000882 | 0.619615 |
| cnn1d | 0.021789 | 0.018593 | 0.025543 | 0.566455 |
| pretrigger_gated_cnn | 0.024034 | 0.021993 | 0.026590 | 0.590659 |
| traditional_s16f_scorecard | 0.033752 | 0.033150 | 0.034414 | 0.577090 |
| mlp | 0.036993 | 0.024860 | 0.051468 | 0.596541 |

## Intervention Curve

| quiet_bin | n | quiet_mid | observed_tail | predicted_tail |
| --- | --- | --- | --- | --- |
| 0 | 1360 | 0.145489 | 0.936460 | 0.936434 |
| 1 | 1360 | 0.238113 | 0.838287 | 0.838241 |
| 2 | 1360 | 0.321204 | 0.737485 | 0.737454 |
| 3 | 1360 | 0.417844 | 0.635181 | 0.635195 |
| 4 | 1360 | 0.568294 | 0.497018 | 0.497048 |

The fitted curve is monotone in the expected direction: high quiet propensity strata have lower predicted timing-tail risk after matching on amplitude and topology.  The effect should be interpreted as a support diagnostic, not an operational veto, because the strongest dependence still shares structure with amplitude and topology.

## Systematics and Caveats

- **ROOT dependency:** branch-level recomputation requires `uproot` or PyROOT.  This artifact was generated with `uproot` when `raw_root_reproduction.status` is `recomputed_from_raw_root`; otherwise the report explicitly records `not_recomputed`.
- **True pedestal source absence:** no accessible HRDB ROOT file carries an independent forced/random/no-pulse B-stack trigger code or matching ROOT filename.  This is the dominant systematic and prevents promoting the fallback score to direct pedestal truth.
- **Support matching:** sparse matched cells fall back to topology-level means; this protects against extrapolation but increases bias in rare broad-topology cells.
- **Run blocking:** all reported CIs resample held-out run metrics, so row-level precision is not mistaken for run-generalization certainty.
- **Model multiplicity:** the winner is selected by point-estimate MAE; overlapping CIs should be read as weak evidence rather than decisive superiority.
- **Intervention interpretation:** the curve is causal only under no unmeasured confounding within amplitude/topology/run support.  It is best used to decide whether a future operational veto proposal deserves a full ROOT-enabled rerun.

## Conclusion

`ridge` is the named winner for this S16i run-held-out benchmark.  The intervention curve supports the qualitative ticket claim that quiet-proxy support contains information beyond gross amplitude/topology, but the caveats require a rerun with an independently logged non-beam forced/random pedestal ROOT source before an operational veto is proposed.
