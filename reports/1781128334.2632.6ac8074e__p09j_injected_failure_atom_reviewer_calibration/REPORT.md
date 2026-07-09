# P09j: injected-failure atom reviewer calibration

Ticket: `1781128334.2632.6ac8074e`. Worker: `testbeam-laptop-4`.

## Abstract

P09j asks whether the autonomous P09g atom labels for injected false positives, injected false negatives, and raw `D_t`-tail rows survive a blinded reviewer calibration. The analysis freezes the P09g bounded failure gallery and held-out run predictions, constructs three independent deterministic reviewer views from morphology masks, atom-rubric evidence, and hybrid ML counterfactual masks, and compares the frozen traditional atom rubric with ridge, gradient-boosted trees, MLP, 1D-CNN, and a new atom-gated CNN architecture.

## Data and raw-ROOT reproduction

The raw data folder is `data/root/root`. P09g's raw-ROOT reproduction table is reused as the frozen upstream selection ledger, and every referenced ROOT input is re-read from the local data folder for SHA-256 verification in `raw_root_input_verification.csv`. The reproduced parent counts are written to `reproduction_counts_by_run.csv`; these counts are the raw event and selected-pulse denominator for the bounded P09g gallery.

ROOT verification: 8 files matched their frozen P09g hashes; 0 mismatches were found.

## Methods

For row `i` in run `r`, each method emits a binary action `a_{im}`. The primary calibrated target is the blinded reviewer consensus

`y_i = 1[ v_{i,A} + v_{i,B} + v_{i,C} >= 2 ]`,

where reviewer A is ML-mask dominated, reviewer B is frozen-rubric dominated, and reviewer C is a hybrid counterfactual-mask reviewer. The traditional baseline is the frozen P09g atom rubric. ML/NN competitors are the frozen P09g ridge, gradient-boosted tree, MLP, 1D-CNN, and atom-gated CNN scores. No model is retrained on reviewer consensus.

The primary score is curated precision

`PPV_m = sum_i 1[a_{im}=1 and y_i=1] / max(1, sum_i 1[a_{im}=1])`.

Secondary scores are balanced accuracy, action flip rate against the traditional rubric, and explanatory precision among ML-minus-rubric flips:

`EP_m = sum_i 1[a_{im}=y_i and a_{im} != a_{iT}] / max(1, sum_i 1[a_{im} != a_{iT}])`.

All confidence intervals are nonparametric run-block bootstrap intervals: complete runs are resampled with replacement, metrics are recomputed on the concatenated rows, and the 2.5 and 97.5 percentiles are reported.

## Main table

|   curated_precision |   curated_precision_ci_low |   curated_precision_ci_high |   balanced_accuracy |   balanced_accuracy_ci_low |   balanced_accuracy_ci_high |   action_flip_rate |   action_flip_rate_ci_low |   action_flip_rate_ci_high |   explanatory_precision |   explanatory_precision_ci_low |   explanatory_precision_ci_high | method                  | score_column                  | action_column                  |
|--------------------:|---------------------------:|----------------------------:|--------------------:|---------------------------:|----------------------------:|-------------------:|--------------------------:|---------------------------:|------------------------:|-------------------------------:|--------------------------------:|:------------------------|:------------------------------|:-------------------------------|
|            0.98138  |                   0.969683 |                    0.993506 |            0.834852 |                   0.78642  |                    0.880845 |           0.355234 |                  0.317844 |                   0.413596 |                0.91164  |                       0.86128  |                        0.937348 | gradient_boosted_trees  | score_gradient_boosted_trees  | action_gradient_boosted_trees  |
|            0.951831 |                   0.940056 |                    0.968616 |            0.845599 |                   0.819496 |                    0.864516 |           0.394818 |                  0.376153 |                   0.419975 |                0.882225 |                       0.847574 |                        0.906485 | mlp                     | score_mlp                     | action_mlp                     |
|            0.944862 |                   0.932685 |                    0.964564 |            0.708903 |                   0.687367 |                    0.732391 |           0.248167 |                  0.232738 |                   0.270791 |                0.848562 |                       0.796317 |                        0.881706 | cnn1d                   | score_cnn1d                   | action_cnn1d                   |
|            0.940593 |                   0.920617 |                    0.962265 |            0.707527 |                   0.68277  |                    0.737749 |           0.247464 |                  0.220165 |                   0.282705 |                0.847338 |                       0.802038 |                        0.877965 | atom_gated_cnn          | score_atom_gated_cnn          | action_atom_gated_cnn          |
|            0.913319 |                   0.872568 |                    0.956897 |            0.708566 |                   0.675391 |                    0.733387 |           0.261677 |                  0.207888 |                   0.320493 |                0.829864 |                       0.775172 |                        0.865069 | ridge                   | score_ridge                   | action_ridge                   |
|            0.702804 |                   0.623269 |                    0.805568 |            0.525685 |                   0.51734  |                    0.541319 |           0        |                  0        |                   0        |                0        |                       0        |                        0        | traditional_atom_rubric | score_traditional_atom_rubric | action_traditional_atom_rubric |

## Curated precision by taxon

| method                  | taxon                |    n |   reviewer_positive_rate |   curated_precision |   action_rate |
|:------------------------|:---------------------|-----:|-------------------------:|--------------------:|--------------:|
| traditional_atom_rubric | broad_or_saturated   |  623 |                 0.563403 |            0        |    0          |
| traditional_atom_rubric | delayed_peak_or_tail |  692 |                 0.719653 |            0.679825 |    0.32948    |
| traditional_atom_rubric | dropout_step         |   61 |                 0.754098 |            1        |    0.0819672  |
| traditional_atom_rubric | early_pretrigger     | 1147 |                 0.374891 |            0        |    0          |
| traditional_atom_rubric | nominal_shape        |  829 |                 0.279855 |            0        |    0          |
| traditional_atom_rubric | template_mismatch    |  958 |                 0.493737 |            1        |    0.00417537 |
| ridge                   | broad_or_saturated   |  623 |                 0.563403 |            0.958333 |    0.23114    |
| ridge                   | delayed_peak_or_tail |  692 |                 0.719653 |            0.915612 |    0.342486   |
| ridge                   | dropout_step         |   61 |                 0.754098 |            0.888889 |    0.442623   |
| ridge                   | early_pretrigger     | 1147 |                 0.374891 |            0.882155 |    0.258936   |
| ridge                   | nominal_shape        |  829 |                 0.279855 |            0.873786 |    0.124246   |
| ridge                   | template_mismatch    |  958 |                 0.493737 |            0.917749 |    0.241127   |
| gradient_boosted_trees  | broad_or_saturated   |  623 |                 0.563403 |            1        |    0.459069   |
| gradient_boosted_trees  | delayed_peak_or_tail |  692 |                 0.719653 |            0.994186 |    0.49711    |
| gradient_boosted_trees  | dropout_step         |   61 |                 0.754098 |            1        |    0.311475   |
| gradient_boosted_trees  | early_pretrigger     | 1147 |                 0.374891 |            0.952522 |    0.29381    |
| gradient_boosted_trees  | nominal_shape        |  829 |                 0.279855 |            0.935294 |    0.205066   |
| gradient_boosted_trees  | template_mismatch    |  958 |                 0.493737 |            1        |    0.292276   |
| mlp                     | broad_or_saturated   |  623 |                 0.563403 |            0.983871 |    0.398074   |
| mlp                     | delayed_peak_or_tail |  692 |                 0.719653 |            0.993464 |    0.442197   |
| mlp                     | dropout_step         |   61 |                 0.754098 |            1        |    0.52459    |
| mlp                     | early_pretrigger     | 1147 |                 0.374891 |            0.902613 |    0.367044   |
| mlp                     | nominal_shape        |  829 |                 0.279855 |            0.892045 |    0.212304   |
| mlp                     | template_mismatch    |  958 |                 0.493737 |            0.973046 |    0.387265   |

## Result

The winner is `gradient_boosted_trees` on curated precision with run-block bootstrap uncertainty. The result is not a license to replace visual review; it says that the frozen gradient_boosted_trees action agrees best with the deterministic blinded-review calibration induced from the bounded P09g gallery.

## Systematics and caveats

- The reviewer labels are deterministic calibrators derived from frozen displays and masks, not newly collected human labels.
- P09j inherits P09g's bounded support: runs without P09g held-out rows and failure modes absent from the gallery are outside scope.
- The atom-gated CNN is evaluated only as the frozen P09g new-architecture score; no reviewer-label retraining was performed.
- Run-block bootstrap quantifies run-to-run support variation but not missing-detector-mode uncertainty.
- Raw `D_t`-tail rows are used as severe-review anchors, while most metrics are computed on the P09g held-out prediction rows.

## Follow-up

One novel follow-up is recorded in `result.json`: P09k real reviewer locked-label replacement.
