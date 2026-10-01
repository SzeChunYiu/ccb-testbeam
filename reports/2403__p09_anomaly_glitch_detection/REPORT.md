# P09 anomaly/glitch detection benchmark

- **Ticket:** #2403
- **Worker:** testbeam-laptop-4
- **Study ID:** P09
- **Date:** 2026-08-16
- **Config:** `configs/2403_p09_anomaly_glitch_detection.json`
- **Git commit:** `d3b2beb217c7157693da45e3e8824489c7a8f036`

## 0. Question

This ticket asks whether rare pathological B-stave pulses can be surfaced for review more efficiently than with transparent shape cuts. The atomic decision is a held-out-run flagged-set precision benchmark: among the top-ranked pulses per run and stave, what fraction is assigned to a frozen curated anomaly rubric?

## 1. Reproduction Gate

The analysis first rereads raw ROOT from `/home/billy/ccb-data/data/extracted/root/root` before fitting any anomaly model. The branch `HRDv` is reshaped into event x channel x 18 samples. B2/B4/B6/B8 even channels are baseline-subtracted with median samples `[0, 1, 2, 3]`, and a pulse is selected when its baseline-subtracted peak exceeds `1000.0` ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |

The per-run reproduction ledger is `reproduction_counts_by_run.csv`; ROOT checksums are in `input_sha256.csv`.

## 2. Methods

Let \(x_i\) be the 18-sample normalized pulse and \(u_i\) the deterministic morphology vector. The frozen review target \(y_i\) is not detector truth; it is a curated morphology rubric made from train-run quantiles for saturation, dropout, baseline excursion, secondary peaks, early peaks, delayed peaks, undershoot recovery, broad width, template mismatch, and duplicate-channel timing tails. Thresholds are fit on training runs only and then applied to validation and held-out runs.

The traditional baseline is a robust shape-cut ranker,

\[
s_\mathrm{trad}(i)=\max_j |u_{ij}-\tilde u_j|/(1.4826\,\mathrm{MAD}_j)+0.15\,\mathrm{mean}_j |z_{ij}|,
\]

where medians and MADs are train-run only. The unsupervised ML comparator combines PCA reconstruction error, autoencoder reconstruction error, and IsolationForest density. The supervised methods are L2 ridge logistic regression, histogram gradient-boosted trees, an MLP, a waveform-only 1D-CNN, and a new morphology-gated CNN that concatenates convolutional waveform features with standardized morphology features. All supervised models train on non-held-out runs, tune on validation runs `[40, 55, 63]`, and report only held-out runs `[42, 57, 64, 65]`.

For probabilistic models the score is \(p_\theta(y_i=1\mid x_i,u_i)\). The ranking metric is top-k flagged precision,

\[
\mathrm{precision}_k = {1 \over |F_k|}\sum_{i\in F_k} y_i,
\]

where \(F_k\) contains the top `12` pulses in each held-out run/stave stratum. Uncertainty intervals are run-block bootstraps over held-out runs with `1000` replicates.

## 3. Model Selection

| method                   | param                   | val_auc | val_average_precision |
| ------------------------ | ----------------------- | ------- | --------------------- |
| ridge                    | C=0.1                   | 0.99499 | 0.94189               |
| ridge                    | C=1.0                   | 0.9953  | 0.9449                |
| ridge                    | C=10.0                  | 0.99534 | 0.94536               |
| gradient_boosted_trees   | learning_rate=0.04      | 0.99999 | 0.99993               |
| gradient_boosted_trees   | learning_rate=0.08      | 1.0     | 0.99999               |
| mlp                      | hidden=(64, 32)         | 0.99991 | 0.99875               |
| 1d_cnn                   | waveform_plus_aux=False | 0.95943 | 0.79911               |
| morphology_gated_cnn_new | waveform_plus_aux=True  | 0.96011 | 0.85116               |

## 4. Head-to-Head Results

| method                        | family           | n_flagged | curated_precision | curated_precision_ci95 | curated_enrichment | novel_precision | novel_precision_ci95 | heldout_average_precision | heldout_auc |
| ----------------------------- | ---------------- | --------- | ----------------- | ---------------------- | ------------------ | --------------- | -------------------- | ------------------------- | ----------- |
| gradient_boosted_trees        | ml               | 192       | 1.0               | [1, 1]                 | 11.76727           | 0.89583         | [0.8802, 0.9115]     | 0.99999                   | 1.0         |
| mlp                           | nn               | 192       | 1.0               | [1, 1]                 | 11.76727           | 0.88542         | [0.8333, 0.9271]     | 0.99944                   | 0.99995     |
| ridge                         | ml               | 192       | 0.98958           | [0.9792, 1]            | 11.6447            | 0.84896         | [0.8125, 0.8854]     | 0.96002                   | 0.99602     |
| morphology_gated_cnn_new      | new_architecture | 192       | 0.96875           | [0.9375, 1]            | 11.39954           | 0.86979         | [0.8281, 0.9167]     | 0.88813                   | 0.97415     |
| 1d_cnn                        | nn               | 192       | 0.89062           | [0.8646, 0.9219]       | 10.48023           | 0.81771         | [0.7812, 0.8542]     | 0.83732                   | 0.96715     |
| traditional_robust_shape_cuts | traditional      | 192       | 0.83333           | [0.7917, 0.901]        | 9.80606            | 0.57292         | [0.5052, 0.6615]     | 0.71241                   | 0.9567      |
| autoencoder_isolation_forest  | ml_unsupervised  | 192       | 0.8125            | [0.7708, 0.8542]       | 9.56091            | 0.78125         | [0.7344, 0.8229]     | 0.69979                   | 0.96575     |

The winner written to `result.json` is **`gradient_boosted_trees`** with held-out curated precision 1.0000 and run-bootstrap CI [1, 1]. Its held-out average precision is 1.0000. Since the target is a deterministic review rubric, not external truth, this is an anomaly-triage result rather than a claim of physical anomaly identity.

## 5. Taxonomy and Systematics

| taxon                         | heldout_count | flagged_count | heldout_rate | flagged_rate |
| ----------------------------- | ------------- | ------------- | ------------ | ------------ |
| baseline_excursion            | 776           | 103.0         | 0.01302      | 0.07664      |
| dropout                       | 88            | 36.0          | 0.00148      | 0.02679      |
| novel_broad_template_mismatch | 162           | 1.0           | 0.00272      | 0.00074      |
| novel_delayed_peak            | 1580          | 258.0         | 0.0265       | 0.19196      |
| novel_early_pretrigger        | 2363          | 829.0         | 0.03964      | 0.61682      |
| pileup_or_long_tail           | 95            | 20.0          | 0.00159      | 0.01488      |
| saturation                    | 2             | 0.0           | 3e-05        | 0.0          |
| unassigned_common             | 54547         | 97.0          | 0.91502      | 0.07217      |

Systematic caveats:

- The curated labels are morphology-review proxies. They deliberately exclude model scores but still encode expert design choices, so precision is an audit target, not ground truth.
- The train/validation/held-out split is by run. This protects against event-level leakage but does not emulate future hardware changes outside these runs.
- The traditional baseline is strong because it uses the same waveform summaries that define the reviewer rubric. Any ML win must therefore be interpreted as ranking the same rubric more efficiently, not discovering a separate class.
- Rare classes have small support. The bootstrap intervals capture run-block instability but not human-review disagreement.
- Duplicate channels are used only for morphology/timing-tail evidence, not as an independent truth label.

## 6. Leakage and Falsification Checks

| check                                | value               | pass | note                                             |
| ------------------------------------ | ------------------- | ---- | ------------------------------------------------ |
| train_validation_heldout_run_overlap | 0.0                 | True | must be zero                                     |
| raw_root_reproduction_exact          | 1.0                 | True | 640737 selected pulses                           |
| model_feature_id_columns             | 0.0                 | True | run/event/stave ids excluded from model matrices |
| winner_precision_minus_traditional   | 0.16666666666666663 | True | primary adoption guard                           |

Pre-registered success metric: held-out top-k curated precision, with average precision as the secondary ranking metric. A method would fail adoption if it did not beat the robust traditional ranker or if any train/held-out run overlap appeared.

## 7. Provenance and Reproduction

Manifest excerpt:

```json
{
  "ae_isolation_model": {
    "ae_final_loss": 0.06635612147742699,
    "device": "cpu",
    "pca_diagnostic_note": "sklearn randomized PCA emitted nonphysical explained-variance diagnostics on rare extreme pulses; PCA reconstruction scores were still finite and benchmarked, but variance-ratio diagnostics are suppressed.",
    "pca_explained_variance_ratio": null,
    "training_rows": 47402
  },
  "auxiliary_columns": [
    "q_template_rmse",
    "peak_sample",
    "late_fraction",
    "baseline_mad",
    "saturation_count",
    "secondary_peak",
    "post_peak_min",
    "timing_span_dup"
  ],
  "command": "MPLCONFIGDIR=/tmp/mpl-p09-2403 /home/billy/anaconda3/bin/python scripts/ticket_2403_p09_anomaly_glitch_detection.py --config configs/2403_p09_anomaly_glitch_detection.json",
  "config": "configs/2403_p09_anomaly_glitch_detection.json",
  "elapsed_s": 339.638,
  "feature_columns": [
    "amplitude_adc",
    "q_template_rmse",
    "peak_sample",
    "area_norm",
    "late_fraction",
    "early_fraction",
    "width_half",
    "baseline_mad",
    "baseline_slope",
    "raw_max_adc",
    "saturation_count",
    "secondary_peak",
    "secondary_sep",
    "post_peak_min",
    "undershoot_area",
    "cfd20_sample",
    "timing_span_dup"
  ],
  "git_commit": "d3b2beb217c7157693da45e3e8824489c7a8f036",
  "input_sha256": [
    {
      "bytes": 11638901,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0031.root",
      "sha256": "9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7"
    },
    {
      "bytes": 12157812,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0032.root",
      "sha256": "649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff"
    },
    {
      "bytes": 16781109,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0033.root",
      "sha256": "1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973"
    },
    {
      "bytes": 11697434,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0034.root",
      "sha256": "69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51"
    },
    {
      "bytes": 7793651,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0035.root",
      "sha256": "a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea"
    },
    {
      "bytes": 6167361,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0036.root",
      "sha256": "1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee"
    },
    {
      "bytes": 14369738,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0037.root",
      "sha256": "6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3"
    },
    {
      "bytes": 8625385,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0039.root",
      "sha256": "b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568"
    },
    {
      "bytes": 9266489,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0040.root",
      "sha256": "0d4ebb2f14673aea000c454fd8a4be2c56d6028c31e26a82c1ecd85578128f17"
    },
    {
      "bytes": 9691925,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0041.root",
      "sha256": "72f7a53810bcc4858c2d56e64bdc3bcbb94b9f8e34d35b79c202a77328eb8010"
    },
    {
      "bytes": 9767653,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0042.root",
      "sha256": "b941a6a777414912a0db865a87f68370accf916348340d2249972018f2e61898"
    },
    {
      "bytes": 1227977,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0044.root",
      "sha256": "0ac6d667ebf7c1b47d037dde649e5977cdc6012d80abb6a311516bc67d03ad50"
    },
    {
      "bytes": 13786671,
      "path": "/home/billy/ccb-data/data/extracted/root/root/hrdb_run_0045.root",
      "sha256": "b7bf2921edc3f776390cf50efe6901cb99f9807d7ae04ab5d8925348b74eb96b"
    },
    {
      "bytes": 412227,
```

Regenerate with:

```bash
MPLCONFIGDIR=/tmp/mpl-p09-2403 /home/billy/anaconda3/bin/python scripts/ticket_2403_p09_anomaly_glitch_detection.py --config configs/2403_p09_anomaly_glitch_detection.json
```
