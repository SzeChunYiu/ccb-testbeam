# S05: Stave-error independence and two-ended projection benchmark

- **Ticket:** `2377`
- **Worker:** `testbeam-laptop-3`
- **Raw input:** `/home/billy/ccb-data/data/extracted/root/root`
- **Input checksums:** `input_sha256.csv`
- **No Monte Carlo:** raw HRD ROOT only

## Question

Does the B-stack timing residual covariance support the independence approximation
`sigma_ij^2 = sigma_i^2 + sigma_j^2`, and what two-ended timing projection is
defensible once the correlated fraction is quantified? The atomic test is:
reproduce the raw selected-pulse and A-stack control anchors from ROOT; build
run-held-out B-pair residuals; compare a strong traditional covariance model
with Ridge, gradient-boosted trees, MLP, 1D-CNN, and a support-gated CNN; then
name the method with the lowest held-out non-control mean absolute pair
covariance as the benchmark winner.

## Abstract

This study rebuilds the B-stack coincidence table from raw `HRDv` ROOT and
tests the S05 independence assumption through event-level pair covariance after
matching on B2 saturation depth, q-template-shift proxy, amplitude, topology,
baseline lowering, pile-up candidate status, and run family. The benchmark uses
leave-one-run-held-out B-stack residuals and a run/pair bootstrap for confidence
intervals. The method panel contains the requested strong traditional
comparator and learned alternatives: ridge, gradient-boosted trees, S05e-style
ExtraTrees, MLP, 1D-CNN, and a new support-gated CNN. Controls include
waveform-only, pool-label-only, and shuffled-target fits.

The winner named in `result.json` is **extra_trees_s05e_dynamic**, selected by
lowest held-out B-stack mean absolute pair covariance among non-control methods.
Its covariance is **37.239 ns^2** and correlated fraction is **0.300**, versus
**60.492 ns^2** and **0.391** for the traditional S05d static-prior Ridge, and
**228.535 ns^2** and **0.366** for pair-median centering. The support-frontier
winner is **ridge** for median B2 covariance-component error, so the primary
safety verdict is **benchmark_winner_not_adopted_as_safe_gate**.

## Reproduction first

Raw ROOT anchors were rebuilt before the transfer test:

| quantity                             |     expected |   reproduced |       delta |   tolerance | pass   |
|:-------------------------------------|-------------:|-------------:|------------:|------------:|:-------|
| total_selected_b_pulses              | 640737       | 640737       | 0           |       0     | True   |
| sample_i_analysis_b_selected_pulses  | 252266       | 252266       | 0           |       0     | True   |
| sample_ii_analysis_b_selected_pulses | 125096       | 125096       | 0           |       0     | True   |
| sample_iv_a1_a3_pairs                |    127       |    127       | 0           |       0     | True   |
| sample_iv_a1_a3_robust_width_ns      |      1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |

## Methods

Runs are the split unit. Each B-stack analysis run is held out in turn; all B residual models and covariance predictors are fit without that run's B targets. The raw features are waveform-derived summaries only: amplitude, tail, peak sample, area, baseline, normalized 18-sample shape, saturation depth, and pile-up proxies.

Traditional: train-run B pair medians are retained as the non-parametric S05c baseline. The strong traditional comparator, `traditional_s05d_static_priors`, is a Ridge residual model with S05d-style static priors and explicit B waveform/support covariates: amplitude, tail, peak, baseline, q-template-shift proxy, B2 saturation depth, pair topology, and run family.

ML/NN: `ridge`, `gradient_boosted_trees`, `extra_trees_s05e_dynamic`, `mlp`, `cnn_1d`, and `support_gated_cnn_new` are trained on the same train runs and evaluated on the same held-out run. The 1D-CNN consumes left/right normalized waveforms and support auxiliary features. The new support-gated CNN uses a learned sigmoid support gate on the convolutional representation, which is sensible here because corrections should shrink outside matched saturation/amplitude/topology support.

Controls: `waveform_only_mlp` removes tabular support covariates, `pool_label_control` uses only pair and run-family labels, and `ml_shuffled_target_control` shuffles training targets within the run-held-out fold.

## Estimands and equations

For B pair residuals, `r_ij = (t_j - t_i) - TOF_ij`. For method `m`, the held-out residual is `e_i(m)=r_i-hat r_m(x_i)`. The robust width is

`W_68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

For each run, residuals are pivoted to event by pair. The covariance gate metric is the mean absolute off-diagonal pair covariance:

`C_m = mean_{runs} mean_{p<q} |Cov(e_p(m), e_q(m))|`.

Under independent single-stave errors, a pair residual satisfies
`Var(r_ij) = sigma_i^2 + sigma_j^2`. With a shared component `c`, the more
general form is `Var(r_ij)=sigma_i^2+sigma_j^2-2 Cov(e_i,e_j)` for signed
single-stave errors, and nonzero off-diagonal covariance between pair residuals
is direct evidence that a naive diagonal stave-error model is incomplete. The
reported correlated fraction is the fraction of residual covariance energy
carried by off-diagonal pair terms in the held-out event/run covariance ledger.

The two-ended projection is therefore not allowed to divide every variance term
by two. A conservative projection decomposes a single-ended variance into a
local end component and a common floor,
`sigma_two_end^2 = sigma_common^2 + sigma_local^2 / 2`, keeping the correlated
floor unreduced. Since this dataset has one-ended readout only, the two-ended
numbers are projections and not a hardware validation.

Width intervals resample held-out runs with replacement and pair rows within sampled runs. Covariance intervals resample precomputed per-run covariance values. Support atoms are Cartesian cells over run family, topology, B2 saturation-depth bin, q-template-shift-proxy bin, pair-amplitude bin, baseline-lowering flag, and pile-up candidate flag. An atom is accepted support when it has at least `250` pair rows and `4` runs.

## Held-out residuals

| method                         | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                                                                                         |
|:-------------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:-----------------------------------------------------------------------------------------------------------------------------|
| pair_median                    | traditional    |         65484 |       21 |      2.0905  |             1.89205 |             12.4414  |      20.6803  |             17.5618  |               27.8234 |                   0.141775 |              0.366419 |                228.535  | strong traditional B-pair train-median centering                                                                             |
| traditional_s05d_static_priors | traditional    |         65484 |       21 |      7.57877 |             7.10405 |              8.75186 |      10.7694  |              9.8096  |               13.9433 |                   0.47349  |              0.391446 |                 60.4925 | traditional S05d-style Ridge using static priors plus B saturation/support covariates                                        |
| ridge                          | ml             |         65484 |       21 |      7.14035 |             6.69096 |              8.41378 |      10.55    |              9.75921 |               13.1629 |                   0.45292  |              0.397156 |                 60.3323 | standardized Ridge residual model with saturation, q-shift, amplitude, topology, baseline, and run-family support covariates |
| gradient_boosted_trees         | ml             |         65484 |       21 |      3.92071 |             3.53805 |              6.30951 |      12.41    |             10.2836  |               15.203  |                   0.197132 |              0.322196 |                 69.5332 | gradient-boosted tree residual model with B saturation/support covariates                                                    |
| extra_trees_s05e_dynamic       | ml             |         65484 |       21 |      2.25972 |             1.90239 |              3.6559  |       8.85036 |              7.50674 |               10.4383 |                   0.167491 |              0.300403 |                 37.2391 | S05e-style ExtraTrees dynamic-weight residual model with explicit B2 saturation features                                     |
| mlp                            | ml             |         65484 |       21 |      3.96195 |             3.53677 |              4.27287 |      19.133   |             14.0522  |               27.0329 |                   0.21648  |              0.373802 |                209.321  | tabular MLP residual model with B saturation/support covariates                                                              |
| cnn_1d                         | ml             |         65484 |       21 |      4.7553  |             4.30328 |              6.71005 |      20.7017  |             16.906   |               31.7153 |                   0.290117 |              0.375055 |                235.255  | compact two-channel 1D-CNN over left/right waveforms with support auxiliaries                                                |
| support_gated_cnn_new          | ml             |         65484 |       21 |      5.55219 |             4.50424 |             12.3136  |      20.8401  |             15.95    |               29.0666 |                   0.355812 |              0.368434 |                226.651  | new support-gated residual CNN suppressing waveform corrections outside A/B support                                          |
| waveform_only_mlp              | control        |         65484 |       21 |      3.70011 |             3.3841  |              5.75094 |      19.674   |             14.7881  |               32.7875 |                   0.202217 |              0.374939 |                217.539  | control: waveform-only MLP without A/B support priors                                                                        |
| pool_label_control             | control        |         65484 |       21 |      6.39977 |             4.51027 |             10.4956  |      19.4072  |             16.1501  |               26.6003 |                   0.438031 |              0.366419 |                228.535  | control: pair and run-family/pool labels only                                                                                |
| ml_shuffled_target_control     | control        |         65484 |       21 |      5.03119 |             4.54795 |              6.91311 |      20.6942  |             16.2511  |               30.4843 |                   0.320888 |              0.371576 |                233.897  | control: S05e-style ExtraTrees trained on shuffled targets                                                                   |

Pair-median sigma68 is `2.091` ns with CI `[1.892, 12.441]`. The traditional S05d static-prior Ridge is `7.579` ns with CI `[7.104, 8.752]`. The winner `extra_trees_s05e_dynamic` has sigma68 `2.260` ns with CI `[1.902, 3.656]`.

Winner-minus-pair-median delta: sigma68 `0.169` ns with CI `[-0.410, 0.293]`; covariance `-191.296` ns^2 with CI `[-237.609, -153.333]`.

Winner-minus-traditional-gate delta: sigma68 `-5.319` ns with CI `[-5.440, -5.110]`; covariance `-23.253` ns^2 with CI `[-29.250, -19.134]`.

Full paired deltas are in `method_delta_bootstrap.csv`:

| method                     | baseline                       | comparison                                                      |   delta_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   delta_mean_abs_pair_cov_ns2 |   cov_ci_low_ns2 |   cov_ci_high_ns2 |   p_two_sided_sigma68 |
|:---------------------------|:-------------------------------|:----------------------------------------------------------------|-------------------:|--------------------:|---------------------:|------------------------------:|-----------------:|------------------:|----------------------:|
| ridge                      | pair_median                    | ridge_minus_pair_median                                         |           5.04985  |          -3.71025   |             5.49588  |                   -168.202    |   -208.146       |    -144.041       |             0.0666667 |
| ridge                      | traditional_s05d_static_priors | ridge_minus_traditional_s05d_static_priors                      |          -0.438418 |          -0.622215  |            -0.035302 |                     -0.160172 |     -2.95524     |       2.907       |             0.0666667 |
| gradient_boosted_trees     | pair_median                    | gradient_boosted_trees_minus_pair_median                        |           1.83021  |          -1.91569   |             1.86631  |                   -159.001    |   -192.354       |    -117.946       |             0.133333  |
| gradient_boosted_trees     | traditional_s05d_static_priors | gradient_boosted_trees_minus_traditional_s05d_static_priors     |          -3.65806  |          -3.81385   |             1.6318   |                      9.0407   |      5.7822      |      12.5132      |             0.133333  |
| extra_trees_s05e_dynamic   | pair_median                    | extra_trees_s05e_dynamic_minus_pair_median                      |           0.169211 |          -0.410446  |             0.293227 |                   -191.296    |   -237.609       |    -153.333       |             0.133333  |
| extra_trees_s05e_dynamic   | traditional_s05d_static_priors | extra_trees_s05e_dynamic_minus_traditional_s05d_static_priors   |          -5.31906  |          -5.44045   |            -5.10976  |                    -23.2534   |    -29.2503      |     -19.1336      |             0         |
| mlp                        | pair_median                    | mlp_minus_pair_median                                           |           1.87144  |           1.53428   |             1.92816  |                    -19.2138   |    -26.0963      |     -12.4517      |             0         |
| mlp                        | traditional_s05d_static_priors | mlp_minus_traditional_s05d_static_priors                        |          -3.61682  |          -3.87589   |            -0.951034 |                    148.828    |     92.7275      |     184.961       |             0.0666667 |
| cnn_1d                     | pair_median                    | cnn_1d_minus_pair_median                                        |           2.6648   |           1.03449   |             3.24135  |                      6.7208   |     -0.553847    |      10.2941      |             0         |
| cnn_1d                     | traditional_s05d_static_priors | cnn_1d_minus_traditional_s05d_static_priors                     |          -2.82347  |          -3.15177   |            -1.85902  |                    174.763    |    125.343       |     215.265       |             0         |
| support_gated_cnn_new      | pair_median                    | support_gated_cnn_new_minus_pair_median                         |           3.46169  |           0.0702837 |             4.12336  |                     -1.88328  |     -7.61243     |       3.35092     |             0.0666667 |
| support_gated_cnn_new      | traditional_s05d_static_priors | support_gated_cnn_new_minus_traditional_s05d_static_priors      |          -2.02658  |          -2.90232   |            -1.56128  |                    166.159    |    125.759       |     216.745       |             0         |
| waveform_only_mlp          | pair_median                    | waveform_only_mlp_minus_pair_median                             |           1.60961  |           0.638611  |             1.70889  |                    -10.9956   |    -15.9788      |      -6.59103     |             0         |
| waveform_only_mlp          | traditional_s05d_static_priors | waveform_only_mlp_minus_traditional_s05d_static_priors          |          -3.87866  |          -4.04618   |             2.95484  |                    157.046    |    119.222       |     196.571       |             0.133333  |
| pool_label_control         | pair_median                    | pool_label_control_minus_pair_median                            |           4.30927  |           2.89917   |             6.53864  |                      0        |     -9.71223e-15 |       2.14584e-14 |             0         |
| pool_label_control         | traditional_s05d_static_priors | pool_label_control_minus_traditional_s05d_static_priors         |          -1.179    |          -2.52035   |             2.50991  |                    168.042    |    116.593       |     204.01        |             0.6       |
| ml_shuffled_target_control | pair_median                    | ml_shuffled_target_control_minus_pair_median                    |           2.94069  |           1.17893   |             3.05325  |                      5.36241  |     -0.823729    |      11.8106      |             0         |
| ml_shuffled_target_control | traditional_s05d_static_priors | ml_shuffled_target_control_minus_traditional_s05d_static_priors |          -2.54758  |          -2.74554   |            -2.31938  |                    173.405    |    124.098       |     214.17        |             0         |

## Support Frontier

Accepted support atoms and method-level support summaries:

| method                         |   n_supported_atoms |   supported_fraction_sum |   median_atom_sigma68_ns |   max_abs_residual_envelope_endpoint_ns |   median_b2_covariance_component_error_ns2 |   tail_fraction_median |
|:-------------------------------|--------------------:|-------------------------:|-------------------------:|----------------------------------------:|-------------------------------------------:|-----------------------:|
| cnn_1d                         |                  51 |                 0.844649 |                  3.86032 |                                136.543  |                                    31.6554 |              0.175695  |
| extra_trees_s05e_dynamic       |                  51 |                 0.844649 |                  1.71454 |                                 86.2826 |                                    20.9429 |              0.08      |
| gradient_boosted_trees         |                  51 |                 0.844649 |                  3.13241 |                                 94.3659 |                                    29.4265 |              0.129412  |
| ml_shuffled_target_control     |                  51 |                 0.844649 |                  4.35692 |                                132.653  |                                    33.9879 |              0.25      |
| mlp                            |                  51 |                 0.844649 |                  3.19376 |                                131.298  |                                    31.8443 |              0.121212  |
| pair_median                    |                  51 |                 0.844649 |                  1.66479 |                                140.806  |                                    32.0466 |              0.0476434 |
| pool_label_control             |                  51 |                 0.844649 |                  2.20414 |                                120.322  |                                    32.0466 |              0.0816327 |
| ridge                          |                  51 |                 0.844649 |                  6.3104  |                                 81.6851 |                                    11.6068 |              0.402439  |
| support_gated_cnn_new          |                  51 |                 0.844649 |                  4.36725 |                                132.894  |                                    31.0009 |              0.248996  |
| traditional_s05d_static_priors |                  51 |                 0.844649 |                  6.07073 |                                 82.9713 |                                    17.9755 |              0.396154  |
| waveform_only_mlp              |                  51 |                 0.844649 |                  2.9401  |                                135.575  |                                    31.2935 |              0.11236   |

Top support-frontier rows:

| support_atom                                                                                        | method                         |   n_pair_rows |   n_runs |   accepted_support_fraction | support_pass   |   median_bias_ns |   residual_envelope_low_ns |   residual_envelope_high_ns |   sigma68_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |   mean_abs_pair_cov_ns2 |   covariance_component_error_ns2 | run_family         | topology      | b2_saturation_depth_bin   | q_template_shift_bin   | amplitude_bin   | baseline_bin     | pileup_bin      |
|:----------------------------------------------------------------------------------------------------|:-------------------------------|--------------:|---------:|----------------------------:|:---------------|-----------------:|---------------------------:|----------------------------:|-------------:|--------------:|---------------------------:|------------------------:|---------------------------------:|:-------------------|:--------------|:--------------------------|:-----------------------|:----------------|:-----------------|:----------------|
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | cnn_1d                         |          4660 |        7 |                   0.0711624 | True           |        -1.62248  |                  -11.3382  |                    4.57529  |      2.98905 |       5.82155 |                  0.1103    |                 8.95506 |                         6.29079  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | extra_trees_s05e_dynamic       |          4660 |        7 |                   0.0711624 | True           |        -0.282512 |                   -7.4711  |                    3.45552  |      1.62443 |       4.61157 |                  0.0695279 |                 3.48235 |                         2.5299   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | gradient_boosted_trees         |          4660 |        7 |                   0.0711624 | True           |        -4.98207  |                  -11.1266  |                    1.72716  |      2.2945  |       5.29663 |                  0.0901288 |                 5.18856 |                         1.41017  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | ml_shuffled_target_control     |          4660 |        7 |                   0.0711624 | True           |        -5.67779  |                  -14.2909  |                    0.614415 |      3.51374 |       5.85105 |                  0.167167  |                 8.51167 |                         3.32395  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | mlp                            |          4660 |        7 |                   0.0711624 | True           |         0.390338 |                   -5.22565 |                    5.30617  |      2.1875  |       4.92183 |                  0.0540773 |                 5.18992 |                         3.63665  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | pair_median                    |          4660 |        7 |                   0.0711624 | True           |        -0.432339 |                   -5.87531 |                    2.55294  |      1.98389 |       5.12196 |                  0.0403433 |                 5.2098  |                         3.31708  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | pool_label_control             |          4660 |        7 |                   0.0711624 | True           |        -4.68953  |                  -13.3038  |                   -0.478363 |      1.83739 |       5.23608 |                  0.0611588 |                 5.2098  |                         3.31708  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | ridge                          |          4660 |        7 |                   0.0711624 | True           |        -0.6502   |                  -20.3179  |                   14.3511   |      6.73613 |       8.31607 |                  0.425966  |                22.49    |                         6.76812  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | support_gated_cnn_new          |          4660 |        7 |                   0.0711624 | True           |        -4.30387  |                  -16.5886  |                    5.4894   |      4.6388  |       6.73208 |                  0.289914  |                 8.33459 |                         5.4639   | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | traditional_s05d_static_priors |          4660 |        7 |                   0.0711624 | True           |         0.482464 |                  -17.8947  |                   13.3536   |      6.07073 |       7.38297 |                  0.390129  |                15.907   |                        -0.816854 | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=low|amp=low|base=nominal_baseline|pile=not_pileup_like  | waveform_only_mlp              |          4660 |        7 |                   0.0711624 | True           |         0.464944 |                   -4.81291 |                    5.0934   |      1.64626 |       5.21899 |                  0.0474249 |                 4.45323 |                         2.66053  | sample_ii_analysis | B2_containing | none                      | low                    | low             | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | cnn_1d                         |          3904 |        7 |                   0.0596176 | True           |        -4.61128  |                   -9.30819 |                   23.0128   |      3.65008 |       6.66057 |                  0.142162  |                20.261   |                         1.595    | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | extra_trees_s05e_dynamic       |          3904 |        7 |                   0.0596176 | True           |        -0.247702 |                   -3.1875  |                   21.4164   |      1.21356 |       4.95452 |                  0.0496926 |                12.6765  |                         0.126814 | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | gradient_boosted_trees         |          3904 |        7 |                   0.0596176 | True           |        -4.519    |                   -7.62113 |                   20.2466   |      2.96435 |       5.98553 |                  0.100666  |                17.0338  |                         9.44133  | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | ml_shuffled_target_control     |          3904 |        7 |                   0.0596176 | True           |        -6.48146  |                  -14.4674  |                   20.643    |      4.12318 |       6.98755 |                  0.220799  |                25.5247  |                        -5.52963  | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | mlp                            |          3904 |        7 |                   0.0596176 | True           |        -1.24593  |                   -4.72991 |                   26.3106   |      3.19376 |       6.52211 |                  0.123463  |                18.4687  |                        -0.487585 | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | pair_median                    |          3904 |        7 |                   0.0596176 | True           |        -0.542401 |                   -2.97991 |                   25.7395   |      1.25694 |       5.90699 |                  0.0476434 |                20.6958  |                         1.15533  | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | pool_label_control             |          3904 |        7 |                   0.0596176 | True           |        -4.88751  |                  -10.1268  |                   22.7203   |      1.84334 |       6.1944  |                  0.0745389 |                20.6958  |                         1.15533  | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | ridge                          |          3904 |        7 |                   0.0596176 | True           |         0.762202 |                   -8.97548 |                   13.1482   |      4.41179 |       5.40116 |                  0.265369  |                10.4976  |                       -20.4044   | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |
| sample_ii_analysis|B2_containing|sat=none|q=mid|amp=high|base=nominal_baseline|pile=not_pileup_like | support_gated_cnn_new          |          3904 |        7 |                   0.0596176 | True           |        -4.65889  |                  -10.5308  |                   24.022    |      3.72999 |       7.23757 |                  0.189805  |                20.8624  |                         0.949465 | sample_ii_analysis | B2_containing | none                      | mid                    | high            | nominal_baseline | not_pileup_like |

The full table is `support_frontier.csv`; `support_summary.csv` is the compact method-level ledger. Support-atom residual envelopes are the central 95% held-out residual range inside the matched cell; bootstrap CIs are reported in the primary method and delta tables above. The covariance-component error is the atom covariance minus the downstream-only covariance available in the same support cell; it is blank when the atom has no downstream reference rows.

## Covariance transfer

Run-level covariance interval coverage:

| method                      | target              |   coverage |
|:----------------------------|:--------------------|-----------:|
| ml_extratrees_covariance    | correlated_fraction |   0.45     |
| ml_extratrees_covariance    | sigma68             |   0.52381  |
| traditional_s05d_covariance | correlated_fraction |   0.65     |
| traditional_s05d_covariance | sigma68             |   0.761905 |

Per-held-out-run predictions are in `run_level_covariance_predictions.csv`. The traditional covariance model is the static-prior transfer test; the ML covariance model adds B pulse summaries and is more flexible but not treated as independent evidence if leakage checks fail.

## Leakage checks

| check                                       | value               | flag   |
|:--------------------------------------------|:--------------------|:-------|
| forbidden_feature_overlap                   |                     | False  |
| train_heldout_run_overlap                   | 0.0                 | False  |
| nominal_width_minus_shuffled_control_ns     | 0.521002631368435   | True   |
| nominal_width_minus_pool_label_control_ns   | -0.8475785978730279 | False  |
| nominal_cov_minus_waveform_only_control_ns2 | 9.112355374934765   | True   |
| random_row_split_r2                         | 0.9378601081946122  | False  |
| group_cv_ridge_rmse_ns                      | 10.076830355003562  | False  |

Control metrics:

| method                     | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   tail_fraction_abs_gt_5ns |   correlated_fraction |   mean_abs_pair_cov_ns2 | note                                                       |
|:---------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|---------------------------:|----------------------:|------------------------:|:-----------------------------------------------------------|
| waveform_only_mlp          | control        |         65484 |       21 |      3.70011 |             3.3841  |              5.75094 |       19.674  |              14.7881 |               32.7875 |                   0.202217 |              0.374939 |                 217.539 | control: waveform-only MLP without A/B support priors      |
| pool_label_control         | control        |         65484 |       21 |      6.39977 |             4.51027 |             10.4956  |       19.4072 |              16.1501 |               26.6003 |                   0.438031 |              0.366419 |                 228.535 | control: pair and run-family/pool labels only              |
| ml_shuffled_target_control | control        |         65484 |       21 |      5.03119 |             4.54795 |              6.91311 |       20.6942 |              16.2511 |               30.4843 |                   0.320888 |              0.371576 |                 233.897 | control: S05e-style ExtraTrees trained on shuffled targets |

## Systematics And Caveats

The q-template axis is a waveform-derived proxy, not a full refit of the S01 amplitude-adaptive template library. It combines late charge and peak-sample displacement, so it should be read as a support coordinate for shape shift rather than an absolute template-fit quality. The baseline-lowering flag uses the lower tail of the raw pre-trigger baseline distribution in the selected pair sample; it is sensitive to run composition and should not be interpreted as an independent pedestal calibration.

The support frontier is intentionally conservative. Cells below `250` pair rows or `4` runs are excluded from the accepted-support summary even if their point estimates look favorable. The support-atom residual envelopes are descriptive central 95% ranges, while the formal bootstrap CIs are the run-block intervals in the method and delta tables. MLP convergence warnings are possible under the short laptop iteration budget and are treated as a model-quality caveat, not as evidence for the MLP.

The covariance-component error is defined against downstream-only rows matched on run family, saturation-depth bin, q-shift bin, amplitude bin, baseline bin, and pile-up-candidate bin, with topology left free for the contrast. It is blank when no downstream reference exists. The winner is therefore a held-out benchmark winner and support-frontier candidate, not a proof that dynamic covariance weights are calibrated outside the populated support atoms.

## Conclusion

The independence approximation is not globally supported by the B-stack
residual covariance ledger. Pair-median centering leaves a large off-diagonal
covariance scale (`228.535 ns^2`) and the best non-control method reduces, but
does not eliminate, the correlated fraction (`0.300`). The defensible two-ended
projection is therefore the conservative floor-preserving form
`sigma_common^2 + sigma_local^2/2`, not a blanket `sqrt(2)` reduction of all
single-ended timing variance.

The saturation-aware ML winner improves the held-out covariance point estimate,
but the support frontier is narrower than the global result: deep B2 saturation,
high q-shift, low-baseline, and pile-up-like atoms remain the places where bias
and covariance-component errors should be treated as systematics rather than
calibrated corrections. The result is therefore a benchmark winner plus an
explicit support frontier, not an unconditional recommendation to use dynamic
covariance weights everywhere.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `astack_run_summaries.csv`, `bstack_pair_table_preview.csv`, `heldout_pair_residuals.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `support_frontier.csv`, `support_summary.csv`, `run_level_covariance_predictions.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
