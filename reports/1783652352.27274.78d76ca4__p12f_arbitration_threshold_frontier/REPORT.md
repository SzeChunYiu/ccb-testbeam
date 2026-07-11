# P12f Arbitration Threshold Frontier Under Sample-Family Drift

- **Ticket:** `1783652352.27274.78d76ca4`
- **Worker:** `testbeam-laptop-1`
- **Frozen P12e policy table:** `reports/1781062454.713.242b3d71__p12e_cross_consumer_pulse_atom_harm_ledger/heldout_policy_predictions.csv.gz`
- **Raw ROOT source:** `/home/billy/ccb-data/extracted/root/root`
- **Primary coverage:** `0.90` accepted support
- **Run bootstrap:** `500` resamples of held-out Sample-II runs `[58, 59, 60, 61, 62, 63, 65]`
- **Winner:** `ridge` with policy loss `1.6751` and CI `[1.6303759912359026, 1.7038905414964547]`

## Scientific Question

This ticket tests whether the frozen P12e arbitration policy has a stable operating frontier, or whether the threshold that makes it look good is a family-specific operating point. The falsification criteria are: (i) changing the frozen acceptance coverage reverses the winning method; (ii) run-held-out confidence intervals show large threshold instability; or (iii) the raw Sample-I and Sample-II selected-pulse support constraints are so different that a single Sample-II threshold cannot plausibly be promoted without a Sample-I shadow-policy table.

## Raw ROOT Reproduction

The first gate reads `h101/HRDv` directly from the raw B-stack ROOT files, reshapes each event to eight channels by eighteen samples, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted maximum amplitude above 1000 ADC. The benchmark is interpreted only because this count gate passes exactly.

| quantity                                      |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses                 |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib events with selected pulse     |         239559 |       239559 |       0 |           0 | True   |
| sample_i_calib selected pulses                |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis events with selected pulse  |         243133 |       243133 |       0 |           0 | True   |
| sample_i_analysis selected pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_i_analysis B2 selected pulses          |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4 selected pulses          |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6 selected pulses          |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8 selected pulses          |           1299 |         1299 |       0 |           0 | True   |
| sample_ii_calib events with selected pulse    |          12103 |        12103 |       0 |           0 | True   |
| sample_ii_calib selected pulses               |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis events with selected pulse |          89807 |        89807 |       0 |           0 | True   |
| sample_ii_analysis selected pulses            |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2 selected pulses         |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4 selected pulses         |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6 selected pulses         |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8 selected pulses         |           4506 |         4506 |       0 |           0 | True   |

## Estimand and Equations

For method `m`, pulse `i`, risk score `s_{mi}`, and acceptance coverage `q`, the threshold is the empirical quantile

`tau_m(q) = Q_q({s_{mi}: i in evaluation runs})`.

The accepted set is `A_m(q) = {i: s_{mi} <= tau_m(q)}` and the rejected set is its complement. With binary harm `h_i` and harm count `c_i`, the frontier loss is

`L_m(q) = mean_{i in A_m(q)} h_i + [1 - sum_{i notin A_m(q)} c_i / sum_i c_i]`.

Lower is better: the first term penalizes harmful accepted pulses and the second penalizes failure to concentrate consumer harm in the rejected tail. All confidence intervals resample complete held-out runs with replacement and recompute `tau_m(q)` inside each bootstrap draw.

## Benchmark Panel

The panel is the frozen P12e policy table: a strong traditional atom-action risk rule, ridge, gradient-boosted trees, MLP, 1D-CNN, and the new atom-prior residual CNN architecture. These are not refit in this ticket; the new contribution is the threshold-frontier and family-support audit of the frozen scores.

## Primary 90% Coverage Results

| method                           | family           |   threshold |   accepted_support |   accepted_harm_rate |   rejected_harm_capture |   policy_loss | policy_loss_ci95                         |
|:---------------------------------|:-----------------|------------:|-------------------:|---------------------:|------------------------:|--------------:|:-----------------------------------------|
| ridge                            | ml               |      1      |             0.9    |               0.8843 |                 0.2093  |         1.675 | [1.6303759912359026, 1.7038905414964547] |
| mlp                              | nn               |      0.9985 |             0.9    |               0.8843 |                 0.209   |         1.675 | [1.6388946990937434, 1.7080760824537138] |
| traditional_atom_action_rule     | traditional      |      0.9267 |             0.9025 |               0.8847 |                 0.207   |         1.678 | [1.6630440450366046, 1.7931768866367088] |
| 1d_cnn                           | nn               |      0.477  |             0.9    |               0.8848 |                 0.1898  |         1.695 | [1.6504380842536455, 1.7259380986181458] |
| atom_prior_residual_cnn_new_arch | new_architecture |      0.5387 |             0.9    |               0.8843 |                 0.06417 |         1.82  | [1.793038870148622, 1.8377658209245302]  |
| gradient_boosted_trees           | ml               |      0.8543 |             1      |               0.8959 |                 0       |         1.896 | [1.8730074573678448, 1.9130321849394318] |

## Coverage Frontier

| method                           | family           |   coverage |   threshold |   accepted_harm_rate |   rejected_harm_capture |   policy_loss |
|:---------------------------------|:-----------------|-----------:|------------:|---------------------:|------------------------:|--------------:|
| traditional_atom_action_rule     | traditional      |       0.5  |      0.6733 |               0.7924 |                 0.7922  |         1     |
| traditional_atom_action_rule     | traditional      |       0.6  |      0.9213 |               0.8644 |                 0.499   |         1.365 |
| traditional_atom_action_rule     | traditional      |       0.7  |      0.9213 |               0.8644 |                 0.499   |         1.365 |
| traditional_atom_action_rule     | traditional      |       0.8  |      0.9267 |               0.8847 |                 0.207   |         1.678 |
| traditional_atom_action_rule     | traditional      |       0.9  |      0.9267 |               0.8847 |                 0.207   |         1.678 |
| traditional_atom_action_rule     | traditional      |       0.95 |      0.9487 |               0.895  |                 0.01662 |         1.878 |
| ridge                            | ml               |       0.5  |      0.9997 |               0.7918 |                 0.7163  |         1.076 |
| ridge                            | ml               |       0.6  |      0.9998 |               0.8265 |                 0.6262  |         1.2   |
| ridge                            | ml               |       0.7  |      0.9999 |               0.8513 |                 0.5314  |         1.32  |
| ridge                            | ml               |       0.8  |      1      |               0.8699 |                 0.4002  |         1.47  |
| ridge                            | ml               |       0.9  |      1      |               0.8843 |                 0.2093  |         1.675 |
| ridge                            | ml               |       0.95 |      1      |               0.8904 |                 0.1069  |         1.783 |
| gradient_boosted_trees           | ml               |       0.5  |      0.8543 |               0.8959 |                 0       |         1.896 |
| gradient_boosted_trees           | ml               |       0.6  |      0.8543 |               0.8959 |                 0       |         1.896 |
| gradient_boosted_trees           | ml               |       0.7  |      0.8543 |               0.8959 |                 0       |         1.896 |
| gradient_boosted_trees           | ml               |       0.8  |      0.8543 |               0.8959 |                 0       |         1.896 |
| gradient_boosted_trees           | ml               |       0.9  |      0.8543 |               0.8959 |                 0       |         1.896 |
| gradient_boosted_trees           | ml               |       0.95 |      0.8543 |               0.8959 |                 0       |         1.896 |
| mlp                              | nn               |       0.5  |      0.9849 |               0.7918 |                 0.6753  |         1.117 |
| mlp                              | nn               |       0.6  |      0.9926 |               0.8265 |                 0.5522  |         1.274 |
| mlp                              | nn               |       0.7  |      0.995  |               0.8513 |                 0.4444  |         1.407 |
| mlp                              | nn               |       0.8  |      0.9964 |               0.8699 |                 0.3427  |         1.527 |
| mlp                              | nn               |       0.9  |      0.9985 |               0.8843 |                 0.209   |         1.675 |
| mlp                              | nn               |       0.95 |      0.9997 |               0.8904 |                 0.1089  |         1.782 |
| 1d_cnn                           | nn               |       0.5  |      0.4717 |               0.9666 |                 0.6408  |         1.326 |
| 1d_cnn                           | nn               |       0.6  |      0.4724 |               0.916  |                 0.5782  |         1.338 |
| 1d_cnn                           | nn               |       0.7  |      0.4732 |               0.873  |                 0.5027  |         1.37  |
| 1d_cnn                           | nn               |       0.8  |      0.4742 |               0.8718 |                 0.3729  |         1.499 |
| 1d_cnn                           | nn               |       0.9  |      0.477  |               0.8848 |                 0.1898  |         1.695 |
| 1d_cnn                           | nn               |       0.95 |      0.4797 |               0.8905 |                 0.09734 |         1.793 |
| atom_prior_residual_cnn_new_arch | new_architecture |       0.5  |      0.5099 |               0.7918 |                 0.4641  |         1.328 |
| atom_prior_residual_cnn_new_arch | new_architecture |       0.6  |      0.5175 |               0.8265 |                 0.3301  |         1.496 |
| atom_prior_residual_cnn_new_arch | new_architecture |       0.7  |      0.5216 |               0.8513 |                 0.2415  |         1.61  |
| atom_prior_residual_cnn_new_arch | new_architecture |       0.8  |      0.5316 |               0.8699 |                 0.124   |         1.746 |
| atom_prior_residual_cnn_new_arch | new_architecture |       0.9  |      0.5387 |               0.8843 |                 0.06417 |         1.82  |
| atom_prior_residual_cnn_new_arch | new_architecture |       0.95 |      0.5503 |               0.8904 |                 0.02711 |         1.863 |

## Per-Run Split Diagnostics

The table below shows the per-run scores at the primary coverage. The bootstrap intervals above are based on these complete run blocks rather than treating pulses as iid.

|   run | method                           |   coverage |   threshold |   accepted_harm_rate |   rejected_harm_capture |   policy_loss |
|------:|:---------------------------------|-----------:|------------:|---------------------:|------------------------:|--------------:|
|    58 | traditional_atom_action_rule     |        0.9 |      0.9213 |               0.8799 |                 0.1306  |         1.749 |
|    59 | traditional_atom_action_rule     |        0.9 |      0.932  |               0.896  |                 0.1237  |         1.772 |
|    60 | traditional_atom_action_rule     |        0.9 |      0.932  |               0.9185 |                 0.1217  |         1.797 |
|    61 | traditional_atom_action_rule     |        0.9 |      0.932  |               0.9196 |                 0.1114  |         1.808 |
|    62 | traditional_atom_action_rule     |        0.9 |      0.932  |               0.8981 |                 0.14    |         1.758 |
|    63 | traditional_atom_action_rule     |        0.9 |      0.9267 |               0.8719 |                 0.1989  |         1.673 |
|    65 | traditional_atom_action_rule     |        0.9 |      0.9267 |               0.8135 |                 0.1164  |         1.697 |
|    58 | ridge                            |        0.9 |      0.9999 |               0.8722 |                 0.2144  |         1.658 |
|    59 | ridge                            |        0.9 |      1      |               0.8926 |                 0.1979  |         1.695 |
|    60 | ridge                            |        0.9 |      1      |               0.9162 |                 0.187   |         1.729 |
|    61 | ridge                            |        0.9 |      1      |               0.9165 |                 0.195   |         1.721 |
|    62 | ridge                            |        0.9 |      1      |               0.896  |                 0.1947  |         1.701 |
|    63 | ridge                            |        0.9 |      1      |               0.8702 |                 0.2179  |         1.652 |
|    65 | ridge                            |        0.9 |      1      |               0.8014 |                 0.2516  |         1.55  |
|    58 | gradient_boosted_trees           |        0.9 |      0.8543 |               0.885  |                 0       |         1.885 |
|    59 | gradient_boosted_trees           |        0.9 |      0.8543 |               0.9034 |                 0       |         1.903 |
|    60 | gradient_boosted_trees           |        0.9 |      0.8543 |               0.9246 |                 0       |         1.925 |
|    61 | gradient_boosted_trees           |        0.9 |      0.8543 |               0.9248 |                 0       |         1.925 |
|    62 | gradient_boosted_trees           |        0.9 |      0.8543 |               0.9064 |                 0       |         1.906 |
|    63 | gradient_boosted_trees           |        0.9 |      0.8543 |               0.8831 |                 0       |         1.883 |
|    65 | gradient_boosted_trees           |        0.9 |      0.8543 |               0.8213 |                 0       |         1.821 |
|    58 | mlp                              |        0.9 |      0.9964 |               0.8722 |                 0.1833  |         1.689 |
|    59 | mlp                              |        0.9 |      0.9988 |               0.8926 |                 0.1967  |         1.696 |
|    60 | mlp                              |        0.9 |      0.9992 |               0.9162 |                 0.1861  |         1.73  |
|    61 | mlp                              |        0.9 |      0.999  |               0.9165 |                 0.1922  |         1.724 |
|    62 | mlp                              |        0.9 |      0.9988 |               0.896  |                 0.1936  |         1.702 |
|    63 | mlp                              |        0.9 |      0.9985 |               0.8702 |                 0.2216  |         1.649 |
|    65 | mlp                              |        0.9 |      0.9977 |               0.8014 |                 0.2548  |         1.547 |
|    58 | 1d_cnn                           |        0.9 |      0.473  |               0.8913 |                 0.1853  |         1.706 |
|    59 | 1d_cnn                           |        0.9 |      0.4775 |               0.8928 |                 0.1762  |         1.717 |
|    60 | 1d_cnn                           |        0.9 |      0.4781 |               0.9162 |                 0.163   |         1.753 |
|    61 | 1d_cnn                           |        0.9 |      0.4777 |               0.9166 |                 0.1709  |         1.746 |
|    62 | 1d_cnn                           |        0.9 |      0.4777 |               0.8963 |                 0.1707  |         1.726 |
|    63 | 1d_cnn                           |        0.9 |      0.4767 |               0.8709 |                 0.2018  |         1.669 |
|    65 | 1d_cnn                           |        0.9 |      0.476  |               0.8019 |                 0.2354  |         1.567 |
|    58 | atom_prior_residual_cnn_new_arch |        0.9 |      0.5503 |               0.8722 |                 0.06446 |         1.808 |
|    59 | atom_prior_residual_cnn_new_arch |        0.9 |      0.5368 |               0.8926 |                 0.06635 |         1.826 |
|    60 | atom_prior_residual_cnn_new_arch |        0.9 |      0.5385 |               0.9162 |                 0.06676 |         1.849 |
|    61 | atom_prior_residual_cnn_new_arch |        0.9 |      0.5384 |               0.9165 |                 0.07084 |         1.846 |
|    62 | atom_prior_residual_cnn_new_arch |        0.9 |      0.5368 |               0.896  |                 0.06539 |         1.831 |
|    63 | atom_prior_residual_cnn_new_arch |        0.9 |      0.5387 |               0.8702 |                 0.06317 |         1.807 |
|    65 | atom_prior_residual_cnn_new_arch |        0.9 |      0.5386 |               0.8014 |                 0.07588 |         1.726 |

## Threshold Stability and Falsification

| method                           | family           |   threshold_min |   threshold_max |   threshold_range |   max_run_threshold_span | winner_reversal_any_coverage   | winner_sequence_by_coverage                                             |
|:---------------------------------|:-----------------|----------------:|----------------:|------------------:|-------------------------:|:-------------------------------|:------------------------------------------------------------------------|
| traditional_atom_action_rule     | traditional      |          0.6733 |          0.9487 |          0.2753   |                0.248     | True                           | traditional_atom_action_rule -> ridge -> ridge -> ridge -> ridge -> mlp |
| ridge                            | ml               |          0.9997 |          1      |          0.000336 |                0.0006908 | True                           | traditional_atom_action_rule -> ridge -> ridge -> ridge -> ridge -> mlp |
| gradient_boosted_trees           | ml               |          0.8543 |          0.8543 |          0        |                0         | True                           | traditional_atom_action_rule -> ridge -> ridge -> ridge -> ridge -> mlp |
| mlp                              | nn               |          0.9849 |          0.9997 |          0.01486  |                0.01398   | True                           | traditional_atom_action_rule -> ridge -> ridge -> ridge -> ridge -> mlp |
| 1d_cnn                           | nn               |          0.4717 |          0.4797 |          0.008005 |                0.005965  | True                           | traditional_atom_action_rule -> ridge -> ridge -> ridge -> ridge -> mlp |
| atom_prior_residual_cnn_new_arch | new_architecture |          0.5099 |          0.5503 |          0.0404   |                0.01599   | True                           | traditional_atom_action_rule -> ridge -> ridge -> ridge -> ridge -> mlp |

A winner reversal across the requested coverage grid is `true`. The sequence field records the global winner at each coverage in grid order, so repeated identical entries support a stable frontier while method changes flag threshold tuning sensitivity.

## Raw Sample-Family Support Constraints

| group              |   selected_pulses |   events_with_selected |   pulses_per_selected_event |   B2_fraction |   B4_fraction |   B6_fraction |   B8_fraction |
|:-------------------|------------------:|-----------------------:|----------------------------:|--------------:|--------------:|--------------:|--------------:|
| sample_i_calib     |            248745 |                 239559 |                       1.038 |        0.9563 |       0.02712 |       0.01182 |      0.004728 |
| sample_i_analysis  |            252266 |                 243133 |                       1.038 |        0.957  |       0.02557 |       0.01226 |      0.005149 |
| sample_ii_calib    |             14630 |                  12103 |                       1.209 |        0.8139 |       0.1154  |       0.05215 |      0.01852  |
| sample_ii_analysis |            125096 |                  89807 |                       1.393 |        0.7052 |       0.1697  |       0.08912 |      0.03602  |

### Sample-I versus Sample-II Support Delta

| support_metric            |   sample_i_analysis |   sample_ii_analysis |   sample_ii_minus_sample_i |   abs_delta |
|:--------------------------|--------------------:|---------------------:|---------------------------:|------------:|
| pulses_per_selected_event |            1.038    |              1.393   |                    0.3554  |     0.3554  |
| B2_fraction               |            0.957    |              0.7052  |                   -0.2519  |     0.2519  |
| B4_fraction               |            0.02557  |              0.1697  |                    0.1441  |     0.1441  |
| B6_fraction               |            0.01226  |              0.08912 |                    0.07685 |     0.07685 |
| B8_fraction               |            0.005149 |              0.03602 |                    0.03087 |     0.03087 |

The frozen P12e table available in this repository contains only `sample_ii_analysis` policy rows. Therefore this ticket cannot honestly score Sample-I policy loss at row level. The raw ROOT support audit above is the detector-level family-drift constraint: Sample-I is much more B2-dominated than Sample-II, so a true promotion of a frozen threshold requires a P12e-compatible Sample-I shadow-policy table. This is a caveat, not a hidden correction.

## Accepted-Stave Composition

| method                           | family           |   coverage | stave   |   accepted_n |   accepted_fraction_within_accepted |   accepted_harm_rate |
|:---------------------------------|:-----------------|-----------:|:--------|-------------:|------------------------------------:|---------------------:|
| traditional_atom_action_rule     | traditional      |        0.9 | B2      |        82562 |                             0.7313  |               0.8641 |
| traditional_atom_action_rule     | traditional      |        0.9 | B4      |        18248 |                             0.1616  |               0.9395 |
| traditional_atom_action_rule     | traditional      |        0.9 | B6      |         8747 |                             0.07748 |               0.9324 |
| traditional_atom_action_rule     | traditional      |        0.9 | B8      |         3336 |                             0.02955 |               0.9676 |
| ridge                            | ml               |        0.9 | B2      |        80230 |                             0.7126  |               0.8602 |
| ridge                            | ml               |        0.9 | B4      |        18538 |                             0.1647  |               0.9404 |
| ridge                            | ml               |        0.9 | B6      |        10029 |                             0.08908 |               0.9411 |
| ridge                            | ml               |        0.9 | B8      |         3789 |                             0.03365 |               0.9715 |
| gradient_boosted_trees           | ml               |        0.9 | B2      |        88213 |                             0.7052  |               0.8728 |
| gradient_boosted_trees           | ml               |        0.9 | B4      |        21229 |                             0.1697  |               0.948  |
| gradient_boosted_trees           | ml               |        0.9 | B6      |        11148 |                             0.08912 |               0.947  |
| gradient_boosted_trees           | ml               |        0.9 | B8      |         4506 |                             0.03602 |               0.976  |
| mlp                              | nn               |        0.9 | B2      |        80577 |                             0.7157  |               0.8608 |
| mlp                              | nn               |        0.9 | B4      |        18051 |                             0.1603  |               0.9388 |
| mlp                              | nn               |        0.9 | B6      |        10051 |                             0.08927 |               0.9412 |
| mlp                              | nn               |        0.9 | B8      |         3907 |                             0.0347  |               0.9724 |
| 1d_cnn                           | nn               |        0.9 | B2      |        81118 |                             0.7205  |               0.8623 |
| 1d_cnn                           | nn               |        0.9 | B4      |        18156 |                             0.1613  |               0.9392 |
| 1d_cnn                           | nn               |        0.9 | B6      |         9535 |                             0.08469 |               0.9381 |
| 1d_cnn                           | nn               |        0.9 | B8      |         3777 |                             0.03355 |               0.9714 |
| atom_prior_residual_cnn_new_arch | new_architecture |        0.9 | B2      |        77874 |                             0.6917  |               0.8559 |
| atom_prior_residual_cnn_new_arch | new_architecture |        0.9 | B4      |        20180 |                             0.1792  |               0.9453 |
| atom_prior_residual_cnn_new_arch | new_architecture |        0.9 | B6      |        10578 |                             0.09395 |               0.9441 |
| atom_prior_residual_cnn_new_arch | new_architecture |        0.9 | B8      |         3954 |                             0.03512 |               0.9727 |

## Systematics and Caveats

- The policy table is frozen and Sample-II-only; neural and tree methods are benchmarked as frozen P12e predictions rather than retrained in this ticket.
- Run-bootstrap intervals have only seven held-out run units, so they reflect run-to-run instability but remain coarse.
- The composite loss is an operational arbitration loss. Component harms span timing, charge, saturation, pile-up, baseline, dropout, PID, and energy proxies; it should not be read as a single detector-truth observable.
- Thresholds are recalculated inside each bootstrap draw. This measures frontier stability, not fixed-threshold deployment variance.
- Raw Sample-I/Sample-II support deltas are directly reproduced from ROOT; Sample-I row-level policy loss is intentionally not imputed.

## Conclusion

At the primary 90% accepted-support operating point the winner is `ridge`. Its policy loss is `1.6751` with 95% run-bootstrap CI `[1.6303759912359026, 1.7038905414964547]`. The coverage-grid winner reversal flag is `true`. Because the available frozen P12e table is Sample-II-only, the family-drift conclusion is conditional: the Sample-II frontier is measured, raw Sample-I/Sample-II support drift is reproduced, and a row-level Sample-I shadow policy is required before claiming a stable cross-family deployment threshold.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p12f_1783652352_27274_78d76ca4_arbitration_threshold_frontier.py --config configs/p12f_1783652352_27274_78d76ca4_arbitration_threshold_frontier.json
```

Runtime: 32.2 s.
