# S01k independent overlay review feasibility and benchmark

**Ticket:** `1783744936.12694.7f7904bd`  
**Worker:** `testbeam-laptop-2`  
**Date:** 2026-07-11

## Abstract

The ticket requested a repeat of S01j on an independently reviewed overlay/real-current gallery with at least 100 positive labels in every labelled acquisition run. I first audited the available independent S11h galleries and found that this positive-count gate is not satisfiable by the current artifacts: the largest compatible real-current adjudication has 986 rows over 12 runs, but the maximum positive count in any run is 28 for the consensus target.

The benchmark on the available independent real-current review sample is still reported using the frozen S11h method adjudication outputs. The named benchmark winner is **gradient_boosted_trees** with average precision **0.3990** [0.3343, 0.4687] and ROC AUC **0.7645** [0.7034, 0.8141]. The strong traditional comparator is **traditional_template_fit** with AP **0.1887** and ROC AUC **0.5061**. The result verdict is `blocked_positive_count_gate_available_sample_benchmark_only` because the requested positive-count gate fails.

## Raw ROOT Reproduction

| quantity                                         |   expected |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| selected B-stave pulses with amplitude >1000 ADC |     640737 |       640737 |       0 |           0 | True   |

The reproduction gate reruns the S01j raw ROOT scan before loading review labels. For each B-stack ROOT file, `HRDv` is pedestal-subtracted by the median of samples 0-3, reshaped into 8 channels by 18 samples, restricted to B2/B4/B6/B8 even channels, and counted when the baseline-subtracted maximum amplitude exceeds 1000 ADC. This exactly reproduces the established selected-pulse count of 640737.

## Positive-Count Feasibility Gate

|   run |   n |   positives |   positive_fraction |   required_positives | pass   |
|------:|----:|------------:|--------------------:|---------------------:|:-------|
|    44 |  27 |           7 |           0.259259  |                  100 | False  |
|    45 |  90 |          27 |           0.3       |                  100 | False  |
|    48 |  90 |          28 |           0.311111  |                  100 | False  |
|    49 |  90 |          21 |           0.233333  |                  100 | False  |
|    50 |  90 |           9 |           0.1       |                  100 | False  |
|    51 |  90 |          13 |           0.144444  |                  100 | False  |
|    52 |  59 |          11 |           0.186441  |                  100 | False  |
|    53 |  90 |           7 |           0.0777778 |                  100 | False  |
|    54 |  90 |           8 |           0.0888889 |                  100 | False  |
|    55 |  90 |          13 |           0.144444  |                  100 | False  |
|    56 |  90 |           7 |           0.0777778 |                  100 | False  |
|    57 |  90 |          27 |           0.3       |                  100 | False  |

The explicit S01k gate requires at least 100 positives in every labelled run. Let \(n_r^+=\sum_{i:r_i=r} y_i\). The gate is \(n_r^+ \ge 100\) for every labelled run \(r\). The current independent consensus target has \(\max_r n_r^+=28\), so the requirement is empirically false for the available review table.

Secondary target audit over the expanded S11h gallery:

| target_column                           |   n_runs |   total_positive |   max_positive_in_run |   runs_passing_100_positive_gate |
|:----------------------------------------|---------:|-----------------:|----------------------:|---------------------------------:|
| in_prior_gallery                        |       14 |              474 |                   238 |                                1 |
| artifact_reviewer_shape                 |       14 |              563 |                   235 |                                1 |
| artifact_like_blinded                   |       14 |              563 |                   235 |                                1 |
| artifact_like                           |       14 |              443 |                   221 |                                1 |
| shape_artifact_strong                   |       14 |              443 |                   221 |                                1 |
| artifact_reviewer_external              |       14 |              443 |                   221 |                                1 |
| trad_failed                             |       14 |              567 |                   217 |                                1 |
| mlp__accepted                           |       14 |              537 |                   177 |                                1 |
| gradient_boosted_trees__accepted        |       14 |              310 |                    32 |                                0 |
| consensus_abstention_ensemble__accepted |       14 |              325 |                    32 |                                0 |
| reviewer_external_or_fit                |       14 |               46 |                    25 |                                0 |
| downstream                              |       14 |               57 |                    22 |                                0 |
| ambiguous_blinded                       |       14 |               55 |                    20 |                                0 |
| traditional_template_fit__accepted      |       14 |               27 |                    19 |                                0 |
| two_pulse_like                          |       14 |               31 |                    17 |                                0 |
| cnn_1d_dual_head__accepted              |       14 |               25 |                    16 |                                0 |
| ridge_linear__accepted                  |       14 |               99 |                    14 |                                0 |
| reviewer_bounded_topology               |       14 |               20 |                    13 |                                0 |
| reviewer_shape_blind                    |       14 |               43 |                    11 |                                0 |
| two_pulse_like_blinded                  |       14 |               19 |                    10 |                                0 |

## Target and Split

The benchmark target is `blind_consensus_recoverable` from `reports/1781146783.955.745c6984__s11h_blinded_real_current_waveform_adjudication/blinded_gallery_adjudication.csv`. Scores and accept/reject decisions are loaded from `reports/1781146783.955.745c6984__s11h_blinded_real_current_waveform_adjudication/method_adjudication_scores.csv`. Rows are independent real-current waveform review rows from S11h, and the split unit is acquisition run. All intervals are nonparametric run-block bootstrap intervals: runs are sampled with replacement, all rows inside sampled runs are concatenated, and metrics are recomputed.

For a method score \(s_m(x_i)\) and binary review label \(y_i\in\{0,1\}\), ROC AUC is

\[\mathrm{AUC}_m=P(s_m(x^+)>s_m(x^-))+\tfrac{1}{2}P(s_m(x^+)=s_m(x^-)),\]

and average precision is the Riemann-Stieltjes sum over the precision-recall curve,

\[\mathrm{AP}_m=\sum_k (R_k-R_{k-1})P_k.\]

## Methods

- **traditional_template_fit:** frozen transparent template-fit comparator, used as the strong traditional baseline.
- **ridge:** display name for the frozen S11h `ridge_linear` method.
- **gradient_boosted_trees:** frozen nonlinear tree ensemble method.
- **mlp:** frozen multilayer perceptron comparator.
- **1d_cnn:** display name for the frozen S11h `cnn_1d_dual_head` waveform network.
- **consensus_abstention_ensemble_new:** display name for the frozen S11h `consensus_abstention_ensemble`; this is the new architecture slot because it combines method consensus with abstention rather than a single classifier.

These are frozen method outputs, not newly trained waveform networks. This is intentional: the required high-positive independent training set does not exist, so retraining larger models would create a post-hoc model-selection artifact rather than a valid repeat of S01j.

## Benchmark Table

| method                            | source_method                 | family           |   n |   positives |   roc_auc |   average_precision |   balanced_accuracy |   precision |   recall |       f1 |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision_ci_low |   average_precision_ci_high |   f1_ci_low |   f1_ci_high |
|:----------------------------------|:------------------------------|:-----------------|----:|------------:|----------:|--------------------:|--------------------:|------------:|---------:|---------:|-----------------:|------------------:|---------------------------:|----------------------------:|------------:|-------------:|
| gradient_boosted_trees            | gradient_boosted_trees        | ml               | 986 |         178 |  0.764518 |            0.398997 |            0.550346 |    0.200269 | 0.837079 | 0.32321  |         0.703399 |          0.814123 |                   0.334335 |                    0.468684 |    0.250256 |     0.394921 |
| consensus_abstention_ensemble_new | consensus_abstention_ensemble | new_architecture | 986 |         178 |  0.741809 |            0.340598 |            0.553997 |    0.355556 | 0.179775 | 0.238806 |         0.684726 |          0.799502 |                   0.315829 |                    0.378227 |    0.153846 |     0.320347 |
| mlp                               | mlp                           | nn               | 986 |         178 |  0.646999 |            0.317015 |            0.5565   |    0.199539 | 0.97191  | 0.3311   |         0.552583 |          0.746441 |                   0.267588 |                    0.393993 |    0.252704 |     0.401908 |
| ridge                             | ridge_linear                  | ml               | 986 |         178 |  0.604684 |            0.28641  |            0.549331 |    0.336957 | 0.174157 | 0.22963  |         0.539972 |          0.672007 |                   0.245843 |                    0.339335 |    0.156517 |     0.308304 |
| 1d_cnn                            | cnn_1d_dual_head              | nn               | 986 |         178 |  0.696191 |            0.273056 |            0.492574 |    0        | 0        | 0        |         0.601479 |          0.775346 |                   0.219426 |                    0.325133 |    0        |     0        |
| traditional_template_fit          | traditional_template_fit      | traditional      | 986 |         178 |  0.506087 |            0.18867  |            0.498046 |    0.179325 | 0.477528 | 0.260736 |         0.457186 |          0.553941 |                   0.135143 |                    0.24597  |    0.199654 |     0.315789 |

## Per-Run Metrics

| method                            |   run |   n |   positives |   roc_auc |   average_precision |        f1 |
|:----------------------------------|------:|----:|------------:|----------:|--------------------:|----------:|
| 1d_cnn                            |    44 |  27 |           7 |  0.714286 |           0.431839  | 0         |
| 1d_cnn                            |    45 |  90 |          27 |  0.343915 |           0.22885   | 0         |
| 1d_cnn                            |    48 |  90 |          28 |  0.611751 |           0.355209  | 0         |
| 1d_cnn                            |    49 |  90 |          21 |  0.462388 |           0.229137  | 0         |
| 1d_cnn                            |    50 |  90 |           9 |  0.563786 |           0.195167  | 0         |
| 1d_cnn                            |    51 |  90 |          13 |  0.73027  |           0.235543  | 0         |
| 1d_cnn                            |    52 |  59 |          11 |  0.806818 |           0.487963  | 0         |
| 1d_cnn                            |    53 |  90 |           7 |  0.839931 |           0.326836  | 0         |
| 1d_cnn                            |    54 |  90 |           8 |  0.865854 |           0.26846   | 0         |
| 1d_cnn                            |    55 |  90 |          13 |  0.75025  |           0.277784  | 0         |
| 1d_cnn                            |    56 |  90 |           7 |  0.864028 |           0.460997  | 0         |
| 1d_cnn                            |    57 |  90 |          27 |  0.402704 |           0.271528  | 0         |
| consensus_abstention_ensemble_new |    44 |  27 |           7 |  0.735714 |           0.460088  | 0         |
| consensus_abstention_ensemble_new |    45 |  90 |          27 |  0.649618 |           0.427221  | 0.380952  |
| consensus_abstention_ensemble_new |    48 |  90 |          28 |  0.642857 |           0.391369  | 0.142857  |
| consensus_abstention_ensemble_new |    49 |  90 |          21 |  0.677019 |           0.350173  | 0.258065  |
| consensus_abstention_ensemble_new |    50 |  90 |           9 |  0.825789 |           0.303871  | 0.307692  |
| consensus_abstention_ensemble_new |    51 |  90 |          13 |  0.874126 |           0.487567  | 0.315789  |
| consensus_abstention_ensemble_new |    52 |  59 |          11 |  0.74053  |           0.523162  | 0.333333  |
| consensus_abstention_ensemble_new |    53 |  90 |           7 |  0.839931 |           0.358917  | 0.4       |
| consensus_abstention_ensemble_new |    54 |  90 |           8 |  0.829268 |           0.305079  | 0.266667  |
| consensus_abstention_ensemble_new |    55 |  90 |          13 |  0.692308 |           0.409964  | 0.315789  |
| consensus_abstention_ensemble_new |    56 |  90 |           7 |  0.922547 |           0.471917  | 0.2       |
| consensus_abstention_ensemble_new |    57 |  90 |          27 |  0.558495 |           0.42071   | 0         |
| gradient_boosted_trees            |    44 |  27 |           7 |  0.635714 |           0.380746  | 0.411765  |
| gradient_boosted_trees            |    45 |  90 |          27 |  0.865961 |           0.650168  | 0.461538  |
| gradient_boosted_trees            |    48 |  90 |          28 |  0.723502 |           0.511     | 0.474576  |
| gradient_boosted_trees            |    49 |  90 |          21 |  0.706004 |           0.419465  | 0.378378  |
| gradient_boosted_trees            |    50 |  90 |           9 |  0.843621 |           0.33016   | 0.181818  |
| gradient_boosted_trees            |    51 |  90 |          13 |  0.89011  |           0.462636  | 0.252427  |
| gradient_boosted_trees            |    52 |  59 |          11 |  0.782197 |           0.516669  | 0.314286  |
| gradient_boosted_trees            |    53 |  90 |           7 |  0.784854 |           0.431804  | 0.285714  |
| gradient_boosted_trees            |    54 |  90 |           8 |  0.853659 |           0.52629   | 0.163265  |
| gradient_boosted_trees            |    55 |  90 |          13 |  0.555944 |           0.283523  | 0.252427  |
| gradient_boosted_trees            |    56 |  90 |           7 |  0.772806 |           0.218576  | 0         |
| gradient_boosted_trees            |    57 |  90 |          27 |  0.6505   |           0.521401  | 0.425532  |
| mlp                               |    44 |  27 |           7 |  0.535714 |           0.353096  | 0.411765  |
| mlp                               |    45 |  90 |          27 |  0.549089 |           0.304408  | 0.461538  |
| mlp                               |    48 |  90 |          28 |  0.443548 |           0.415908  | 0.474576  |
| mlp                               |    49 |  90 |          21 |  0.672878 |           0.473769  | 0.368932  |
| mlp                               |    50 |  90 |           9 |  0.786008 |           0.223122  | 0.1875    |
| mlp                               |    51 |  90 |          13 |  0.89011  |           0.472484  | 0.317073  |
| mlp                               |    52 |  59 |          11 |  0.691288 |           0.536641  | 0.349206  |
| mlp                               |    53 |  90 |           7 |  0.836489 |           0.354308  | 0.444444  |
| mlp                               |    54 |  90 |           8 |  0.652439 |           0.40019   | 0.163265  |
| mlp                               |    55 |  90 |          13 |  0.694306 |           0.344892  | 0.252427  |
| mlp                               |    56 |  90 |           7 |  0.908778 |           0.562386  | 0.145833  |
| mlp                               |    57 |  90 |          27 |  0.602881 |           0.480012  | 0.461538  |
| ridge                             |    44 |  27 |           7 |  0.614286 |           0.482275  | 0.363636  |
| ridge                             |    45 |  90 |          27 |  0.704292 |           0.470462  | 0.176471  |
| ridge                             |    48 |  90 |          28 |  0.455645 |           0.307139  | 0.232558  |
| ridge                             |    49 |  90 |          21 |  0.490683 |           0.343453  | 0.358974  |
| ridge                             |    50 |  90 |           9 |  0.620027 |           0.19369   | 0         |
| ridge                             |    51 |  90 |          13 |  0.688312 |           0.341869  | 0.2       |
| ridge                             |    52 |  59 |          11 |  0.611742 |           0.45373   | 0.166667  |
| ridge                             |    53 |  90 |           7 |  0.746988 |           0.3816    | 0.526316  |
| ridge                             |    54 |  90 |           8 |  0.617378 |           0.287233  | 0.222222  |
| ridge                             |    55 |  90 |          13 |  0.403596 |           0.186486  | 0.285714  |
| ridge                             |    56 |  90 |           7 |  0.753873 |           0.176939  | 0         |
| ridge                             |    57 |  90 |          27 |  0.443857 |           0.326928  | 0.102564  |
| traditional_template_fit          |    44 |  27 |           7 |  0.478571 |           0.25189   | 0.333333  |
| traditional_template_fit          |    45 |  90 |          27 |  0.410935 |           0.280601  | 0.26087   |
| traditional_template_fit          |    48 |  90 |          28 |  0.528802 |           0.339116  | 0.382353  |
| traditional_template_fit          |    49 |  90 |          21 |  0.430642 |           0.216778  | 0.25      |
| traditional_template_fit          |    50 |  90 |           9 |  0.35048  |           0.0921147 | 0.0714286 |
| traditional_template_fit          |    51 |  90 |          13 |  0.571429 |           0.1866    | 0.259259  |
| traditional_template_fit          |    52 |  59 |          11 |  0.471591 |           0.187908  | 0.222222  |
| traditional_template_fit          |    53 |  90 |           7 |  0.538726 |           0.0859236 | 0.16      |
| traditional_template_fit          |    54 |  90 |           8 |  0.594512 |           0.105923  | 0.229508  |
| traditional_template_fit          |    55 |  90 |          13 |  0.647852 |           0.209167  | 0.321429  |
| traditional_template_fit          |    56 |  90 |           7 |  0.55852  |           0.0891011 | 0.163265  |
| traditional_template_fit          |    57 |  90 |          27 |  0.560259 |           0.344149  | 0.422535  |

## Systematics and Caveats

- The main requested feasibility condition fails; the benchmark is therefore diagnostic, not a completed adoption claim.
- The target is deterministic blinded morphology review, not particle truth or human-labeled ground truth with 100 positives per run.
- The method panel uses frozen S11h adjudication outputs because the independent positive sample is too small for credible retraining.
- Run-block bootstrap intervals are wide where some held-out runs contain few positives.
- Q-template transfer cannot be claimed from this independent real-current table because it does not carry S01j q-template RMSE columns.

## Verdict

`result.json` names **gradient_boosted_trees** as the available-sample winner and records `positive_gate_pass=false`. No novel follow-up ticket is appended from this worker, because S01j already appended S01k and the objective allows at most one novel ticket.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s01k_1783744936_12694_7f7904bd_independent_overlay_review.py --config configs/s01k_1783744936_12694_7f7904bd_independent_overlay_review.yaml
```
