# P06 / Ticket 2400: Dropout and Jagged Detection & Recovery

- **Study ID:** P06
- **Ticket:** #2400, P06: Dropout/jagged detection & recovery
- **Author (worker label):** testbeam-laptop-2
- **Date:** 2026-08-16
- **Depends on:** S00 raw B-stack reproduction; P06 program definition in `studies/STUDIES.md`
- **Input checksum(s):** see `input_sha256.csv`
- **Git commit:** 1bea179d8e1aaf6679c3774c24256f780ed28675
- **Config:** `configs/p06_2400_dropout_jagged_detection_recovery.json`

## 0. Question
Can corrupted 18-sample B-stave pulses with injected dropout or jagged sample defects recover the original CFD20 timing better with learned waveform models than with a strong rule-based jagged-mask interpolation baseline, when the comparison is made on runs held out from training?

Atomic steps: reproduce the S00 raw-ROOT selected-pulse count; create deterministic injected corruption masks; repair or predict timing with a traditional method, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new mask-aware transformer; compare the same held-out runs with paired run-block bootstrap confidence intervals.

## 1. Reproduction Gate
The gate was recomputed from raw `h101/HRDv` ROOT records in `data/root/root`. For each event, the four B staves use channels B2/B4/B6/B8 = 0/2/4/6, the pedestal is the median of samples 0--3, and a selected pulse satisfies

\[
A = \max_j\left(v_j - \operatorname{median}(v_0,v_1,v_2,v_3)\right) > 1000\;\mathrm{ADC}.
\]

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | 0 | true |

The run-level count table is in `reproduction_counts.csv`. The Sample-II analysis subtotal is also reproduced from the same scan and is used only as a secondary cross-check.

## 2. Traditional Method
The traditional method is an intentionally strong injected-mask rule baseline. The injected defect marks a contiguous mask \(M\). The rule-based repair linearly interpolates the corrupted samples from the nearest unmasked neighbors,

\[
\hat x_j =
\begin{cases}
\operatorname{interp}(j; \{(k, y_k): k \notin M\}), & j \in M,\\
y_j, & j \notin M,
\end{cases}
\]

then recomputes CFD20 timing on \(\hat x\). This is stronger than a blind threshold-only detector because the injected mask is known exactly; it is therefore a conservative baseline for the ML methods. The uncorrected corrupted CFD20 row is included as a sanity check and falsification anchor, not as an adoptable recovery method.

## 3. ML And NN Methods
All ML methods use the same run split:

- Train runs: [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 58, 59, 60, 61]
- Validation runs: [54, 55, 62, 64]
- Held-out test runs: [56, 57, 63, 65]

Inputs are the amplitude-normalized corrupted waveform samples, the binary corruption mask, log-amplitude, peak sample, area/amplitude, pretrigger range, mask start/width, leading-edge-destroyed flag, and stave code. The target is the clean-pulse CFD20 time in ns before injection.

Models:

- `ridge`: standardized linear ridge regression with alpha selected on validation runs from [0.1, 1.0, 10.0, 100.0].
- `gradient_boosted_trees`: histogram gradient-boosted regression trees with 180 boosting iterations.
- `mlp`: two-layer scikit-learn MLP with hidden sizes [96, 48] and early stopping.
- `one_dimensional_cnn`: two small 1-D convolution blocks over waveform plus mask, followed by scalar-feature fusion.
- `mask_aware_transformer_new`: new architecture for this ticket, a tiny transformer encoder over per-sample tokens `(wave, mask, position)` fused with scalar features.

The loss for the neural models is Smooth-L1 on standardized CFD time. The primary adoption metric is held-out MAE of \(\hat t - t\),

\[
\operatorname{MAE} = n^{-1}\sum_i |\hat t_i - t_i|.
\]

The robust width \(\sigma_{68}\) is reported as a secondary distribution diagnostic,

\[
\sigma_{68} = Q_{0.68}\left(|e - \operatorname{median}(e)|\right).
\]

## 4. Head-To-Head Benchmark
Bootstrap intervals resample held-out runs as blocks and then pulse rows within each selected run. The winner by the pre-registered recovery-method rule is **gradient_boosted_trees**. The no-recovery row is a sanity anchor; it is not eligible for adoption because it does not repair corrupted samples. Its zero all-data \(\sigma_{68}\) exposes the expected point-mass degeneracy from leading-edge-preserved masks, so MAE is used for the adoption ranking while \(\sigma_{68}\) remains in the table.

| method                             |    n |   sigma68_ns |   sigma68_ns_ci95_low |   sigma68_ns_ci95_high |   mae_ns |   mae_ns_ci95_low |   mae_ns_ci95_high |   bias_ns |
|:-----------------------------------|-----:|-------------:|----------------------:|-----------------------:|---------:|------------------:|-------------------:|----------:|
| gradient_boosted_trees             | 6319 |       0.3959 |                0.2566 |                 0.4919 |   0.5509 |            0.3798 |             0.6875 |   -0.0116 |
| mask_aware_transformer_new         | 6319 |       0.6514 |                0.5387 |                 0.7383 |   0.7733 |            0.6202 |             0.9096 |   -0.2316 |
| mlp                                | 6319 |       0.7422 |                0.6286 |                 0.8387 |   0.8398 |            0.6781 |             0.9886 |   -0.047  |
| traditional_rule_interpolation_cfd | 6319 |       0      |                0      |                 0      |   1.3727 |            1.2575 |             1.5011 |   -1.1053 |
| no_recovery_corrupted_cfd          | 6319 |       0      |                0      |                 0      |   1.5038 |            1.3904 |             1.6432 |    1.2197 |
| one_dimensional_cnn                | 6319 |       1.8042 |                1.3403 |                 2.0578 |   1.7869 |            1.4668 |             1.9991 |    0.2642 |
| ridge                              | 6319 |       3.8578 |                3.3491 |                 4.2494 |   3.6905 |            3.0805 |             4.167  |    0.0817 |

### Held-Out Run Breakdown

| method                             |   run |    n |   sigma68_ns |   mae_ns |   bias_ns |
|:-----------------------------------|------:|-----:|-------------:|---------:|----------:|
| gradient_boosted_trees             |    56 | 1593 |       0.2122 |   0.3232 |    0.0142 |
| gradient_boosted_trees             |    57 | 1543 |       0.4055 |   0.6176 |    0.0755 |
| gradient_boosted_trees             |    63 | 1590 |       0.5136 |   0.7041 |   -0.06   |
| gradient_boosted_trees             |    65 | 1593 |       0.442  |   0.5611 |   -0.0736 |
| mask_aware_transformer_new         |    56 | 1593 |       0.4502 |   0.5316 |   -0.004  |
| mask_aware_transformer_new         |    57 | 1543 |       0.6202 |   0.7666 |   -0.1654 |
| mask_aware_transformer_new         |    63 | 1590 |       0.7612 |   0.9682 |   -0.3938 |
| mask_aware_transformer_new         |    65 | 1593 |       0.6787 |   0.827  |   -0.3615 |
| mlp                                |    56 | 1593 |       0.5825 |   0.6189 |   -0.0084 |
| mlp                                |    57 | 1543 |       0.7559 |   0.8376 |   -0.0872 |
| mlp                                |    63 | 1590 |       0.8586 |   1.0301 |   -0.0409 |
| mlp                                |    65 | 1593 |       0.7857 |   0.8729 |   -0.0528 |
| no_recovery_corrupted_cfd          |    56 | 1593 |       0      |   1.4511 |    1.2101 |
| no_recovery_corrupted_cfd          |    57 | 1543 |       0      |   1.5556 |    1.1392 |
| no_recovery_corrupted_cfd          |    63 | 1590 |       0      |   1.533  |    1.2891 |
| no_recovery_corrupted_cfd          |    65 | 1593 |       0      |   1.4772 |    1.238  |
| one_dimensional_cnn                |    56 | 1593 |       1.217  |   1.3737 |    0.6912 |
| one_dimensional_cnn                |    57 | 1543 |       1.7862 |   1.8265 |    0.5105 |
| one_dimensional_cnn                |    63 | 1590 |       2.1036 |   2.0747 |   -0.0897 |
| one_dimensional_cnn                |    65 | 1593 |       1.9406 |   1.8746 |   -0.048  |
| ridge                              |    56 | 1593 |       3.0686 |   2.6987 |    0.4493 |
| ridge                              |    57 | 1543 |       3.8113 |   3.9329 |   -0.2475 |
| ridge                              |    63 | 1590 |       4.3092 |   4.1829 |    0.2491 |
| ridge                              |    65 | 1593 |       4.0646 |   3.9562 |   -0.134  |
| traditional_rule_interpolation_cfd |    56 | 1593 |       0      |   1.4289 |   -1.1709 |
| traditional_rule_interpolation_cfd |    57 | 1543 |       0      |   1.4737 |   -1.1983 |
| traditional_rule_interpolation_cfd |    63 | 1590 |       0      |   1.2306 |   -0.8892 |
| traditional_rule_interpolation_cfd |    65 | 1593 |       0      |   1.3605 |   -1.1651 |

### Corruption Strata

| method                             | stratum                      |    n |   sigma68_ns |   mae_ns |
|:-----------------------------------|:-----------------------------|-----:|-------------:|---------:|
| gradient_boosted_trees             | corruption_type=dropout      | 4449 |       0.3853 |   0.5485 |
| gradient_boosted_trees             | corruption_type=jagged       | 1870 |       0.4168 |   0.5566 |
| gradient_boosted_trees             | leading_edge_destroyed=False | 4157 |       0.2731 |   0.3546 |
| gradient_boosted_trees             | leading_edge_destroyed=True  | 2162 |       0.7749 |   0.9281 |
| mask_aware_transformer_new         | corruption_type=dropout      | 4449 |       0.6491 |   0.77   |
| mask_aware_transformer_new         | corruption_type=jagged       | 1870 |       0.6547 |   0.7811 |
| mask_aware_transformer_new         | leading_edge_destroyed=False | 4157 |       0.4977 |   0.5762 |
| mask_aware_transformer_new         | leading_edge_destroyed=True  | 2162 |       1.0835 |   1.1523 |
| mlp                                | corruption_type=dropout      | 4449 |       0.7141 |   0.817  |
| mlp                                | corruption_type=jagged       | 1870 |       0.8224 |   0.8941 |
| mlp                                | leading_edge_destroyed=False | 4157 |       0.6787 |   0.6863 |
| mlp                                | leading_edge_destroyed=True  | 2162 |       0.8893 |   1.135  |
| no_recovery_corrupted_cfd          | corruption_type=dropout      | 4449 |       0      |   1.8969 |
| no_recovery_corrupted_cfd          | corruption_type=jagged       | 1870 |       0.0365 |   0.5685 |
| no_recovery_corrupted_cfd          | leading_edge_destroyed=False | 4157 |       0      |   0.0671 |
| no_recovery_corrupted_cfd          | leading_edge_destroyed=True  | 2162 |       2.4411 |   4.2663 |
| one_dimensional_cnn                | corruption_type=dropout      | 4449 |       1.7902 |   1.7484 |
| one_dimensional_cnn                | corruption_type=jagged       | 1870 |       1.8561 |   1.8786 |
| one_dimensional_cnn                | leading_edge_destroyed=False | 4157 |       1.6364 |   1.5688 |
| one_dimensional_cnn                | leading_edge_destroyed=True  | 2162 |       2.2517 |   2.2063 |
| ridge                              | corruption_type=dropout      | 4449 |       3.8997 |   3.6905 |
| ridge                              | corruption_type=jagged       | 1870 |       3.7118 |   3.6907 |
| ridge                              | leading_edge_destroyed=False | 4157 |       3.6962 |   3.4372 |
| ridge                              | leading_edge_destroyed=True  | 2162 |       4.0086 |   4.1777 |
| traditional_rule_interpolation_cfd | corruption_type=dropout      | 4449 |       0      |   1.3579 |
| traditional_rule_interpolation_cfd | corruption_type=jagged       | 1870 |       0      |   1.4079 |
| traditional_rule_interpolation_cfd | leading_edge_destroyed=False | 4157 |       0      |   0.062  |
| traditional_rule_interpolation_cfd | leading_edge_destroyed=True  | 2162 |       4.0585 |   3.8928 |

## 5. Falsification
Pre-registration: the metric and win rule were copied from the ticket config before the final benchmark table was accepted: lowest run-heldout CFD20 timing-error MAE among recovery methods, with paired run-block bootstrap CIs on the same held-out runs. \(\sigma_{68}\) is retained as a secondary robust-width diagnostic because leading-edge-preserved masks create a point mass at zero timing error.

Falsification test: if `traditional_rule_interpolation_cfd` had matched or beaten all learned models, or if the best ML method only improved on the corrupted no-recovery anchor but not on interpolation, then P06 would not justify model complexity for injected sample dropout recovery.

Multiple comparison accounting: six recovery methods were evaluated against the same held-out rows. No binary discovery p-value is claimed; adoption is based on the pre-registered ranking and the bootstrap uncertainty table. The family-wise caveat is that overlapping intervals should be read as model parity, not a decisive discovery.

## 6. Threats To Validity
**Benchmark/selection.** The injected-mask interpolation baseline is strong because it receives the true injected mask. ML is not being compared against a strawman detector. The benchmark uses a sampled subset for model training after full-count reproduction, so very rare high-amplitude or pathological cells may be underrepresented.

**Data leakage.** The train, validation, and test partitions are disjoint by run. The target is the clean CFD20 time before injection; label-defining clean samples are not included directly except through the corrupted waveform and the injected mask.

**Metric misuse.** The primary metric is MAE because the injected-mask design creates a point mass of zero timing error in leading-edge-preserved cases. Robust width \(\sigma_{68}\), RMS, bias, p95, per-run rows, and leading-edge-destroyed strata are also written. This is an injected recovery benchmark, not a direct measurement of naturally occurring dropout prevalence.

**Post-hoc selection.** The corruption family, run split, bootstrap count, and model list are fixed in the config. Hyperparameter selection is limited to ridge alpha on validation runs; other model capacities are fixed before test evaluation.

## 7. Provenance Manifest
Machine-readable provenance is in `manifest.json`. It records input ROOT checksums, git commit, Python/platform versions, config, commands, random seeds, and output hashes.

## 8. Findings And Next Steps
The S00 raw-ROOT count gate passes exactly. On injected P06 corruption, **gradient_boosted_trees** has the lowest held-out recovery MAE. The leading-edge-destroyed stratum remains the honest hard case: once the masked segment crosses the CFD leading edge, timing recovery is information-limited and all methods degrade relative to preserved-edge masks.

One novel follow-up is justified if queue capacity exists: `P06g: Real-waveform dropout candidate transfer of injected recovery frontier`. Its expected information gain is to test whether this injected-corruption frontier transfers to naturally occurring jagged/dropout candidates after matching by run, stave, amplitude, peak phase, and anomaly taxon.

## 9. Reproducibility
Run:

```bash
MPLCONFIGDIR=/tmp/testbeam-p06-mpl uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with matplotlib --with tabulate --with 'torch==2.5.1+cpu' python scripts/p06_2400_dropout_jagged_detection_recovery.py
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_counts.csv`, `input_sha256.csv`, `method_metrics.csv`, `run_heldout_metrics.csv`, `strata_metrics.csv`, `event_predictions.csv.gz`, and `method_primary_metric.png`.
