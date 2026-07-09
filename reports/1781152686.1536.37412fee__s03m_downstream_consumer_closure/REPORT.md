# S03m: Downstream-consumer closure for S03l residual-risk atoms

- **Ticket:** `1781152686.1536.37412fee`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** B-stack ROOT files resolved by `configs/p03f_1781034623_1381_12086ef0_loro_feature_multimodel.json`
- **Frozen atom source:** S03l residual-risk ledger `reports/1781052591.513.61ea58a7__s03l_cross_sample_timewalk_residual_atom_ledger`
- **Comparator:** exact-fold S03 `analytic_timewalk`
- **Correction under test:** `s03l_atom_gated_hgb`, which substitutes the frozen HGB correction only inside frozen S03l high-risk atoms
- **Held-out split:** Sample-II runs 58, 59, 60, 61, 62, 63, and 65; CIs use run-block bootstrap

## Abstract

This S03m closure freezes the S03l high-risk atom definitions and asks whether applying a timing correction only in those atoms changes downstream consumer metrics. The raw-ROOT reproduction gate passes exactly at **640,737** selected B-stave pulses. The frozen atom gate marks **6,764 / 11,460** held-out pair residuals (**0.590**) as high risk. On the primary timing residual estimand, the atom-gated correction changes `sigma68` by **0.065 ns** with run-block 95% CI **[-0.180, 0.206]** relative to the S03 analytic comparator. The full HGB correction remains the global family-benchmark winner, but the atom gate isolates the downstream change to the S03l risk support.

## Raw-ROOT Reproduction Gate

The gate reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3, and counts selected B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Frozen Atom Definitions

The S03l high-risk gate is fixed before inspecting S03m consumer deltas:

`G_i = 1[ A_min > 4000 ADC or saturation_i or template_mismatch_i or q_template_bin_i = (0.0228,0.0474] or pretrigger_lowering_i > 25 ADC ]`.

These are the top S03l residual-risk mechanisms with direct pulse-shape support: high-amplitude/saturation, template mismatch, and pretrigger lowering. Topology is retained as a reported support covariate but is not used in the gate, because using common amplitude-order labels as a correction trigger would cover most held-out rows and weaken the closure interpretation. The atom-gated residual is

`r_i(gated) = G_i r_i(HGB) + (1 - G_i) r_i(S03 analytic)`.

The full-HGB row is retained as a positive-control bound, not as the atom-conditioned policy.

## Estimands

For event `e`, pair `(a,b)`, and timing method `m`,

`r_{eabm} = tau_{eam} - tau_{ebm}`,

`sigma68(r) = (Q84(r) - Q16(r))/2`,

`T5(r) = P(|r - median(r)| > 5 ns)`.

For consumer stratum `c`, S03m reports `Delta_c = metric_c(gated) - metric_c(analytic)`. Negative deltas improve width, RMS, or tail fraction. Whole held-out runs are resampled with replacement for bootstrap CIs.

## Required Family Benchmark

| method                                 | model_family                      | family      |   n_pair_residuals |   sigma68_ns | ci             |   full_rms_ns |   tail_frac_vs_traditional_p95 |   delta_vs_traditional_ns | delta_ci         |
|:---------------------------------------|:----------------------------------|:------------|-------------------:|-------------:|:---------------|--------------:|-------------------------------:|--------------------------:|:-----------------|
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees            | ml          |              11460 |      1.10742 | [1.075, 1.159] |       2.13171 |                      0.0203316 |                 -0.443675 | [-0.842, -0.241] |
| mlp_waveform_amp_shape_stave           | mlp                               | ml          |              11460 |      1.1621  | [1.106, 1.235] |       2.45852 |                      0.0205061 |                 -0.388989 | [-0.818, -0.167] |
| ridge_waveform_stave_onehot            | ridge                             | ml          |              11460 |      1.24442 | [1.173, 1.322] |       2.40735 |                      0.0267888 |                 -0.306677 | [-0.739, -0.089] |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture    | ml          |              11460 |      1.25349 | [1.213, 1.308] |       2.43513 |                      0.0273997 |                 -0.297601 | [-0.671, -0.095] |
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                            | ml          |              11460 |      1.26387 | [1.212, 1.343] |       2.43601 |                      0.0280105 |                 -0.287227 | [-0.686, -0.086] |
| analytic_timewalk                      | traditional_s03_analytic_timewalk | traditional |              11460 |      1.55109 | [1.364, 1.936] |       2.66699 |                      0.05      |                  0        | [0.000, 0.000]   |

The required panel contains the strong traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and the feature-gated architecture. `result.json` names **hgb_waveform_amp_shape_stave** as the global benchmark winner.

## Top-Level Consumer Closure

| consumer   | stratum               |   n_pair_residuals |   atom_gate_fraction |   analytic_sigma68_ns |   candidate_sigma68_ns |   candidate_minus_analytic_sigma68_ns | sigma68_delta_ci   |   candidate_minus_analytic_tail_frac_abs_gt5ns | tail_delta_ci     |
|:-----------|:----------------------|-------------------:|---------------------:|----------------------:|-----------------------:|--------------------------------------:|:-------------------|-----------------------------------------------:|:------------------|
| timing     | all                   |              11460 |             0.590227 |               1.55109 |                1.61562 |                             0.0645319 | [-0.180, 0.206]    |                                     0.00314136 | [-0.0032, 0.0093] |
| charge     | all_charge_matched    |              11460 |             0.590227 |               1.55109 |                1.61562 |                             0.0645319 | [-0.180, 0.199]    |                                     0.00314136 | [-0.0037, 0.0090] |
| energy     | all_energy_support    |              11460 |             0.590227 |               1.55109 |                1.61562 |                             0.0645319 | [-0.174, 0.199]    |                                     0.00314136 | [-0.0032, 0.0091] |
| pileup     | all_timing_tail_proxy |              11460 |             0.590227 |               1.55109 |                1.61562 |                             0.0645319 | [-0.182, 0.204]    |                                     0.00314136 | [-0.0034, 0.0090] |
| pid        | all_topology_proxy    |              11460 |             0.590227 |               1.55109 |                1.61562 |                             0.0645319 | [-0.182, 0.193]    |                                     0.00314136 | [-0.0032, 0.0095] |

The consumer rows are not independent truth measurements. They are downstream support views on the same joined event-pair population: charge and energy use S06 support covariates, pile-up uses timing-window and run-family support, and PID uses topology/anomaly support.

## Atom and Consumer Strata

| consumer   | stratum                                                                            |   n_pair_residuals |   atom_gate_fraction |   analytic_sigma68_ns |   candidate_sigma68_ns |   candidate_minus_analytic_sigma68_ns | sigma68_delta_ci   |
|:-----------|:-----------------------------------------------------------------------------------|-------------------:|---------------------:|----------------------:|-----------------------:|--------------------------------------:|:-------------------|
| energy     | amplitude_bin=amp_adc[4000,7000)                                                   |                492 |             1        |               2.55444 |               1.36516  |                            -1.18928   | [-1.854, -0.889]   |
| timing     | s03l_atom_label=high_amplitude_or_saturation                                       |               1330 |             1        |               2.03576 |               1.21562  |                            -0.82014   | [-1.130, -0.561]   |
| timing     | s03l_atom_label=high_amplitude_or_saturation+template_mismatch                     |                420 |             1        |               1.8747  |               1.21013  |                            -0.664569  | [-1.097, -0.294]   |
| timing     | s03l_atom_label=template_mismatch                                                  |               1969 |             1        |               2.01055 |               1.35343  |                            -0.657126  | [-1.188, -0.344]   |
| timing     | s03l_atom_label=high_amplitude_or_saturation+pretrigger_lowering                   |                260 |             1        |               1.58974 |               0.975408 |                            -0.614336  | [-0.794, -0.286]   |
| pid        | p09_anomaly_class=novel_early_pretrigger                                           |                298 |             1        |               1.31998 |               0.780244 |                            -0.539737  | [-0.620, -0.405]   |
| timing     | s03l_atom_label=template_mismatch+pretrigger_lowering                              |               1756 |             1        |               1.19484 |               0.669346 |                            -0.525499  | [-0.553, -0.486]   |
| timing     | S03l high-risk atoms                                                               |               6764 |             1        |               1.53517 |               1.01757  |                            -0.517602  | [-0.783, -0.394]   |
| pileup     | sample_window_mask=artifact_sensitive_3_6                                          |               2498 |             0.869896 |               1.18037 |               0.678508 |                            -0.501865  | [-0.544, -0.446]   |
| timing     | s03l_atom_label=high_amplitude_or_saturation+template_mismatch+pretrigger_lowering |                205 |             1        |               1.13995 |               0.71636  |                            -0.423593  | [-0.858, -0.275]   |
| timing     | s03l_atom_label=pretrigger_lowering                                                |                824 |             1        |               1.14819 |               0.877484 |                            -0.270708  | [-0.429, -0.127]   |
| charge     | charge_bin=charge[24000,40000)                                                     |               3624 |             0.681291 |               1.77525 |               1.52442  |                            -0.250831  | [-0.423, -0.064]   |
| pileup     | sample_window_mask=nominal_template_7_11                                           |               8056 |             0.527433 |               1.86995 |               1.77167  |                            -0.0982789 | [-0.215, 0.139]    |
| pileup     | run_family=sampleII_mid_61_63                                                      |               6330 |             0.593207 |               1.73368 |               1.6799   |                            -0.0537868 | [-0.208, 0.232]    |
| timing     | s03l_atom_label=nominal                                                            |               4696 |             0        |               1.5839  |               1.5839   |                             0         | [0.000, 0.000]     |
| timing     | S03l nominal atoms                                                                 |               4696 |             0        |               1.5839  |               1.5839   |                             0         | [0.000, 0.000]     |
| pid        | p09_anomaly_class=unassigned_common                                                |              10516 |             0.589578 |               1.59707 |               1.61496  |                             0.0178938 | [-0.200, 0.172]    |
| energy     | amplitude_bin=amp_adc[2500,4000)                                                   |               6811 |             0.53487  |               1.56158 |               1.61153  |                             0.0499537 | [-0.175, 0.241]    |

The largest atom-gated gains occur where the frozen S03l gate has appreciable support. Nominal rows remain anchored to the analytic comparator by construction; this makes the test conservative for global adoption and more directly interpretable as a downstream risk-containment policy.

## Imported Consumer Context

| source                              | consumer   | method                    | metric                 |     value |      ci_low |     ci_high | role                                      |
|:------------------------------------|:-----------|:--------------------------|:-----------------------|----------:|------------:|------------:|:------------------------------------------|
| S06b charge-energy timing support   | charge     | traditional               | calibration_loss       | 0.659059  |   0.549944  |   0.775257  | charge-matched pull baseline              |
| S06b charge-energy timing support   | charge     | phase_conformal_gated_cnn | calibration_loss       | 0.0534484 |   0.0414198 |   0.0704633 | best existing uncertainty consumer        |
| S06b charge-energy timing support   | energy     | phase_conformal_gated_cnn | sigma68_ns             | 1.50399   |   1.3773    |   1.68357   | best existing energy-support timing width |
| S06c action-band closure            | energy     | phase_conformal_gated_cnn | calibration_loss       | 0.0748153 |   0.0542841 |   0.106241  | accepted support best existing consumer   |
| S10h phase-calibrated pileup window | pileup     | 1d_cnn                    | mean_average_precision | 1         | nan         | nan         | event-level pile-up classifier reference  |
| S00h calibrated PID-energy support  | pid        | new_shape_residual_fusion | roc_auc                | 0.988338  |   0.984335  |   0.993619  | best PID-energy support model             |
| S14h G4 energy calibration          | energy     | geant4_birks_lookup       | res68_frac             | 0.040244  |   0.0388569 |   0.0416063 | traditional energy calibration            |

These imported rows calibrate the meaning of the consumer labels but do not determine the S03m winner.

## Systematics and Caveats

- **Raw reproduction:** the selected-pulse count is reproduced from raw ROOT before any joined-table inference.
- **Frozen atoms:** thresholds and topologies are fixed from S03l. S03m does not re-optimize the atom gate on consumer deltas.
- **Split discipline:** the residual panel is the frozen P03f/S03k leave-one-run-out Sample-II panel, and CIs resample held-out runs.
- **Consumer coupling:** top-level charge, pile-up, PID, and energy rows share the same timing residuals with different support labels, so they are correlated screens rather than independent detector truth.
- **Policy limitation:** atom-gated HGB is a risk-containment correction. Full replacement still needs a locked correction API and consumer-native retraining.
- **Small strata:** strata below the support threshold are omitted from tables; rare failure modes require gallery-style follow-up.

## Verdict

`result.json` names **hgb_waveform_amp_shape_stave** as the global family-benchmark winner and records the atom-gated S03m policy as the downstream closure object. The atom-conditioned correction improves the frozen high-risk rows, but the pooled top-level consumer deltas do not establish a global replacement: the primary pooled `sigma68` delta is small, positive, and statistically compatible with zero. The defensible conclusion is therefore risk-local usefulness, not unconditional downstream adoption.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03m_1781152686_1536_37412fee_downstream_consumer_closure.py
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `required_family_benchmark.csv`, `atom_gated_residual_rows.csv.gz`, `substitution_summary.csv`, `downstream_metric_deltas.csv`, `imported_consumer_evidence.csv`, `input_sha256.csv`, and `manifest.json`.
