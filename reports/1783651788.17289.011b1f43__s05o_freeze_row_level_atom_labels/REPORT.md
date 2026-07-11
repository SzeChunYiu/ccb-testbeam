# S05o: Freeze Row-Level Atom Labels In Residual Export

## Abstract

Ticket `1783651788.17289.011b1f43` asks for the S05 row-level support labels to be written into the original leave-one-run-out residual export rather than reconstructed later by joining the B-stack preview. I materialized `loro_residual_export_with_atoms.csv.gz` from the frozen S05h `oof_full.csv.gz` fold-generation artifact, then reran the S05n atom-conditional interval calibration on that export. The export includes `support_atom`, `support_ref_atom`, saturation, q-shift, amplitude, baseline, pile-up, topology, target residual, and every benchmark residual column.

The winner in `result.json` is **ridge**, selected by minimum atom-weighted absolute 95% coverage error with worst atom undercoverage and full RMS as tie-breakers. Its held-out sigma68 is **7.074460 ns** with run-bootstrap 95% CI **[7.714074, 9.132112]**, and its atom-weighted absolute 95% coverage error is **0.001566**.

## Raw ROOT Reproduction

The source S05h fold export was generated from raw HRD ROOT under `/home/billy/ccb-data/extracted/root/root`. I re-recorded the frozen S05m reproduction table, which checks the raw A-stack anchor before the B-stack residual analysis.

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total_selected_b_pulses | 640737.0 | 640737.0 | 0.0 | 0.0 | True |
| sample_i_analysis_b_selected_pulses | 252266.0 | 252266.0 | 0.0 | 0.0 | True |
| sample_ii_analysis_b_selected_pulses | 125096.0 | 125096.0 | 0.0 | 0.0 | True |
| sample_iv_a1_a3_pairs | 127.0 | 127.0 | 0.0 | 0.0 | True |
| sample_iv_a1_a3_robust_width_ns | 1.7936257228944266 | 1.7936260637768346 | 3.4088240807861325e-07 | 0.001 | True |

## Export-Time Freeze

Let `x_i` be the row features present at fold generation for pair row `i`. S05h already computes support coordinates

`a_i = (family_i, topology_i, saturation_i, q_i, amplitude_i, baseline_i, pileup_i)`.

S05o persists both the full label

`support_atom_i = family | topology | sat | q | amp | baseline | pileup`

and the downstream reference label

`support_ref_atom_i = family | downstream_only | sat | q | amp | baseline | pileup`.

This removes the later reconstruction join as a dependency for S05m/S05n interval calibration.

## Invariance Checks

| check | value | expected | pass |
| --- | --- | --- | --- |
| row_count_export | 65504 | 65504 | True |
| key_set_match | {'both': 65504, 'left_only': 0, 'right_only': 0} | both only | True |
| support_atom_mismatch_count | 0 | 0 | True |
| support_ref_atom_mismatch_count | 0 | 0 | True |
| atom_b2_saturation_depth_mismatch_count | 0 | 0 | True |
| atom_q_template_shift_mismatch_count | 0 | 0 | True |
| atom_amplitude_mismatch_count | 0 | 0 | True |
| atom_baseline_lowering_mismatch_count | 0 | 0 | True |
| atom_pileup_candidate_mismatch_count | 0 | 0 | True |

Metric deltas against the previous reconstruction-join path:

| method | metric | delta_export_minus_reconstructed | pass |
| --- | --- | --- | --- |
| pair_median | sigma68_ns | 0.0 | True |
| pair_median | full_rms_ns | 0.0 | True |
| pair_median | atom_weighted_abs_coverage_error_95 | 1.9949319973733282e-17 | True |
| pair_median | worst_atom_undercoverage_95 | -8.326672684688674e-17 | True |
| traditional_s05d_static_priors | sigma68_ns | 0.0 | True |
| traditional_s05d_static_priors | full_rms_ns | 0.0 | True |
| traditional_s05d_static_priors | atom_weighted_abs_coverage_error_95 | 4.358492733391728e-17 | True |
| traditional_s05d_static_priors | worst_atom_undercoverage_95 | -8.326672684688674e-17 | True |
| ridge | sigma68_ns | -8.881784197001252e-16 | True |
| ridge | full_rms_ns | 0.0 | True |
| ridge | atom_weighted_abs_coverage_error_95 | 9.215718466126788e-17 | True |
| ridge | worst_atom_undercoverage_95 | -5.551115123125783e-17 | True |
| gradient_boosted_trees | sigma68_ns | 0.0 | True |
| gradient_boosted_trees | full_rms_ns | 0.0 | True |
| gradient_boosted_trees | atom_weighted_abs_coverage_error_95 | 7.37257477290143e-17 | True |
| gradient_boosted_trees | worst_atom_undercoverage_95 | 0.0 | True |
| mlp | sigma68_ns | 0.0 | True |
| mlp | full_rms_ns | 0.0 | True |
| mlp | atom_weighted_abs_coverage_error_95 | 5.377642775528102e-17 | True |
| mlp | worst_atom_undercoverage_95 | 0.0 | True |
| cnn_1d | sigma68_ns | 0.0 | True |
| cnn_1d | full_rms_ns | 0.0 | True |
| cnn_1d | atom_weighted_abs_coverage_error_95 | 3.469446951953614e-18 | True |
| cnn_1d | worst_atom_undercoverage_95 | -5.551115123125783e-17 | True |
| support_gated_cnn_new | sigma68_ns | 0.0 | True |
| support_gated_cnn_new | full_rms_ns | 7.105427357601002e-15 | True |
| support_gated_cnn_new | atom_weighted_abs_coverage_error_95 | 2.6020852139652106e-17 | True |
| support_gated_cnn_new | worst_atom_undercoverage_95 | 0.0 | True |
| extra_trees_s05e_dynamic | sigma68_ns | 0.0 | True |
| extra_trees_s05e_dynamic | full_rms_ns | 0.0 | True |
| extra_trees_s05e_dynamic | atom_weighted_abs_coverage_error_95 | 7.19910242530375e-17 | True |
| extra_trees_s05e_dynamic | worst_atom_undercoverage_95 | -1.3877787807814457e-17 | True |

## Benchmark Methods

The benchmark is split by held-out run and uses the same frozen residual columns as S05h/S05n: `traditional_s05d_static_priors`, `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, `support_gated_cnn_new`, and `extra_trees_s05e_dynamic`. `support_gated_cnn_new` is retained as the new architecture because it gates convolutional waveform channels by the same support coordinates now persisted in the export.

For method `m`, residuals are `e_i(m)=y_i-f_m(x_i)`. The robust width is

`sigma68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

For atom `a`, held-out run `g`, and nominal coverage `q`, the conformal half-width is

`h_{m,a,g}(q)=Q_q(|e_i(m)-median(e_{train,a}(m))| : run_i != g, atom_i=a)`.

Coverage is estimated on the held-out run only; CIs resample held-out runs with replacement.

## Results

| method | method_class | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | full_rms_ns | atom_weighted_abs_coverage_error_95 | worst_atom_undercoverage_95 | n_supported_atoms_95 | supported_row_fraction_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ridge | ml | 7.0744603724416875 | 7.714073529704373 | 9.132112357004917 | 10.501281309481117 | 0.001566023166023192 | -0.12869415807560136 | 10 | 0.9884892525647289 |
| traditional_s05d_static_priors | traditional | 7.812067271683465 | 8.332398891308449 | 10.025433692139334 | 10.8241666084736 | 0.0018764478764478436 | -0.12525773195876289 | 10 | 0.9884892525647289 |
| extra_trees_s05e_dynamic | ml | 2.1985998230967114 | 3.710302360961038 | 5.701584768658118 | 8.86200300209221 | 0.002185328185328172 | -0.09224137931034482 | 10 | 0.9884892525647289 |
| gradient_boosted_trees | ml | 3.922680120866924 | 7.289268244203953 | 12.304769270499646 | 12.353136013212938 | 0.002325868725868674 | -0.1396551724137931 | 10 | 0.9884892525647289 |
| pair_median | traditional | 2.0907157547048136 | 9.851401549809385 | 23.412079965229417 | 20.690021500723844 | 0.00326332046332042 | -0.18706896551724128 | 10 | 0.9884892525647289 |
| mlp | ml | 4.269809927916058 | 11.016485529619702 | 21.39189056375287 | 19.1947553385069 | 0.011413127413127354 | -0.1396551724137931 | 10 | 0.9884892525647289 |
| support_gated_cnn_new | ml | 4.889256979871144 | 11.599895138015127 | 23.186816755433536 | 20.33876322738382 | 0.012183783783783726 | -0.2689655172413793 | 10 | 0.9884892525647289 |
| cnn_1d | ml | 5.79714148741575 | 11.095399527108551 | 22.644768661367948 | 20.53316194245538 | 0.024653281853281802 | -0.07658857332301905 | 10 | 0.9884892525647289 |

Worst 95% atom rows:

| method | support_atom | n_runs | n_pair_rows | coverage | coverage_ci_low | coverage_ci_high | coverage_error | mean_interval_width_ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| support_gated_cnn_new | sample_i_analysis|B2_containing|sat=deep|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 4 | 232 | 0.6810344827586207 | 0.642512077294686 | 1.0 | -0.2689655172413793 | 18.679358135086883 |
| support_gated_cnn_new | sample_i_analysis|downstream_only|sat=none|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 3 | 291 | 0.6838487972508591 | 0.3333333333333333 | 0.6923076923076923 | -0.26615120274914084 | 13.825835103264986 |
| pair_median | sample_i_analysis|B2_containing|sat=deep|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 4 | 232 | 0.7629310344827587 | 0.7342995169082126 | 1.0 | -0.18706896551724128 | 19.938028899225802 |
| mlp | sample_i_analysis|B2_containing|sat=deep|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 4 | 232 | 0.8103448275862069 | 0.7874396135265701 | 1.0 | -0.1396551724137931 | 22.032447593779658 |
| gradient_boosted_trees | sample_i_analysis|B2_containing|sat=deep|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 4 | 232 | 0.8103448275862069 | 0.7874396135265701 | 1.0 | -0.1396551724137931 | 20.442228793600776 |
| ridge | sample_i_analysis|downstream_only|sat=none|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 3 | 291 | 0.8213058419243986 | 0.8015267175572519 | 1.0 | -0.12869415807560136 | 20.35540379597722 |
| traditional_s05d_static_priors | sample_i_analysis|downstream_only|sat=none|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 3 | 291 | 0.8247422680412371 | 0.8075471698113208 | 1.0 | -0.12525773195876289 | 19.371645848352735 |
| extra_trees_s05e_dynamic | sample_i_analysis|B2_containing|sat=deep|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 4 | 232 | 0.8577586206896551 | 0.8454106280193237 | 1.0 | -0.09224137931034482 | 16.019826593430526 |
| cnn_1d | sample_ii_analysis|downstream_only|sat=none|q=all|amp=all|base=low_baseline|pile=not_pileup_like | 7 | 18098 | 0.8734114266769809 | 0.755256512152288 | 0.9722772277227723 | -0.07658857332301905 | 16.604658430120818 |
| traditional_s05d_static_priors | sample_i_analysis|B2_containing|sat=none|q=all|amp=all|base=nominal_baseline|pile=not_pileup_like | 4 | 374 | 0.8877005347593583 | 0.8746177370030581 | 1.0 | -0.06229946524064167 | 26.676019245548886 |
| pair_median | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 173.38903477491692 |
| support_gated_cnn_new | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 166.97572253212215 |
| cnn_1d | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 171.66800882148516 |
| mlp | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 168.44137962178868 |
| ridge | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 96.56493885295542 |
| gradient_boosted_trees | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 92.05138913489151 |
| traditional_s05d_static_priors | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 95.16853780153723 |
| extra_trees_s05e_dynamic | sample_i_analysis|B2_containing|sat=mild|q=all|amp=all|base=nominal_baseline|pile=pileup_like | 2 | 9 | 0.8888888888888888 | 0.875 | 1.0 | -0.061111111111111116 | 97.29695212973674 |

## Systematics And Caveats

The freeze changes data plumbing, not model training: S05h predictors are not refit. This is intentional because the ticket asks whether downstream S05m/S05n calibration is invariant when atom labels are available in the residual export itself. The bootstrap is run-block, so it captures run-level instability but not all possible calibration uncertainty. Sparse atoms below `120` rows or `3` runs are excluded from formal scoring. Support atoms are waveform-derived nuisance strata, not external truth labels.

## Conclusion

The export-time atom freeze is row-count and label invariant relative to the reconstruction-join S05n path. It removes a fragile downstream join while preserving the S05m/S05n interval calibration and benchmark ordering. The winning method remains **ridge** under the frozen export.
