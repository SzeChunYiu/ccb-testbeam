# S00g: external stability of dynamic-selected release latents against calibration-run drift

- **Ticket:** `1781102042.1423.024e7ae7`
- **Worker:** `testbeam-laptop-1`
- **Input raw ROOT:** `/home/billy/.tb-workers/testbeam-laptop-1/data/root/root`
- **Upstream latent artifact:** `reports/1781032398.9027.3d275e75__s00e_dynamic_embedding_release/s00e_dynamic_embedding_latents.npz`
- **Git commit at run time:** `e200430bc072f5ab7addd463c33b184a6ab36d02`

## 1. Question and Scope

The claimed ticket asks whether the S00e dynamic-selected release latents remain stable when the representation is stressed by Sample-I, Sample-II, and calibration-only controls. This report treats stability as an external-domain question: if the S00e latent coordinates are invariant to calibration-run drift, a classifier trained without run id or event id should have difficulty separating calibration-origin rows from analysis-origin rows on runs not used for training.

The target is

\[
y_i = \mathbf{1}(r_i \in R_{calib}),
\]

where `R_calib` is the union of Sample-I calibration runs and the Sample-II calibration run. The held-out run block is `[42, 57, 64, 65]`, containing calibration and analysis runs from both Sample I and Sample II. Hyperparameters are chosen only on validation runs `[41, 56, 63]`. All reported confidence intervals resample held-out runs as blocks.

## 2. Raw-ROOT Reproduction Gate

Before using the S00e artifact, the script rescans the B-stack ROOT files and reproduces the S00e selected-pulse counts. The selectors are

\[
I_{S00}=\mathbf{1}(\max_t(v_t-\mathrm{median}(v_0,v_1,v_2,v_3))>1000),
\]

and

\[
I_{dyn}=\mathbf{1}(\max_t v_t-\min_t v_t>1000).
\]

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| median_first_four_selected | 640737 | 640737 | 0 | 0 | True |
| dynamic_range_selected | 706373 | 706373 | 0 | 0 | True |
| dynamic_only | 65636 | 65636 | 0 | 0 | True |
| median_only | 0 | 0 | 0 | 0 | True |

The exact count gate passes: `result.json` records `reproduced=true`.

## 3. Methods

Each row is a dynamic-selected stave pulse from `s00e_dynamic_embedding_latents.npz`. Features are the four released latent coordinates, log amplitude, stave index, dynamic-only provenance, S00 provenance, latent norm, and simple coordinate interactions. No run id, event id, or group label is supplied to any model.

### 3.1 Traditional Method

The strong traditional benchmark is a diagonal Gaussian log-likelihood-ratio domain score,

\[
s(x)=\log p(x\mid y=1)-\log p(x\mid y=0),
\]

with class-conditional means and variances fitted on non-held-out, non-validation runs. This is a conventional moment-transport stability diagnostic: high AUC means calibration-origin rows occupy a measurably different latent/amplitude support than analysis-origin rows.

### 3.2 ML and NN Methods

The ML panel contains ridge classification, histogram gradient-boosted trees, a one-hidden-layer MLP, and a 1D CNN over the ordered latent/metadata feature vector. The ticket-local new architecture is `new_stave_residualized_fusion_hgb`: per-stave latent residuals are formed from the training rows only, appended to the base features, and passed to a gradient-boosted-tree head. This tests whether drift is mostly a stave-centroid/scale shift or a higher-order residual deformation.

Hyperparameter validation results:

| method | parameter | value | validation_auc |
| --- | --- | --- | --- |
| ridge | alpha | 0.1000 | 0.5479 |
| ridge | alpha | 1.0000 | 0.5479 |
| ridge | alpha | 10.0000 | 0.5480 |
| ridge | alpha | 100.0000 | 0.5471 |
| gradient_boosted_trees_hgb | max_leaf_nodes | 15.0000 | 0.6202 |
| gradient_boosted_trees_hgb | max_leaf_nodes | 31.0000 | 0.6228 |
| gradient_boosted_trees_hgb | max_leaf_nodes | 63.0000 | 0.6249 |
| mlp | hidden | 32.0000 | 0.6125 |
| mlp | hidden | 64.0000 | 0.6238 |
| cnn_1d | channels | 4.0000 | 0.5435 |
| cnn_1d | channels | 8.0000 | 0.6520 |
| new_stave_residualized_fusion_hgb | max_leaf_nodes | 15.0000 | 0.6219 |
| new_stave_residualized_fusion_hgb | max_leaf_nodes | 31.0000 | 0.6247 |
| new_stave_residualized_fusion_hgb | max_leaf_nodes | 63.0000 | 0.6251 |

## 4. Run-Held-Out Results

Primary metric: held-out calibration-origin ROC AUC. Because the metric is a drift detector, higher AUC means stronger evidence that the released latent support is not externally invariant to calibration-run origin.

| method | roc_auc | 95% CI | average_precision | balanced_accuracy | brier | ece_10bin |
| --- | --- | --- | --- | --- | --- | --- |
| ridge | 0.5132 | 0.3101-0.7195 | 0.5058 | 0.5217 | 0.2526 | 0.0173 |
| gradient_boosted_trees_hgb | 0.4951 | 0.2780-0.7247 | 0.4955 | 0.5001 | 0.2860 | 0.1550 |
| new_stave_residualized_fusion_hgb | 0.4947 | 0.2768-0.7255 | 0.4938 | 0.4998 | 0.2857 | 0.1553 |
| mlp | 0.4880 | 0.2915-0.6981 | 0.4889 | 0.4982 | 0.2852 | 0.1574 |
| traditional_diag_gaussian_moment | 0.4871 | 0.3964-0.5850 | 0.4899 | 0.4991 | 0.4806 | 0.4765 |
| cnn_1d | 0.4323 | 0.3964-0.4698 | 0.4584 | 0.4552 | 0.2576 | 0.0778 |

The winner is **ridge**, with ROC AUC **0.5132** (0.3101-0.7195). The AUC excess over random guessing is **0.0132**.

## 5. Interpretation

The result is not a physics-label performance claim. It is a stability stress test of the released S00e latent coordinates. A successful high-AUC detector implies that calibration and analysis populations remain distinguishable in the released coordinate system after run-level splitting; downstream users should therefore retain run-family and calibration provenance when consuming the S00e artifact.

The traditional Gaussian moment score is competitive only if drift is captured by a low-order shift in mean and variance. The ticket-local residualized fusion model tests a stronger alternative: calibration drift can remain after subtracting stave-local moments, indicating higher-order support changes involving latent interactions, amplitude, and selector provenance. In this run-held-out stress test, ridge has the highest point AUC, while all CIs are wide and overlap random-guessing performance.

## 6. Systematics and Caveats

- **Selector coupling:** dynamic-only provenance is retained as an input because S00e explicitly released it as provenance. Removing it is a useful sensitivity but not the primary contract; downstream consumers see this column.
- **Artifact reuse:** the benchmark uses the S00e release artifact instead of retraining full autoencoders for every source subset. The raw ROOT scan independently verifies the row universe, while this ticket asks whether the released coordinates are stable under source-origin stress.
- **Domain target:** calibration-origin classification is a diagnostic nuisance target. High performance is bad for invariance but useful for discovering that a provenance correction is needed.
- **Bootstrap:** confidence intervals resample the four held-out runs as blocks. They therefore capture run-to-run variability, not uncertainty from unobserved run families or alternative ROOT mirrors.
- **Multiplicity:** five model families are compared. The named winner should be read as the strongest stress-test detector in this panel, not as a universal architecture ranking.

## 7. Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s00g_1781102042_1423_024e7ae7_external_latent_stability.py --config configs/s00g_1781102042_1423_024e7ae7_external_latent_stability.json
```

Primary artifacts are `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `selector_counts_by_run.csv`, `heldout_model_benchmark.csv`, `hyperparameter_cv.csv`, and `input_sha256.csv`.
