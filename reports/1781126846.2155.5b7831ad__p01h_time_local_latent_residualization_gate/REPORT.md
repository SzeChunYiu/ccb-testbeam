# P01h: time-local latent residualization gate

**Study ID:** P01h  
**Ticket:** `1781126846.2155.5b7831ad`  
**Author:** `testbeam-laptop-1`  
**Date:** 2026-07-09  
**Depends on:** S00/S01 raw B-stack reproduction, P01b frozen waveform latent artifact, P01d/P01e leakage audits.  
**Git commit:** `6ea6b53502f8475a7c07d9637467f9cedd2cc696`  
**Config:** `configs/p01h_1781126846_2155_5b7831ad_time_local_latent_residualization_gate.json`

## 0. Question
Can the loader-verified P01b latent waveform coordinates retain time-local pulse-shape signal after explicit residualization of sample/run-family, stave, amplitude, peak-phase, topology, q-template, timing-tail, and dropout-like atoms, and do neural probes beat a strong hand-shape traditional baseline on run-heldout events?

The pre-registered primary metric is run-heldout balanced accuracy for `physics_q_template_top_quartile`; the study-level winner is ranked by
`mean physics balanced accuracy - 0.20 * mean nuisance balanced accuracy`, with 95 percent run-block bootstrap CIs shown for each task.

## 1. Reproduction
The analysis independently rescanned raw B-stack ROOT files before modelling. Selection used the standing S00 rule: B2/B4/B6/B8, median baseline over samples 0--3, and baseline-subtracted maximum amplitude greater than 1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| P01b latent rows | 640737 | 640737 | 0 | 0 | True |

The P01b artifact SHA-256 is `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be`; its `(run,event,stave)` key hash is `605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193`.

## 2. Traditional Method
The traditional comparator is a hand-engineered waveform representation: peak sample, normalized area, early/late/tail fractions, threshold widths, steepest down-step, secondary-peak proxy, final-sample fraction, plus six train-fit PCA coordinates of the normalized 18-sample waveform. Let `x` be this vector and `N` the nuisance design matrix containing log amplitude and one-hot sample epoch/run family, multiplicity, amplitude quartile, and stave. On train runs only, each feature column is residualized by ridge projection,

`r_x = x - N (N^T N + alpha I)^(-1) N^T x`, with `alpha = 1.0`.

The classifier is a standardized ridge classifier on `r_x`. This is the non-ML baseline: no learned waveform convolution, no boosted trees, and no P01b latent variables. There is no chi-square fit in this classifier comparison; goodness is reported by full held-out balanced-accuracy distributions through run-block bootstrap.

## 3. ML And NN Methods
All ML/NN methods use the identical train/heldout split by run: heldout runs `42, 57, 64, 65`. No event-level shuffling is used. Targets are weak, internally defined proxies, not particle truth labels.

Models benchmarked:

| Method | Input | Model |
|---|---|---|
| `latent_resid_ridge` | residualized P01b latent | ridge classifier |
| `latent_resid_gbt` | residualized P01b latent | histogram gradient-boosted trees |
| `latent_resid_mlp` | residualized P01b latent | two-layer MLP |
| `waveform_1d_cnn` | normalized raw 18-sample waveform | small 1D CNN |
| `residual_fusion_mlp_new_arch` | residualized hand/PCA plus residualized latent | late-fusion MLP |

For binary targets, ROC AUC, average precision, and Brier score are included in `benchmark_metrics.csv`; multiclass targets use macro one-vs-rest ROC AUC where defined. Neural scores are rankings, not calibrated probabilities; Brier values are therefore diagnostic only.

Target support:

| target                           | family        |   train_non_null |   heldout_non_null | heldout_distribution                         |
|:---------------------------------|:--------------|-----------------:|-------------------:|:---------------------------------------------|
| physics_q_template_top_quartile  | physics_proxy |            71018 |              10498 | {"0": 7764, "1": 2734}                       |
| physics_peak_group               | physics_proxy |            71018 |              10498 | {"0": 3844, "1": 5236, "2": 1418}            |
| physics_timing_tail_top_quartile | physics_proxy |            10869 |               1210 | {"0": 840, "1": 370}                         |
| physics_anomaly_proxy_top5       | physics_proxy |            71018 |              10498 | {"0": 9985, "1": 513}                        |
| nuisance_sample_epoch            | nuisance      |            71018 |              10498 | {"0": 4594, "1": 5904}                       |
| nuisance_topology_multiplicity   | nuisance      |            71018 |              10498 | {"0": 5012, "1": 2512, "2": 2974}            |
| nuisance_amplitude_quartile      | nuisance      |            71018 |              10498 | {"0": 3482, "1": 2909, "2": 2580, "3": 1527} |
| nuisance_stave                   | nuisance      |            71018 |              10498 | {"0": 4800, "1": 3409, "2": 1666, "3": 623}  |

## 4. Head-To-Head Benchmark
Primary task (`physics_q_template_top_quartile`):

| method                            |   value |   ci_low |   ci_high |   roc_auc |   average_precision |   brier |   heldout_rows |
|:----------------------------------|--------:|---------:|----------:|----------:|--------------------:|--------:|---------------:|
| residual_fusion_mlp_new_arch      |   0.88  |    0.871 |     0.892 |     0.952 |               0.896 |   0.09  |          10498 |
| latent_resid_gbt                  |   0.791 |    0.775 |     0.809 |     0.883 |               0.796 |   0.127 |          10498 |
| latent_resid_mlp                  |   0.772 |    0.765 |     0.781 |     0.867 |               0.774 |   0.14  |          10498 |
| waveform_1d_cnn                   |   0.734 |    0.722 |     0.747 |     0.806 |               0.622 |   0.22  |          10498 |
| traditional_hand_pca_residualized |   0.723 |    0.716 |     0.731 |     0.813 |               0.702 |   0.163 |          10498 |
| latent_resid_ridge                |   0.695 |    0.667 |     0.72  |     0.772 |               0.661 |   0.178 |          10498 |

Aggregate method ranking:

| method                            |   mean_physics_bacc |   physics_ci_low_mean |   physics_ci_high_mean |   mean_nuisance_bacc |   winner_score |
|:----------------------------------|--------------------:|----------------------:|-----------------------:|---------------------:|---------------:|
| residual_fusion_mlp_new_arch      |               0.832 |                 0.813 |                  0.845 |                0.933 |          0.645 |
| traditional_hand_pca_residualized |               0.697 |                 0.676 |                  0.725 |                0.367 |          0.623 |
| latent_resid_ridge                |               0.664 |                 0.648 |                  0.684 |                0.33  |          0.598 |
| latent_resid_gbt                  |               0.741 |                 0.719 |                  0.763 |                0.717 |          0.597 |
| latent_resid_mlp                  |               0.726 |                 0.712 |                  0.743 |                0.727 |          0.581 |
| waveform_1d_cnn                   |               0.662 |                 0.645 |                  0.672 |                0.515 |          0.559 |

Winner: **residual_fusion_mlp_new_arch**. The strong traditional hand/PCA ridge baseline achieves mean physics balanced accuracy `0.697` with mean nuisance balanced accuracy `0.367`. The winner achieves mean physics balanced accuracy `0.832` and mean nuisance balanced accuracy `0.933`. The improvement over the traditional method in winner score is `0.022`.

## 4.1 Systematics And Caveats
The dominant systematic is target construction: q-template, timing-tail, peak-phase, and anomaly labels are detector-quality proxies derived from the same raw pulses, not external truth. The q-template target uses q-template RMSE when finite and falls back to autoencoder RMSE for the small non-finite subset; this prevents NaN thresholds but couples the target to reconstruction quality. The late-fusion winner has high nuisance balanced accuracy, so its physics gain may still include residual acquisition-domain information that the linear nuisance projection did not remove. The hand/PCA baseline has lower nuisance predictability and is therefore the more conservative representation despite lower physics-proxy accuracy.

The bootstrap CI treats run identity as the resampling block, but only four heldout runs are available; intervals should be read as a finite-run sensitivity check rather than an asymptotic confidence statement. No hyperparameter search beyond the fixed predeclared model families was performed, which reduces post-hoc model selection but leaves performance potentially under-tuned.

## 5. Falsification
Pre-registration comes from the ticket: residualized waveform coordinates must retain physics-proxy signal while suppressing nuisance/domain atom predictability under run-heldout splitting. The explicit falsifier is that residualized latent or neural methods do not improve the pre-registered winner score over the hand/PCA ridge baseline, or that the apparent gain is dominated by nuisance target predictability.

The tested method families are six planned comparisons, so uncorrected model-picking claims are not made. The selected winner remains a descriptive benchmark result; any claim of superiority should be rechecked in a fresh ticket with the winning architecture frozen.

Negative controls and leakage sentinels:

| check                           | value                        | pass   | detail                                                                           |
|:--------------------------------|:-----------------------------|:-------|:---------------------------------------------------------------------------------|
| train_heldout_run_overlap       | 0                            | True   | Run-heldout split has no shared run ids.                                         |
| latent_raw_key_alignment        | 0.0                          | True   | P01b latent rows match the raw ROOT recount by run, event, stave, and amplitude. |
| winner_nuisance_penalty_applied | 0.6451310035390132           | True   | Winner is ranked by physics accuracy penalized by nuisance predictability.       |
| primary_task_winner             | residual_fusion_mlp_new_arch | True   | Primary target ranking is reported separately from the aggregate winner.         |

## 6. Threats To Validity
**Benchmark/selection.** The hand/PCA ridge baseline is intentionally strong and receives the same nuisance residualization and train rows as the latent methods. The GBT, MLP, CNN, and fusion methods are benchmarked on the same heldout runs and targets.

**Data leakage.** The split is by run. Nuisance residualizers and PCA are fit on train runs only. Features exclude run number and event number. Labels are weak proxies derived from q-template residuals, peak phase, timing tail, and anomaly summaries; they must not be interpreted as ground truth particle classes.

**Metric misuse.** The headline metric is balanced accuracy because several targets are imbalanced. ROC AUC/AP/Brier are reported for binary tasks, and CIs use run-block bootstrap. No narrow-core timing resolution is quoted here because this is a representation/probe gate rather than a timing-resolution fit.

**Post-hoc selection.** The primary target, heldout runs, method list, and winner score are fixed in the config before execution. The new architecture is a single pre-declared late-fusion residual MLP, not a post-hoc architecture search.

## 7. Provenance Manifest
`manifest.json` records raw ROOT hashes, artifact hashes, command line, git commit, seeds, environment, and output hashes. `input_sha256.csv` pins the ROOT files and derived artifacts.

## 8. Findings And Next Steps
Residualized latent methods retain measurable pulse-shape proxy information on heldout runs, but the dominant caveat is that target definitions are still internally defined detector proxies. The fusion winner suggests that the frozen latent and hand/PCA basis encode complementary shape information after nuisance projection; it does not prove that either is physics-causal.

Hypothesis: time-local pulse morphology contains a component that survives acquisition-epoch and amplitude/topology residualization, but the safest use is as a regularized auxiliary representation combined with hand features rather than as a standalone latent truth proxy.

Queued follow-up: `P01m: event-block shuffled downstream transfer falsifier for the P01h residual-fusion gate`. Expected information gain: this freezes the P01h residual-fusion representation and tests whether its proxy-classification gain transfers to pair-timing sigma68 and charge-bias deltas after event-block shuffling removes temporal acquisition shortcuts; it would distinguish reusable pulse-shape information from residual time-block leakage.

## 9. Reproducibility
Regenerate with:

```bash
MPLCONFIGDIR=reports/1781126846.2155.5b7831ad__p01h_time_local_latent_residualization_gate/mplconfig \
  /home/billy/anaconda3/bin/python scripts/p01h_1781126846_2155_5b7831ad_time_local_latent_residualization_gate.py \
  --config configs/p01h_1781126846_2155_5b7831ad_time_local_latent_residualization_gate.json
```

Artifacts include `benchmark_metrics.csv`, `method_summary.csv`, `target_definitions.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, two PNG benchmark figures, `result.json`, and `manifest.json`.
