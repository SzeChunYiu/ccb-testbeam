# S16m: Support-Preserving Pedestal-Imputation Timing Correction

## Abstract

This study tests whether the S16l target-excluded pedestal-imputation signal can be useful as a nuisance covariate for timing correction without replacing the physical waveform support used by the timing estimator. The raw ROOT selection reproduces the registered selected B-stave pulse count exactly. On leave-one-run-out Sample-II downstream-pair timing, the winning correction by the pre-registered rule is **gradient_boosted_trees**.

## Data Reproduction

Raw `h101/HRDv` waveforms were read from `data/root/root`. The same B-stave channel map, four-sample median pedestal seed, and amplitude threshold used in S16l were applied. The reproduction gate is exact equality with the registered counts.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimand

For a downstream pair `(a,b)` in the same event, the uncorrected support-preserving residual is

`r_i = (t_i,a(CFD20) - t_i,b(CFD20)) - (x_a - x_b) tau`,

where the CFD20 time is the CFD crossing from the original four-sample median baseline, `x` is the B-stack position, and `tau=0.078` ns/cm. A model estimates `c_i = E[r_i | z_i]`; the corrected residual is `r_i - c_i`. No model recomputes a pedestal, waveform, amplitude, or CFD crossing from imputed samples.

## Nuisance Construction

For each pulse and each pretrigger sample `j in {0,1,2,3}`, the S16l target-excluded predictors `mean3`, `median3`, and `line3` were computed from the other three pretrigger samples only. Their discrepancies from the observed target sample were aggregated to pulse-level nuisance summaries: signed mean discrepancy, mean absolute discrepancy, maximum absolute discrepancy, model spread, target-sample standard deviation, and visible three-sample range. These quantities enter the correction feature vector only; they are not used as replacement baseline values.

## Models and Split

All comparisons use leave-one-run-out Sample-II analysis splitting over runs `[58, 59, 60, 61, 62, 63, 65]`. The traditional method is a hierarchical binned median correction over pair identity, amplitude-ratio bin, pretrigger-dispersion bin, and nuisance-magnitude bin, with fallbacks to coarser cells and a global median. ML/NN comparators are ridge regression, histogram gradient-boosted trees, MLP, a 1D pair CNN over baseline-subtracted raw waveform pairs, and a new nuisance-gated pair CNN whose convolutional representation is multiplicatively gated by nuisance features.

## Primary Results

Bootstrap intervals resample held-out runs with replacement, preserving the paired method comparison structure within each sampled run.

| method                    |   n_pairs |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_abs_gt_0p5_ns |   tail_abs_gt_0p5_ns_ci_low |   tail_abs_gt_0p5_ns_ci_high |     bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |   delta_sigma68_vs_uncorrected_ns_ci_low |   delta_sigma68_vs_uncorrected_ns_ci_high |
|:--------------------------|----------:|-------------:|--------------------:|---------------------:|---------------------:|----------------------------:|-----------------------------:|------------:|-----------------:|------------------:|-----------------------------------------:|------------------------------------------:|
| uncorrected               |     18098 |      2.94278 |             2.84362 |              3.03585 |             0.922643 |                    0.916234 |                     0.929351 | -3.41237    |       -3.52494   |         -3.2947   |                                 0        |                                  0        |
| traditional_binned_median |     18098 |      1.37559 |             1.33416 |              1.41862 |             0.711736 |                    0.701645 |                     0.720871 | -0.432081   |       -0.574614  |         -0.287464 |                                -1.66644  |                                 -1.45036  |
| ridge                     |     18098 |      2.38943 |             2.27542 |              2.54481 |             0.825671 |                    0.813035 |                     0.840863 | -0.02145    |       -0.242928  |          0.292462 |                                -0.730504 |                                 -0.318042 |
| gradient_boosted_trees    |     18098 |      1.2196  |             1.18813 |              1.25881 |             0.663278 |                    0.65753  |                     0.670842 | -0.00836533 |       -0.0938329 |          0.157423 |                                -1.81833  |                                 -1.60464  |
| mlp                       |     18098 |      1.25432 |             1.20275 |              1.33787 |             0.667311 |                    0.656789 |                     0.683603 | -0.0432521  |       -0.158222  |          0.163143 |                                -1.81166  |                                 -1.51757  |
| one_dimensional_cnn       |     18098 |      1.3892  |             1.36043 |              1.4183  |             0.699525 |                    0.695949 |                     0.706399 | -0.255053   |       -0.33318   |         -0.152889 |                                -1.65035  |                                 -1.43575  |
| nuisance_gated_pair_cnn   |     18098 |      1.38769 |             1.35585 |              1.4278  |             0.700354 |                    0.686885 |                     0.714598 | -0.337564   |       -0.438109  |         -0.196922 |                                -1.65395  |                                 -1.46097  |

## Per-Run Stability

| method                    |   run |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |    bias_ns |
|:--------------------------|------:|----------:|-------------:|---------------------:|-----------:|
| gradient_boosted_trees    |    58 |       353 |      1.42739 |             0.696884 |  1.4536    |
| gradient_boosted_trees    |    59 |      3753 |      1.15171 |             0.651745 | -0.119666  |
| gradient_boosted_trees    |    60 |      3700 |      1.22157 |             0.658919 |  0.0617691 |
| gradient_boosted_trees    |    61 |      4245 |      1.20344 |             0.664547 |  0.019848  |
| gradient_boosted_trees    |    62 |      3833 |      1.21347 |             0.666058 | -0.0166363 |
| gradient_boosted_trees    |    63 |      1816 |      1.2453  |             0.672357 | -0.276852  |
| gradient_boosted_trees    |    65 |       398 |      1.43355 |             0.701005 |  0.0962819 |
| mlp                       |    58 |       353 |      1.58144 |             0.688385 |  1.62026   |
| mlp                       |    59 |      3753 |      1.20694 |             0.660272 | -0.248033  |
| mlp                       |    60 |      3700 |      1.21824 |             0.652162 | -0.0887003 |
| mlp                       |    61 |      4245 |      1.33915 |             0.693522 | -0.0384159 |
| mlp                       |    62 |      3833 |      1.17926 |             0.659536 |  0.0790434 |
| mlp                       |    63 |      1816 |      1.26348 |             0.656938 | -0.222018  |
| mlp                       |    65 |       398 |      1.58352 |             0.698492 |  0.421155  |
| nuisance_gated_pair_cnn   |    58 |       353 |      1.50431 |             0.694051 |  0.616125  |
| nuisance_gated_pair_cnn   |    59 |      3753 |      1.4407  |             0.719957 | -0.355372  |
| nuisance_gated_pair_cnn   |    60 |      3700 |      1.34031 |             0.700541 | -0.547185  |
| nuisance_gated_pair_cnn   |    61 |      4245 |      1.34571 |             0.677739 | -0.361026  |
| nuisance_gated_pair_cnn   |    62 |      3833 |      1.37369 |             0.697365 | -0.177011  |
| nuisance_gated_pair_cnn   |    63 |      1816 |      1.37595 |             0.714207 | -0.477392  |
| nuisance_gated_pair_cnn   |    65 |       398 |      1.55571 |             0.726131 |  0.275239  |
| one_dimensional_cnn       |    58 |       353 |      1.40614 |             0.70255  |  0.39999   |
| one_dimensional_cnn       |    59 |      3753 |      1.34171 |             0.694911 | -0.249098  |
| one_dimensional_cnn       |    60 |      3700 |      1.34822 |             0.708108 | -0.193944  |
| one_dimensional_cnn       |    61 |      4245 |      1.41124 |             0.695406 | -0.383552  |
| one_dimensional_cnn       |    62 |      3833 |      1.38649 |             0.696061 | -0.192284  |
| one_dimensional_cnn       |    63 |      1816 |      1.40206 |             0.698789 | -0.412962  |
| one_dimensional_cnn       |    65 |       398 |      1.51844 |             0.741206 |  0.0262885 |
| ridge                     |    58 |       353 |      3.1825  |             0.889518 |  1.91437   |
| ridge                     |    59 |      3753 |      2.16223 |             0.800426 | -0.0804912 |
| ridge                     |    60 |      3700 |      2.42993 |             0.834324 |  0.154298  |
| ridge                     |    61 |      4245 |      2.50247 |             0.840518 | -0.404926  |
| ridge                     |    62 |      3833 |      2.31    |             0.819463 |  0.192255  |
| ridge                     |    63 |      1816 |      2.29672 |             0.819934 | -0.343612  |
| ridge                     |    65 |       398 |      2.86901 |             0.854271 |  0.686437  |
| traditional_binned_median |    58 |       353 |      1.36738 |             0.728045 |  0.160654  |
| traditional_binned_median |    59 |      3753 |      1.30787 |             0.69118  | -0.476196  |
| traditional_binned_median |    60 |      3700 |      1.3506  |             0.714054 | -0.633723  |
| traditional_binned_median |    61 |      4245 |      1.36062 |             0.713545 | -0.267556  |
| traditional_binned_median |    62 |      3833 |      1.36109 |             0.717715 | -0.31894   |
| traditional_binned_median |    63 |      1816 |      1.43483 |             0.720264 | -0.733298  |
| traditional_binned_median |    65 |       398 |      1.62291 |             0.753769 | -0.137272  |
| uncorrected               |    58 |       353 |      2.8642  |             0.923513 | -2.85184   |
| uncorrected               |    59 |      3753 |      2.95704 |             0.928324 | -3.47279   |
| uncorrected               |    60 |      3700 |      2.96349 |             0.917027 | -3.51308   |
| uncorrected               |    61 |      4245 |      2.7526  |             0.912603 | -3.26935   |
| uncorrected               |    62 |      3833 |      3.00859 |             0.926689 | -3.32187   |
| uncorrected               |    63 |      1816 |      3.18528 |             0.932269 | -3.71769   |
| uncorrected               |    65 |       398 |      2.58048 |             0.944724 | -3.40749   |

## Systematics and Caveats

The split-by-run design guards against event-level leakage and tests whether corrections transport across acquisition periods. The remaining systematic limitations are: (1) run bootstrap intervals have only seven independent run units and should be read as operational uncertainty rather than asymptotic confidence intervals; (2) the correction target is pairwise residual symmetry rather than an external timing truth; (3) waveform CNNs use the original median-baseline support and therefore test timing correction capacity, not a new CFD definition; (4) nuisance features are derived from observed pretrigger samples, so their value is diagnostic of contamination but not evidence that imputed pedestal substitution is safe; and (5) hyperparameters are deliberately modest to keep the ROOT-to-report pipeline reproducible on the worker.

## Conclusion

The support-preserving benchmark separates pedestal-contamination diagnosis from unsafe baseline substitution. The named winner in `result.json` is `gradient_boosted_trees`, selected by lowest held-out `sigma68_ns` among correction methods with the registered tie breakers.
