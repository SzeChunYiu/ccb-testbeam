# S03o: consumer-native labels for frozen S03m excluded regions

- **Ticket:** `1783653582.14387.18484e38`
- **Worker:** `testbeam-laptop-4`
- **Question:** acquire or join event-native pile-up/PID/charge/energy labels for S03m abstain and recalibrate rows, then test whether excluded regions should split into recoverable HGB-refit and hard-veto actions.
- **Primary split:** run-held-out Sample-II excluded-support benchmark; bootstrap unit is held-out run.

## Abstract

This study joins the frozen S03m excluded-region action table to downstream consumer-native evidence from charge, energy, pile-up, and PID studies, and to the S03o external-shape excluded-support ML benchmark. The raw ROOT anchor is reproduced exactly at **640737** selected B-stave pulses. On the excluded-support benchmark, **traditional_hier_amp** wins with `sigma68 = 1.892 ns`, 95% CI **[1.588, 2.335]**, versus the strong traditional hierarchical-amplitude comparator.

The consumer-native action split is intentionally stricter than the ML ranking: an S03m excluded row is called `recoverable_hgb_refit` only when HGB improves the excluded-support residual width without increasing the tail fraction and when the event-native support fraction is adequate. Rows with no support, low support, or non-improving HGB are labelled `hard_veto`; ambiguous rows remain `diagnostic_abstain`.

## Raw ROOT Reproduction

The count gate reads the configured raw ROOT files directly, subtracts the median of samples 0--3 per channel, and counts B2/B4/B6/B8 pulses above 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimands

For event `e`, pair `p`, and method `m`, the same-particle residual is

`r_(e,p,m) = tau_(e,a,m) - tau_(e,b,m)`,

where `tau` is the geometry-corrected downstream timestamp. The principal width is

`sigma68(r) = (Q_84(r) - Q_16(r)) / 2`.

For each excluded S03m row `g`, the consumer-native recovery statistic is

`Delta_g = sigma68_g(HGB) - sigma68_g(traditional)`,

with a parallel tail statistic

`T_g = P(|r_HGB - median(r_HGB)| > 5 ns) - P(|r_trad - median(r_trad)| > 5 ns)`.

The decision rule is:

- `recoverable_hgb_refit` when `Delta_g < 0`, `T_g <= 0`, support event fraction >= 0.1, and at least 100 pair residuals are present.
- `hard_veto` when support is absent/low, or when S03m required recalibration but the consumer-native HGB evidence does not cleanly recover the stratum.
- `diagnostic_abstain` for mixed evidence that should travel as a label but not authorize production reuse.

## Required Method Benchmark

| method                 | model_family               |   n_pair_residuals |   sigma68_ns | sigma68_ci     |   full_rms_ns |   tail_frac_abs_gt5ns | tail_ci          |   bias_vs_log_amp_slope_ns |
|:-----------------------|:---------------------------|-------------------:|-------------:|:---------------|--------------:|----------------------:|:-----------------|---------------------------:|
| traditional_hier_amp   | traditional                |               1344 |      1.89171 | [1.588, 2.335] |       3.89822 |             0.0498512 | [0.0344, 0.0590] |                  -0.925272 |
| tiny_1d_cnn            | 1d_cnn                     |               1344 |      1.92293 | [1.640, 2.285] |       3.84021 |             0.0431548 | [0.0333, 0.0507] |                  -0.70626  |
| gradient_boosted_trees | gradient_boosted_trees     |               1344 |      1.94386 | [1.698, 2.225] |       3.60832 |             0.0424107 | [0.0282, 0.0519] |                  -1.84903  |
| support_gated_ensemble | new_support_gated_ensemble |               1344 |      1.99923 | [1.721, 2.349] |       3.67952 |             0.046131  | [0.0302, 0.0579] |                  -2.00263  |
| mlp_waveform           | mlp                        |               1344 |      2.01402 | [1.782, 2.185] |       3.41983 |             0.0394345 | [0.0316, 0.0523] |                  -1.2667   |
| ridge_waveform         | ridge                      |               1344 |      2.07844 | [1.707, 2.437] |       3.86055 |             0.046875  | [0.0341, 0.0526] |                  -0.950889 |

This table includes the requested strong traditional method, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new support-gated ensemble. The support-gated ensemble is sensible because the candidate rows are not generic pulses: they are selected by S03m exclusion/action support and by external late-shape constraints, so a gate can condition the waveform model on support membership without using run id or event id.

## Consumer-Native Label Join

| consumer   | native_label_source                 | native_label_method       | native_metric          |   native_value | native_ci      | native_role                              | stratum               |   candidate_minus_analytic_sigma68_ns |   sigma68_delta_ci_low_ns |   sigma68_delta_ci_high_ns |
|:-----------|:------------------------------------|:--------------------------|:-----------------------|---------------:|:---------------|:-----------------------------------------|:----------------------|--------------------------------------:|--------------------------:|---------------------------:|
| charge     | S06b charge-energy timing support   | phase_conformal_gated_cnn | calibration_loss       |      0.0534484 | [0.041, 0.070] | best existing uncertainty consumer       | all_charge_matched    |                             -0.443675 |                 -0.860892 |                  -0.245313 |
| energy     | S14h G4 energy calibration          | geant4_birks_lookup       | res68_frac             |      0.040244  | [0.039, 0.042] | traditional energy calibration           | all_energy_support    |                             -0.443675 |                 -0.805817 |                  -0.253092 |
| pid        | S00h calibrated PID-energy support  | new_shape_residual_fusion | roc_auc                |      0.988337  | [0.984, 0.994] | best PID-energy support model            | all_topology_proxy    |                             -0.443675 |                 -0.797505 |                  -0.243368 |
| pileup     | S10h phase-calibrated pileup window | 1d_cnn                    | mean_average_precision |      1         | not estimable  | event-level pile-up classifier reference | all_timing_tail_proxy |                             -0.443675 |                 -0.804033 |                  -0.248449 |

These rows are not used as direct supervised labels for timing. They are event-native consumer references: charge and energy calibration loss or width, pile-up average precision, PID ROC AUC, and GEANT4 energy calibration. The joined high-risk timing deltas show whether the timing substitution that would feed those consumers improves or worsens the same-particle closure in the S03m high-risk/excluded support.

## Excluded-Region Action Split

| source_unit             | source_stratum     | s03m_action   |   n_pair_residuals |   n_runs |   s03m_sigma68_ns | s03m_sigma68_ci   |   support_event_fraction |   hgb_minus_traditional_sigma68_ns |   hgb_minus_traditional_tail_frac | consumer_native_action   | rationale                                                                                |
|:------------------------|:-------------------|:--------------|-------------------:|---------:|------------------:|:------------------|-------------------------:|-----------------------------------:|----------------------------------:|:-------------------------|:-----------------------------------------------------------------------------------------|
| global                  | sample_ii_analysis | abstain       |              11460 |        7 |           1.49467 | [1.373, 1.684]    |                 0.117277 |                          0.0359661 |                       -0.00512952 | diagnostic_abstain       | mixed evidence: keep as diagnostic excluded support                                      |
| sample_ii_amplitude_bin | (2000.0, 3000.0]   | abstain       |               6922 |        7 |           1.56003 | [1.382, 1.828]    |               nan        |                        nan         |                      nan          | diagnostic_abstain       | mixed evidence: keep as diagnostic excluded support                                      |
| sample_ii_amplitude_bin | (4000.0, 7000.0]   | abstain       |                 25 |        6 |          11.199   | [7.165, 18.205]   |               nan        |                        nan         |                      nan          | diagnostic_abstain       | mixed evidence: keep as diagnostic excluded support                                      |
| sample_ii_pair          | B4-B6              | abstain       |               3820 |        7 |           1.0389  | [0.782, 1.281]    |               nan        |                        nan         |                      nan          | diagnostic_abstain       | mixed evidence: keep as diagnostic excluded support                                      |
| sample_ii_pair          | B4-B8              | abstain       |               3820 |        7 |           1.07187 | [0.827, 1.321]    |               nan        |                        nan         |                      nan          | diagnostic_abstain       | mixed evidence: keep as diagnostic excluded support                                      |
| sample_ii_pair          | B6-B8              | abstain       |               3820 |        7 |           1.67097 | [1.577, 1.795]    |               nan        |                        nan         |                      nan          | diagnostic_abstain       | mixed evidence: keep as diagnostic excluded support                                      |
| run                     | 63                 | recalibrate   |               1110 |        1 |           1.40432 | [1.366, 1.546]    |                 0.118919 |                          0.0659957 |                       -0.030303   | hard_veto                | S03m flagged recalibration but consumer-native HGB evidence is not a clean recovery      |
| run                     | 64                 | abstain       |                  0 |        0 |         nan       | not estimable     |                 0        |                        nan         |                      nan          | hard_veto                | no or low consumer-native support for a refit                                            |
| sample_ii_amplitude_bin | (3000.0, 4000.0]   | recalibrate   |                867 |        7 |           1.81425 | [1.657, 1.878]    |               nan        |                        nan         |                      nan          | hard_veto                | S03m flagged recalibration but consumer-native HGB evidence is not a clean recovery      |
| sample_ii_amplitude_bin | (999.999, 1500.0]  | recalibrate   |               1145 |        7 |           1.27171 | [1.211, 1.291]    |               nan        |                        nan         |                      nan          | hard_veto                | S03m flagged recalibration but consumer-native HGB evidence is not a clean recovery      |
| run                     | 61                 | recalibrate   |               2799 |        1 |           1.79299 | [1.744, 1.922]    |                 0.131833 |                         -0.0782223 |                       -0.0216802  | recoverable_hgb_refit    | HGB improves excluded-support sigma68 without tail increase at adequate consumer support |

## Systematics and Caveats

- **Raw input:** The selected-pulse count is reproduced from raw ROOT, but the consumer-native join uses previously frozen downstream artifacts. This is deliberate: the ticket asks to acquire or join labels, not to retune all downstream consumers.
- **Split:** The excluded-support ML benchmark is split by held-out run with run-bootstrap confidence intervals. The S03m action table itself was frozen before this ticket.
- **Leakage:** The joined labels are consumer outcomes and support diagnostics; run id and event id are not features in the benchmark winner selection.
- **Interpretability:** The strong traditional comparator remains the hierarchical amplitude/timewalk method. HGB can be recoverable for some strata but is not globally authorized for all S03m exclusions.
- **Support limitation:** Run 64 has no strict B4/B6/B8 same-event support in the S03m endpoint and is therefore a hard veto here, regardless of indirect evidence.
- **Consumer scope:** Pile-up, PID, charge, and energy metrics have different units. The action decision uses timing residual recovery as the common gate and treats consumer-native metrics as external labels/caveats, not as a scalar objective to optimize.

## Verdict

`result.json` names **traditional_hier_amp** as the benchmark winner. The excluded-region label split contains **1** recoverable HGB-refit rows, **4** hard-veto rows, and **6** diagnostic-abstain rows. Production consumers should carry `consumer_native_action` with the S03m row label rather than treating all S03m exclusions as a single abstention class.
