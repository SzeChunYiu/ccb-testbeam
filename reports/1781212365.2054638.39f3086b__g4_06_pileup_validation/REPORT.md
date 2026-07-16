# G4-06 Pile-up Validation

Ticket `1781212365.2054638.39f3086b` asks whether pile-up corruption of charge/time can be validated against simulated or controlled multi-hit truth, and whether recovery models remain sane on real data. This report uses the raw experimental ROOT files to reproduce the canonical selected-pulse count, then builds a controlled two-pulse truth sample by overlaying real baseline-subtracted B-stack waveforms at known separations. The winner written to `result.json` is **gradient_boosted_trees**, with run-bootstrap mean absolute separation error 21.85 ns and 95% CI [19.95, 23.84] ns.

## Raw ROOT Reproduction

Input raw ROOT directory: `data/root/root`. The reproduction reads `h101/HRDv` from `hrdb_run_*.root`, subtracts the median of samples 0--3 channel by channel, keeps even B-stack readouts B2/B4/B6/B8, and applies the established peak-amplitude threshold `A > 1000` ADC. The reproduced total is **640737** selected B-stave pulses, compared with the expected **640737**; delta is **0**.

## GEANT4 Truth Source Audit

The GEANT4 ROOT candidate audit is saved in `g4_root_schema_audit.csv`. The controlled overlay benchmark is used as the primary truth source because it provides exact event-level separation and charge labels while preserving real pulse shapes and noise. GEANT4 remains relevant for absolute multiplicity/rate priors, but its current tree does not provide a one-to-one event key join to the real HRD waveforms.

## Methods

For a clean normalized pulse template `s(t)`, a controlled pile-up waveform is

```text
x(t) = a_1 s_i(t) + a_2 s_j(t - Delta t) + epsilon(t),
```

where `s_i` and `s_j` are real selected raw waveforms, `Delta t` is drawn uniformly between 5 and 105 ns, and the amplitude ratio is varied to stress unequal overlaps. Clean controls use `a_2 = 0`. Evaluation is leave-run-out over runs `[42, 50, 57, 58, 60, 62, 64, 65]`; every model is trained on all other held-out-run overlays and scored on the excluded run.

The traditional method is a two-pulse template fit. For each candidate separation `Delta`, it solves

```text
min_{alpha,beta >= 0} ||x - alpha s - beta s_Delta||_2^2,
```

selects the lowest-residual separation, and declares pile-up only when the two-template residual improves over the one-template residual and the secondary amplitude is non-negligible. The ML panel uses the same normalized waveform information: ridge regression, gradient-boosted trees, an MLP, a 1D-CNN, and a compact self-attention network introduced here as the new architecture.

## Metrics

Primary metric is mean absolute error on true overlays:

```text
MAE_Delta = N_pile^{-1} sum_i |hat{Delta t_i} - Delta t_i|.
```

Secondary metrics are recovery efficiency within 20 ns, false pile-up rate on clean controls, ROC AUC, and average precision for the pile-up decision. Confidence intervals resample held-out runs with replacement, so they quantify run-to-run stability rather than row-level counting error.

## Run-Bootstrap Summary

| method | dt_mae | eff20 | fpr | auc |
| --- | --- | --- | --- | --- |
| gradient_boosted_trees | 21.85 [19.95, 23.84] | 0.601 [0.559, 0.643] | 0.293 [0.260, 0.328] | 0.922 [0.906, 0.938] |
| mlp | 22.98 [20.92, 24.91] | 0.577 [0.529, 0.622] | 0.561 [0.480, 0.654] | 0.826 [0.790, 0.858] |
| ridge | 23.99 [23.30, 24.64] | 0.500 [0.473, 0.528] | 0.895 [0.879, 0.911] | 0.783 [0.758, 0.808] |
| traditional_template_fit | 26.26 [25.64, 26.82] | 0.590 [0.573, 0.611] | 0.734 [0.698, 0.775] | 0.609 [0.598, 0.618] |
| cnn | 39.79 [36.57, 43.33] | 0.327 [0.277, 0.372] | 1.000 [1.000, 1.000] | 0.596 [0.567, 0.620] |
| attention_net | 45.81 [44.73, 47.02] | 0.240 [0.226, 0.252] | 1.000 [1.000, 1.000] | 0.516 [0.429, 0.602] |

## Per-Run Metrics

| method | run | dt_mae_ns | recovery_efficiency_20ns | false_pileup_rate | pileup_auc |
| --- | --- | --- | --- | --- | --- |
| attention_net | 42 | 46.5628 | 0.2208 | 1.0000 | 0.5436 |
| attention_net | 50 | 45.5279 | 0.2417 | 1.0000 | 0.3703 |
| attention_net | 57 | 45.8994 | 0.2417 | 1.0000 | 0.4932 |
| attention_net | 58 | 44.0922 | 0.2556 | 1.0000 | 0.3906 |
| attention_net | 60 | 42.9099 | 0.2681 | 1.0000 | 0.6512 |
| attention_net | 62 | 46.9567 | 0.2306 | 1.0000 | 0.6282 |
| attention_net | 64 | 45.6596 | 0.2556 | 1.0000 | 0.7018 |
| attention_net | 65 | 48.9013 | 0.2056 | 1.0000 | 0.3527 |
| cnn | 42 | 44.4418 | 0.2500 | 1.0000 | 0.5853 |
| cnn | 50 | 50.2066 | 0.2000 | 1.0000 | 0.5902 |
| cnn | 57 | 33.6281 | 0.4125 | 1.0000 | 0.5793 |
| cnn | 58 | 41.5329 | 0.2972 | 1.0000 | 0.5798 |
| cnn | 60 | 36.8295 | 0.3611 | 1.0000 | 0.5280 |
| cnn | 62 | 34.1953 | 0.4139 | 1.0000 | 0.6377 |
| cnn | 64 | 40.0338 | 0.3264 | 1.0000 | 0.6458 |
| cnn | 65 | 37.4140 | 0.3556 | 1.0000 | 0.6212 |
| gradient_boosted_trees | 42 | 23.7421 | 0.5444 | 0.2958 | 0.9131 |
| gradient_boosted_trees | 50 | 26.4842 | 0.5000 | 0.3958 | 0.8858 |
| gradient_boosted_trees | 57 | 23.5374 | 0.5625 | 0.2917 | 0.9057 |
| gradient_boosted_trees | 58 | 23.2238 | 0.5903 | 0.3000 | 0.9050 |
| gradient_boosted_trees | 60 | 18.3201 | 0.6861 | 0.3208 | 0.9514 |
| gradient_boosted_trees | 62 | 17.7008 | 0.6653 | 0.2792 | 0.9492 |
| gradient_boosted_trees | 64 | 19.2468 | 0.6528 | 0.2167 | 0.9518 |
| gradient_boosted_trees | 65 | 22.5249 | 0.6083 | 0.2458 | 0.9168 |
| mlp | 42 | 25.5920 | 0.5083 | 0.6042 | 0.8013 |
| mlp | 50 | 27.0033 | 0.4681 | 0.5667 | 0.7963 |
| mlp | 57 | 24.9075 | 0.5681 | 0.5375 | 0.8155 |
| mlp | 58 | 23.9004 | 0.5458 | 0.8292 | 0.7213 |
| mlp | 60 | 19.8207 | 0.6486 | 0.4333 | 0.8747 |
| mlp | 62 | 18.3649 | 0.6583 | 0.6458 | 0.8736 |
| mlp | 64 | 20.5870 | 0.6458 | 0.3917 | 0.8764 |
| mlp | 65 | 23.6682 | 0.5708 | 0.4792 | 0.8509 |
| ridge | 42 | 25.1822 | 0.4583 | 0.9292 | 0.7711 |
| ridge | 50 | 25.3546 | 0.4306 | 0.8917 | 0.7203 |
| ridge | 57 | 24.5021 | 0.4875 | 0.8750 | 0.7476 |
| ridge | 58 | 23.8455 | 0.5125 | 0.9208 | 0.7760 |
| ridge | 60 | 22.6295 | 0.5458 | 0.9042 | 0.7931 |
| ridge | 62 | 22.5704 | 0.5458 | 0.8542 | 0.8175 |
| ridge | 64 | 23.3311 | 0.5417 | 0.8750 | 0.8390 |
| ridge | 65 | 24.4650 | 0.4792 | 0.9125 | 0.7966 |
| traditional_template_fit | 42 | 26.3644 | 0.5778 | 0.7417 | 0.6182 |
| traditional_template_fit | 50 | 27.0539 | 0.5514 | 0.6917 | 0.6190 |
| traditional_template_fit | 57 | 25.9949 | 0.5806 | 0.6667 | 0.6061 |
| traditional_template_fit | 58 | 25.5593 | 0.5903 | 0.8292 | 0.6215 |
| traditional_template_fit | 60 | 24.4884 | 0.6500 | 0.7208 | 0.5765 |
| traditional_template_fit | 62 | 26.4054 | 0.5986 | 0.6958 | 0.6043 |
| traditional_template_fit | 64 | 27.0417 | 0.5958 | 0.7167 | 0.6260 |
| traditional_template_fit | 65 | 27.1892 | 0.5722 | 0.8083 | 0.5993 |

## Systematics

- **Overlay realism:** two-pulse labels are exact, but the second pulse is synthetically shifted and added. This preserves real single-pulse morphology but cannot reproduce every acquisition-chain nonlinearity.
- **Template accuracy:** the traditional baseline depends on a fold-local median template. Template mismatch is part of its measured error, and GEANT4 template inaccuracies would propagate similarly.
- **Baseline wander:** the raw reproduction removes a per-event median pedestal from early samples. Long pretrigger excursions can still alter pulse tails and produce false positives.
- **Run splitting:** leave-run-out training prevents row leakage across the reported folds, but the held-out set is a selected subset of high-statistics B-stack runs.
- **Charge scale:** overlay charge labels are amplitude-proxy sums. They validate recovery trends and charge closure, not absolute calorimetric energy.

## Caveats and Interpretation

The study validates separation recovery and pile-up flagging on controlled real-waveform overlays. It does not claim direct real-data pile-up truth, because the HRD ROOT schema exposes acquisition counters and waveforms but not external event-level multi-particle labels. The winning model should therefore be read as the best recovery method on a calibrated overlay truth task; application to real high-rate data still requires conservative false-positive accounting and support checks against current, amplitude, and baseline strata.
