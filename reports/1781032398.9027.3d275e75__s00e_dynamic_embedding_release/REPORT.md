# S00e: P01b-compatible dynamic-only embedding release

- **Ticket:** 1781032398.9027.3d275e75
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Config:** `configs/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.json`
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Git commit at run time:** `62cd446f7454b0f87cd701a91b00c3b323c9585e`

## 0. Question

Can the P01b reusable waveform embedding release be extended from S00-selected B-stave pulses to the strict dynamic-range superset, and do the dynamic-only selector-excess pulses occupy separable latent/morphology support when selector-defining amplitudes are withheld from the benchmark features?

The pre-registered primary benchmark metric is held-out ROC AUC for `dynamic_only` versus S00-control rows on runs `[42, 57, 64, 65]`. The strong traditional baseline is a ridge classifier on hand-engineered, amplitude-normalized pulse-shape variables. ML comparators are gradient-boosted trees, an MLP, a 1D CNN, and a new self-supervised AE-latent plus shape-fusion HGB architecture.

## 1. Reproduction Gate

Raw ROOT files were scanned before any model fitting. For each stave pulse record, the S00 selector is

\[
I_{S00} = \mathbb{1}\{\max_t(v_t - \mathrm{median}(v_0,v_1,v_2,v_3)) > 1000\},
\]

and the dynamic selector is

\[
I_{dyn} = \mathbb{1}\{\max_t v_t - \min_t v_t > 1000\}.
\]

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass |
|---|---:|---:|---:|---:|---|
| median_first_four_selected | 640737 | 640737 | 0 | 0 | True |
| dynamic_range_selected | 706373 | 706373 | 0 | 0 | True |
| dynamic_only | 65636 | 65636 | 0 | 0 | True |
| median_only | 0 | 0 | 0 | 0 | True |

The dynamic-selected release population therefore has **706,373** rows, made of **640,737** S00 rows plus **65,636** dynamic-only rows. Per-run counts are in `selector_counts_by_run.csv` and plotted in `selector_counts_by_run.png`.

## 2. Traditional Method

The traditional benchmark uses amplitude-normalized waveform morphology:

\[
x_i = (s, t_{peak}, A_{area}/A_{med}, A_{+}/A_{med}, f_{early}, f_{late}, w_{20}, w_{50}, q_{template}, n_{sat}),
\]

where `q_template` is the RMSE to a stave-specific median S00-control template fit only on non-held-out runs. The ridge classifier solves

\[
\min_\beta \sum_i (y_i - x_i^\top\beta)^2 + \alpha\lVert\beta\rVert_2^2
\]

with class weighting and run-held-out validation over `alpha`. It does not receive median amplitude, dynamic amplitude, dynamic-minus-median, baseline excursion, run id, event id, or the selector flags.

Traditional ridge achieved ROC AUC **0.9830** (0.9776-0.9868) and average precision **0.8109** (0.8018-0.8466) on the same held-out rows as every ML method.

## 3. ML and NN Methods

The run-held-out evaluation autoencoder was trained only on non-held-out dynamic-selected rows with a masked denoising loss,

\[
\mathcal{L} = \langle (\hat{x}_m-x_m)^2\rangle_m + 0.2\langle(\hat{x}-x)^2\rangle,
\]

then encoded all benchmark rows into a four-dimensional P01b-compatible latent. The release autoencoder was trained later on all dynamic-selected rows and is not used for the held-out benchmark.

All benchmark models use the same held-out runs and bootstrap run blocks for confidence intervals:

| Method | ROC AUC | 95% CI | Average precision | 95% CI | Balanced accuracy | ECE |
|---|---:|---:|---:|---:|---:|---:|
| new_ae_latent_shape_fusion_hgb | 0.9984 | 0.9965-0.9990 | 0.9921 | 0.9790-0.9958 | 0.9836 | 0.0164 |
| gradient_boosted_trees_hgb | 0.9981 | 0.9961-0.9987 | 0.9902 | 0.9769-0.9945 | 0.9810 | 0.0183 |
| mlp_waveform | 0.9953 | 0.9925-0.9966 | 0.9761 | 0.9589-0.9841 | 0.9723 | 0.0316 |
| cnn_1d_waveform | 0.9943 | 0.9914-0.9954 | 0.9686 | 0.9424-0.9785 | 0.9679 | 0.0365 |
| ridge_hand_shape | 0.9830 | 0.9776-0.9868 | 0.8109 | 0.8018-0.8466 | 0.9658 | 0.2626 |

The selected hyperparameters are `{'ridge_alpha': 100.0, 'hgb_max_leaf_nodes': 31, 'fusion_max_leaf_nodes': 31, 'mlp_hidden': 64, 'cnn_channels': 8, 'train_rows': 141932, 'test_rows': 68079, 'test_positive_rows': 8466}`. The validation scan is written to `hyperparameter_cv.csv`; no held-out run is used to tune these choices.

## 4. Head-to-head Verdict

The winner is **new_ae_latent_shape_fusion_hgb** with ROC AUC **0.9984** (0.9965-0.9990). Relative to ridge, the ROC-AUC lift is **0.0154**. This means dynamic-only rows are separable in waveform morphology/latent support even after removing selector-defining amplitudes. The result should be used as release telemetry, not as evidence that dynamic-only rows are clean physics pulses.

## 5. Falsification

The claim would be falsified if the best ML/NN method failed to improve held-out ROC AUC over ridge by more than zero under the run-block bootstrap, or if the release-row counts failed the exact raw-ROOT reproduction gate. The count gate passed exactly. The benchmark improvement is reported as a descriptive CI-backed release diagnostic rather than a discovery p-value because five model families were compared; the multiplicity-aware caveat is that architecture ranking is exploratory while the existence of non-amplitude separability is robust across several families.

## 6. Threats to Validity

- **Benchmark/selection:** the baseline is not a threshold strawman; it uses conventional engineered pulse-shape variables and ridge regularization. The test rows are identical across all models.
- **Data leakage:** train/test split is by run. Selector-defining amplitudes and direct dynamic-minus-median variables are excluded from all benchmark feature sets. The release AE is trained after benchmark scoring and is not used for the benchmark.
- **Metric misuse:** ROC AUC is primary because dynamic-only is imbalanced. Average precision, balanced accuracy, Brier score, and calibration error are also reported. This is a separability benchmark, not a calibrated physical probability claim.
- **Post-hoc selection:** the held-out runs, validation runs, model families, and primary metric are fixed in the committed config before running the analysis.

## 7. Release Artifact

The release artifact `s00e_dynamic_embedding_latents.npz` contains `run`, `event_index`, `stave_index`, `amplitude_adc`, `s00_selected`, `dynamic_only`, and `z` with shape **706373 x 4**. Its sha256 is `de03b77e3b55e33016d2ab81ba17f3dbd30c89d433388a81905b6f533c07cb6a` and its compressed size is **12.71 MiB**. `amplitude_adc` keeps the P01b convention: baseline-subtracted median-first-four peak amplitude, which may be below 1000 ADC for dynamic-only rows.

## 8. Systematics, Caveats, and Interpretation

The dominant systematic is selector-induced support shift: dynamic-only rows are not an exchangeable random subset of S00 controls. The benchmark intentionally asks whether the support differs, so high separability is expected to some degree. A second systematic is normalization for dynamic-only low-amplitude rows; using the P01b amplitude convention preserves compatibility but can amplify baseline-excursion morphology. Finally, the release model is a compact representation for downstream studies, not a truth label, and downstream users should retain `dynamic_only` as provenance.

Hypothesis: the dynamic-only excess is mostly a high-baseline or malformed-pulse support atom that deserves explicit provenance in every downstream representation rather than silent inclusion into S00-like controls.

Queued follow-up: **S00g: external stability of dynamic-selected release latents against calibration-run drift**. Expected information gain: it tests whether the release latent coordinates are stable under alternative training populations, which is the main remaining risk for using the artifact as reusable infrastructure.

## 9. Reproducibility

Regenerate all numbers with:

```bash
/home/billy/anaconda3/bin/python scripts/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.py --config configs/s00e_1781032398_9027_3d275e75_dynamic_embedding_release.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `selector_counts_by_run.csv`, `reproduction_match_table.csv`, `heldout_model_benchmark.csv`, `hyperparameter_cv.csv`, `s00e_dynamic_embedding_latents.npz`, `s00e_autoencoder_state.pt`, and the diagnostic PNG plots.
