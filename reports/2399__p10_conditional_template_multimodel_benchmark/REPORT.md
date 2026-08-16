# Study report: P10-2399 - Conditional generative pulse templates

- **Ticket:** #2399 - P10: Conditional generative pulse templates
- **Author (worker label):** testbeam-laptop-1
- **Date:** 2026-08-16
- **Depends on:** S00, S01
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** 1bea179d8e1aaf6679c3774c24256f780ed28675
- **Config:** `configs/2399_p10_conditional_template_multimodel.yaml`

## 0. Question

Can a learned conditional template family over log-amplitude and stave identity improve the S01 median amplitude-binned pulse templates on run-held-out B-stave pulses?  The primary endpoint was pre-registered as the analysis-run mean aligned normalized-waveform residual,

\[
Q_m = |R_{eval}|^{-1} \sum_{r \in R_{eval}} n_r^{-1}
      \sum_{i \in r} |J_i|^{-1} \sum_{j \in J_i}
      [y_{ij} - \hat s_m(j \mid \log A_i, b_i)]^2 .
\]

with 95% confidence intervals from bootstrap resampling of held-out runs.  Secondary evidence uses the same learned templates in a discrete phase fit and reports pairwise B4/B6/B8 timing `sigma68`.

## 1. Reproduction

The raw-ROOT reproduction gate was rerun from `/home/billy/ccb-data/data/extracted/root/root`, using the S00 B-stave selection `A > 1000` ADC after a four-sample median pedestal subtraction.

| quantity                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses |         640737 |       640737 |       0 |           0 | True   |
| analysis selected rows          |         377362 |       377362 |       0 |           0 | True   |

The count match is exact at zero tolerance, so the benchmark proceeded.

## 2. Traditional Method

The traditional comparator is the strong S01 empirical template library.  Pulses are CFD20-aligned, amplitude-normalized, and grouped by stave and amplitude bin.  For bin edges
`[1000, 1500, 2200, 3200, 4700, 6800, 10000, 15000, 25000]`, the template is the componentwise median

\[
\hat s_{med}(j \mid b,k)=\operatorname{median}_{i \in \mathcal T(b,k)} y_i(j),
\]

where `b` is stave and `k` is amplitude bin.  Bins with fewer than 30 calibration pulses use the stave-level median fallback.  Only calibration runs train templates; all reported metrics are on disjoint analysis runs.

## 3. ML and NN Methods

All learned methods receive the same condition vector: standardized `log(A)`, its square and cube, stave one-hot indicators, and log-amplitude-by-stave interactions.  They do not receive run number, event number, timing residuals, or the target waveform.  Hyperparameters were selected with GroupKFold by run on calibration pulses.

The benchmarked learned methods were:

- **ridge:** multi-output ridge regression for the 18 aligned samples.
- **gradient_boosted_trees:** multi-output histogram gradient-boosted trees.
- **mlp:** two-hidden-layer conditional MLP.
- **conditional_1d_cnn:** condition-to-sequence decoder with 1D convolutional smoothing layers.
- **residual_mlp_hybrid:** new architecture for this ticket; it starts from the empirical median template and learns a small conditional residual correction.

Mean CV rows:

| Method | Selected hyperparameters | CV q MSE |
|---|---|---:|
| conditional_1d_cnn | channels=16.0 | 0.260668 |
| gradient_boosted_trees | max_iter=35.0 | 0.0546379 |
| mlp | hidden_dim=32.0 | 0.210896 |
| residual_mlp_hybrid | hidden_dim=32.0 | 0.073954 |
| ridge | alpha=10.0 | 0.0544649 |
| ridge | alpha=1.0 | 0.0544669 |
| ridge | alpha=0.1 | 0.0544671 |
| ridge | alpha=100.0 | 0.0544884 |
| ridge | alpha=1000.0 | 0.0551567 |

## 4. Head-to-Head Benchmark

Primary metric is lower-is-better `analysis_run_mean_q_template_mse`; timing is a secondary lower-is-better pairwise residual width.

| Method | Family | q MSE [95% CI] | Delta vs traditional [95% CI] | Timing sigma68 ns [95% CI] |
|---|---|---:|---:|---:|
| gradient_boosted_trees | ml_nn | 0.0568449 [0.046071, 0.0681722] | -0.0240957 [-0.0276673, -0.0209691] | 1.353 [0.9947, 1.672] |
| ridge | ml_nn | 0.0577596 [0.0478518, 0.0687774] | -0.023181 [-0.0265656, -0.020005] | 1.267 [0.8635, 1.668] |
| mlp | ml_nn | 0.0758842 [0.0630204, 0.088444] | -0.00505638 [-0.00794716, -0.00218635] | 1.425 [1.257, 1.622] |
| conditional_1d_cnn | ml_nn | 0.0777803 [0.0641401, 0.0906023] | -0.00316026 [-0.00678623, 0.00105911] | 3.019 [2.769, 3.218] |
| residual_mlp_hybrid | new_hybrid | 0.0783947 [0.0659553, 0.0910793] | -0.00254589 [-0.00541028, 0.000894448] | 4.361 [4.167, 4.537] |
| traditional_empirical_median_bins | traditional | 0.0809406 [0.0675363, 0.095245] | 0 [0, 0] | 3.789 [3.699, 3.881] |

**Winner:** `gradient_boosted_trees` by the pre-registered primary metric.  The winner's q MSE was 0.0568449 with 95% CI [0.046071, 0.0681722].  The traditional median-bin baseline is considered beaten only if the run-bootstrap CI for method minus traditional is wholly below zero.

## 5. Falsification

- **Pre-registration:** lower run-mean q-template MSE at two-sided alpha = 0.05; bootstrap unit is run, not event.
- **Falsification test:** a learned method fails to beat the strong baseline if its delta-versus-traditional CI overlaps or exceeds zero.
- **Multiplicity:** five learned methods were compared with one traditional baseline; the winner claim is descriptive unless the delta CI excludes zero after considering this model family sweep.
- **Result:** `gradient_boosted_trees` is the numerical winner.  `ml_beats_traditional` is `True`.

## 6. Threats to Validity

- **Benchmark/selection:** the empirical median-bin baseline is strong and uses the established S01 construction.  Learned models use the same target waveforms and held-out runs.
- **Data leakage:** split is by run.  Calibration groups train and tune; analysis groups evaluate.  Features exclude run id, event id, and downstream residual labels.
- **Metric misuse:** q MSE is directly matched to the template-quality claim; timing is secondary because phase fitting can favor smooth biased templates differently than pointwise waveform fidelity.
- **Post-hoc selection:** the model classes and hyperparameter grids are fixed in the committed config.  The new residual hybrid is included because it is physically sensible for conditional template families: it regularizes the learned correction around the measured median template.

## 6a. Systematics and Caveats

The bootstrap CI treats runs as exchangeable blocks and therefore captures run-to-run variation, but it does not by itself cover all detector systematics.  The leading systematic terms are: pedestal definition, CFD alignment fraction, amplitude-bin edge placement, train/evaluation run-family transport, and the finite hyperparameter grid.  The count gate uses the same S00 amplitude cut and pedestal convention as the prior analyses, so a changed pedestal estimator would coherently move both the reproduced count and template residuals.  The timing metric is deliberately secondary: these templates are optimized for waveform fidelity, and a smoother but biased template can sometimes reduce pairwise `sigma68` while worsening pointwise q-template MSE.  No GEANT4 truth or particle-ID truth labels are used; conclusions are therefore about empirical template quality, not microscopic pulse-generation truth.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`; input file hashes are in `input_sha256.csv`; output file hashes are in `output_sha256.csv`.  Commands, random seeds, git commit, config hash, script hash, and runtime are recorded there.

## 8. Findings and Next Steps

The analysis reproduces the S00/S01 selected-pulse count exactly from raw ROOT and shows that conditional template learning is not automatically superior to median empirical bins.  The winner field in `result.json` records the primary-metric winner and the adoption flag records whether that result clears the strong-baseline criterion.  The dominant systematic is run-family transport: Sample I and Sample II have different amplitude and phase populations, so any continuous conditional model can interpolate within a family but still fail external family transfer.  A useful follow-up would be a physics-constrained conditional spline/normalizing-flow template with explicit timewalk and saturation state, but no ticket was appended here because related P10 follow-ups already exist.

## 9. Reproducibility

Regenerate all artifacts with:

```bash
/home/billy/anaconda3/bin/python scripts/ticket_2399_p10_conditional_template_multimodel.py --config configs/2399_p10_conditional_template_multimodel.yaml
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `template_bin_counts.csv`, `method_metrics.csv`, `method_cv.csv`, `q_template_run_benchmark.csv`, `timing_run_benchmark.csv`, `input_sha256.csv`, `output_sha256.csv`, and three PNG figures.
