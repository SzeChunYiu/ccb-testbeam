# S06f: External Duplicate-Source Validation for Charge-Bin Conformal Timing Intervals

- **Ticket:** `1783656008.24866.43be308f`
- **Worker:** `testbeam-laptop-3`
- **Winner:** `traditional` at abstention budget `0.05`
- **Split:** leave-one-run-out and leave-one-target-pair-out conformal fitting over runs 58, 59, 60, 61, 62, 63, 65
- **Bootstrap:** run-block bootstrap, `400` replicates

## Abstract

S06e calibrated charge-bin timing intervals on pair residuals. S06f asks whether the same interval logic transfers to an independent duplicate-source timing target rather than only the residual panel used for calibration. This study uses the S06c frozen method panel but makes the conformal layer stricter: for each evaluated target pair and held-out run, the charge-bin scale is estimated from the other runs and the other two stave-pair endpoints. Thus, a B4-B6 interval is never calibrated on B4-B6 rows, and the evaluated run is also excluded.

The selected winner is **`traditional`**, with calibration loss `0.0786` (95% CI `0.0328`--`0.1691`), 68% coverage `0.7255`, 95% coverage `0.8872`, pull width `0.8697`, and accepted fraction `0.8945`.

## Raw ROOT Reproduction

Before using derived S06c rows, the S00/S01 selected-pulse gate is rerun from raw B-stack `h101/HRDv` ROOT files under `/home/billy/ccb-data/extracted/root/root`. The waveform tensor is reshaped to 8 channels by 18 samples; the channel pedestal is `median(samples 0..3)`; physical B-stave channels B2, B4, B6, and B8 are selected when the baseline-subtracted maximum exceeds 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimands and Equations

For event `e`, stave pair `p=(a,b)`, and method `m`, S06c provides a run-held-out time residual `r_{epm}=tau_{eam}-tau_{ebm}` and a predicted standard error `sigma_hat_{epm}`. S06e evaluated the pull `z_{epm}=r_{epm}/sigma_hat_{epm}` and fit charge-bin scale factors. S06f changes the calibration set for each held-out run `h` and target pair `p`:

`q_{b,m}^{(-h,-p)} = Quantile_0.682689({ |z_i| : run_i != h, pair_i != p, charge_bin_i=b, method_i=m })`.

The deployed interval is `sigma_prime_i = sigma_hat_i max(1, q_{b,m}^{(-h,-p)})`. Sparse charge bins with fewer than 30 calibration rows use the method-global scale from the same run/pair-excluded calibration pool. Optional abstention uses the training absolute-pull score cutoff for a 5% budget. Evaluation rows are never used to fit their own conformal factor or abstention threshold.

The primary loss is

`L = ( |C_68 - 0.682689| + |C_95 - 0.95| + |w_68(z) - 1| ) / 3`,

where `C_68=P(|z'|<=1)`, `C_95=P(|z'|<=1.96)`, and `w_68=(Q_0.84(z')-Q_0.16(z'))/2`.

## Pooled Benchmark

|   abstention_budget | method                    |     n |   accepted_fraction |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   coverage68 |   coverage68_ci_low |   coverage68_ci_high |   coverage95 |   pull_width68 |
|--------------------:|:--------------------------|------:|--------------------:|-------------------:|--------------------------:|---------------------------:|-------------:|--------------------:|---------------------:|-------------:|---------------:|
|                0    | phase_conformal_gated_cnn | 11460 |            1        |          0.0580421 |                 0.0400224 |                  0.0983528 |     0.691361 |            0.627359 |             0.751053 |     0.967277 |       0.851823 |
|                0    | cnn1d                     | 11460 |            1        |          0.0587635 |                 0.0480475 |                  0.124281  |     0.688482 |            0.575749 |             0.785784 |     0.964136 |       0.843638 |
|                0    | mlp                       | 11460 |            1        |          0.0656804 |                 0.0608714 |                  0.119778  |     0.682286 |            0.613107 |             0.751451 |     0.947208 |       0.806154 |
|                0    | gradient_boosted_trees    | 11460 |            1        |          0.0675132 |                 0.0531789 |                  0.144897  |     0.684991 |            0.57899  |             0.773444 |     0.936998 |       0.812764 |
|                0    | ridge                     | 11460 |            1        |          0.0817726 |                 0.076703  |                  0.162685  |     0.677225 |            0.558071 |             0.788927 |     0.946248 |       0.763899 |
|                0    | traditional               | 11460 |            1        |          0.13972   |                 0.0494859 |                  0.281083  |     0.648953 |            0.539144 |             0.73083  |     0.80288  |       1.2383   |
|                0.05 | traditional               | 10251 |            0.894503 |          0.0786108 |                 0.0328063 |                  0.16907   |     0.72549  |            0.60434  |             0.811608 |     0.887231 |       0.869738 |
|                0.05 | gradient_boosted_trees    | 10790 |            0.941536 |          0.115527  |                 0.0658378 |                  0.179399  |     0.727525 |            0.638794 |             0.806217 |     0.987303 |       0.735558 |
|                0.05 | mlp                       | 10827 |            0.944764 |          0.119962  |                 0.0897369 |                  0.165038  |     0.722176 |            0.657818 |             0.785807 |     0.993535 |       0.723134 |
|                0.05 | phase_conformal_gated_cnn | 10635 |            0.92801  |          0.120499  |                 0.089537  |                  0.15579   |     0.744993 |            0.672454 |             0.809542 |     1        |       0.750805 |
|                0.05 | cnn1d                     | 10588 |            0.923909 |          0.124958  |                 0.091262  |                  0.176587  |     0.745183 |            0.64927  |             0.841018 |     1        |       0.737619 |
|                0.05 | ridge                     | 10719 |            0.93534  |          0.136383  |                 0.109935  |                  0.198556  |     0.724041 |            0.616635 |             0.818391 |     0.997108 |       0.67931  |

## Run-Split Results

|   run | method                    |    n |   calibration_loss |   coverage68 |   coverage95 |   pull_width68 |   sigma68_ns |
|------:|:--------------------------|-----:|-------------------:|-------------:|-------------:|---------------:|-------------:|
|    58 | cnn1d                     |  205 |          0.0761043 |     0.682927 |     1        |       0.821924 |      1.36543 |
|    58 | gradient_boosted_trees    |  213 |          0.124205  |     0.694836 |     0.99061  |       0.680142 |      1.45427 |
|    58 | mlp                       |  207 |          0.137091  |     0.657005 |     0.995169 |       0.65958  |      1.56023 |
|    58 | phase_conformal_gated_cnn |  209 |          0.0801811 |     0.636364 |     1        |       0.855783 |      1.44125 |
|    58 | ridge                     |  206 |          0.133821  |     0.68932  |     1        |       0.655167 |      1.27949 |
|    58 | traditional               |  184 |          0.140205  |     0.777174 |     0.896739 |       0.72713  |      1.21101 |
|    59 | cnn1d                     | 2116 |          0.105303  |     0.706994 |     1        |       0.758395 |      1.41503 |
|    59 | gradient_boosted_trees    | 2208 |          0.103985  |     0.706522 |     0.983696 |       0.745574 |      1.38937 |
|    59 | mlp                       | 2175 |          0.121706  |     0.735172 |     0.991724 |       0.729088 |      1.46707 |
|    59 | phase_conformal_gated_cnn | 2098 |          0.113362  |     0.750715 |     1        |       0.77794  |      1.39985 |
|    59 | ridge                     | 2149 |          0.102316  |     0.672406 |     0.996743 |       0.750078 |      1.41123 |
|    59 | traditional               | 2066 |          0.168404  |     0.816554 |     0.93272  |       0.645933 |      1.5096  |
|    60 | cnn1d                     | 2261 |          0.193058  |     0.855816 |     1        |       0.643954 |      1.35758 |
|    60 | gradient_boosted_trees    | 2340 |          0.15936   |     0.778632 |     0.996154 |       0.664017 |      1.34374 |
|    60 | mlp                       | 2291 |          0.137556  |     0.737233 |     0.997818 |       0.689693 |      1.46124 |
|    60 | phase_conformal_gated_cnn | 2267 |          0.156628  |     0.788266 |     1        |       0.685693 |      1.28892 |
|    60 | ridge                     | 2331 |          0.17856   |     0.779923 |     0.998284 |       0.609836 |      1.34236 |
|    60 | traditional               | 2152 |          0.131365  |     0.774164 |     0.919145 |       0.728235 |      1.37208 |
|    61 | cnn1d                     | 2497 |          0.108659  |     0.569884 |     1        |       0.836827 |      1.79602 |
|    61 | gradient_boosted_trees    | 2426 |          0.0584432 |     0.570486 |     0.967436 |       0.95431  |      1.68082 |
|    61 | mlp                       | 2562 |          0.0902344 |     0.592896 |     0.986339 |       0.855429 |      1.73251 |
|    61 | phase_conformal_gated_cnn | 2621 |          0.101151  |     0.627242 |     1        |       0.801996 |      1.72765 |
|    61 | ridge                     | 2434 |          0.12929   |     0.54848  |     0.992605 |       0.788945 |      1.76686 |
|    61 | traditional               | 2510 |          0.217365  |     0.506773 |     0.760159 |       1.28634  |      2.20717 |
|    62 | cnn1d                     | 2279 |          0.171399  |     0.849934 |     1        |       0.703048 |      1.42917 |
|    62 | gradient_boosted_trees    | 2336 |          0.190155  |     0.825771 |     0.997432 |       0.620046 |      1.42839 |
|    62 | mlp                       | 2332 |          0.164262  |     0.798027 |     0.996998 |       0.669549 |      1.55917 |
|    62 | phase_conformal_gated_cnn | 2223 |          0.175863  |     0.849753 |     1        |       0.689473 |      1.39324 |
|    62 | ridge                     | 2341 |          0.217293  |     0.848355 |     0.999573 |       0.56336  |      1.44719 |
|    62 | traditional               | 2172 |          0.149743  |     0.787753 |     0.930939 |       0.674895 |      1.53548 |
|    63 | cnn1d                     | 1044 |          0.160188  |     0.788314 |     1        |       0.67506  |      1.30611 |
|    63 | gradient_boosted_trees    | 1076 |          0.172476  |     0.796468 |     0.997212 |       0.643562 |      1.39263 |
|    63 | mlp                       | 1072 |          0.189224  |     0.809701 |     0.998134 |       0.607473 |      1.4675  |
|    63 | phase_conformal_gated_cnn | 1024 |          0.104137  |     0.719727 |     1        |       0.774626 |      1.41234 |
|    63 | ridge                     | 1069 |          0.20345   |     0.837231 |     1        |       0.594193 |      1.36655 |
|    63 | traditional               |  991 |          0.171249  |     0.815338 |     0.936428 |       0.632474 |      1.40923 |
|    65 | cnn1d                     |  186 |          0.118093  |     0.731183 |     1        |       0.744213 |      1.39583 |
|    65 | gradient_boosted_trees    |  191 |          0.202231  |     0.78534  |     0.989529 |       0.535487 |      1.39238 |
|    65 | mlp                       |  188 |          0.171933  |     0.781915 |     0.989362 |       0.622787 |      1.5023  |
|    65 | phase_conformal_gated_cnn |  193 |          0.136524  |     0.818653 |     1        |       0.776391 |      1.50522 |
|    65 | ridge                     |  189 |          0.157756  |     0.740741 |     0.994709 |       0.629492 |      1.39987 |
|    65 | traditional               |  176 |          0.206846  |     0.852273 |     0.948864 |       0.550182 |      1.6006  |

## Duplicate Target-Pair Results

| target_pair   | method                    |    n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   coverage68 |   coverage95 |   pull_width68 |
|:--------------|:--------------------------|-----:|-------------------:|--------------------------:|---------------------------:|-------------:|-------------:|---------------:|
| B4-B6         | cnn1d                     | 3770 |           0.278033 |                 0.26966   |                   0.337189 |     0.705305 |     1        |       0.238515 |
| B4-B6         | gradient_boosted_trees    | 3706 |           0.207731 |                 0.184835  |                   0.288372 |     0.710739 |     0.976794 |       0.43165  |
| B4-B6         | mlp                       | 3742 |           0.218002 |                 0.199966  |                   0.277878 |     0.716996 |     0.989311 |       0.419613 |
| B4-B6         | phase_conformal_gated_cnn | 3779 |           0.291847 |                 0.273926  |                   0.334116 |     0.736174 |     1        |       0.227942 |
| B4-B6         | ridge                     | 3721 |           0.225871 |                 0.201925  |                   0.29534  |     0.729105 |     0.995969 |       0.414773 |
| B4-B6         | traditional               | 2665 |           0.125383 |                 0.115917  |                   0.1971   |     0.614634 |     0.888555 |       0.75335  |
| B4-B8         | cnn1d                     | 3747 |           0.291222 |                 0.267297  |                   0.326409 |     0.756872 |     1        |       0.250515 |
| B4-B8         | gradient_boosted_trees    | 3660 |           0.213632 |                 0.193181  |                   0.268249 |     0.71694  |     0.988251 |       0.431604 |
| B4-B8         | mlp                       | 3659 |           0.198075 |                 0.189604  |                   0.245624 |     0.698005 |     0.991801 |       0.462892 |
| B4-B8         | phase_conformal_gated_cnn | 3742 |           0.275433 |                 0.258548  |                   0.314957 |     0.733832 |     1        |       0.274845 |
| B4-B8         | ridge                     | 3668 |           0.1859   |                 0.17717   |                   0.241115 |     0.67121  |     0.995638 |       0.499416 |
| B4-B8         | traditional               | 3781 |           0.119895 |                 0.0603542 |                   0.252899 |     0.572071 |     0.78101  |       1.08008  |
| B6-B8         | cnn1d                     | 3071 |           0.143051 |                 0.129413  |                   0.158862 |     0.779876 |     1        |       0.718035 |
| B6-B8         | gradient_boosted_trees    | 3424 |           0.108527 |                 0.0839739 |                   0.121729 |     0.757009 |     0.997664 |       0.796401 |
| B6-B8         | mlp                       | 3426 |           0.10821  |                 0.0840974 |                   0.134441 |     0.753649 |     1        |       0.796328 |
| B6-B8         | phase_conformal_gated_cnn | 3114 |           0.14737  |                 0.119192  |                   0.163953 |     0.769107 |     1        |       0.694309 |
| B6-B8         | ridge                     | 3330 |           0.113755 |                 0.0925352 |                   0.152053 |     0.776577 |     1        |       0.802622 |
| B6-B8         | traditional               | 3805 |           0.319025 |                 0.292883  |                   0.345413 |     0.955585 |     0.991853 |       0.357672 |

## Conformal Leakage Checks

| check | value | pass |
|:--|:--|:--|
| raw_root_reproduction_passed | True | True |
| required_methods_present | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional | True |
| run_excluded_from_scale_fit | true by construction; ledger rows 1368 | true |
| target_pair_excluded_from_scale_fit | true by construction; target pairs B4-B6,B4-B8,B6-B8 | true |

## Systematics

- The duplicate-source endpoint is independent at the stave-pair level, not an external hardware clock. It is stronger than reusing the same pair residuals, but it still comes from the same HRD waveforms and same event population.
- Rows sharing one event are correlated because B4-B6, B4-B8, and B6-B8 residuals share staves. The bootstrap therefore resamples run blocks rather than pretending row independence.
- Charge-bin conformal scaling is marginal over each run/pair-excluded calibration pool. It does not guarantee conditional coverage for every morphology, saturation state, or current regime.
- The central timing estimates and method-specific `sigma_hat` values are inherited from S06c. S06f tests transfer of interval calibration, not a retraining of the original neural or traditional timing models.
- Sparse high-charge bins often fall back to a global scale. The ledger records this explicitly so apparent coverage in tails is not overinterpreted.

## Caveats

No independent absolute clock branch or tagged duplicate timing detector was found in the raw HRD schema used by this project. The operationally honest answer is therefore a duplicate-source validation: the target endpoint is a different downstream stave pair from the rows used to fit the conformal scale. A clean external-clock validation would still be a stronger promotion gate.

## Conclusion

Under run-held-out and target-pair-held-out duplicate-source conformal validation, traditional has the lowest calibration loss (0.0786, 95% CI [0.0328, 0.1691]) versus traditional 0.0786. The validation supports interval transfer across duplicate stave-pair endpoints, but not promotion to an absolute-clock calibration because no independent clock branch is present.
