# S04e: q_template vetoes on B2-containing residual tails

- **Ticket:** `1781028505.1210.78b135ab`
- **Worker:** `testbeam-laptop-1`
- **Config:** `configs/s04e_1781028505_1210_78b135ab_qtemplate_b2_tail_tables.json`
- **Inputs:** raw B-stack ROOT under `data/root/root` and the S01 q_template table.

## Question

Do q_template veto policies that were weak on S03 downstream-only pairs change the full S04/S05 B2-containing pair-residual tail tables by topology?

## Raw ROOT Reproduction First

The gate rebuilds the S05e/S05c B-stack pair table directly from `h101/HRDv`: baseline samples 0-3, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, CFD20 timing, `A > 1000 ADC`, and the configured S04/S05 analysis runs.

| quantity                             | report_value | reproduced | delta | tolerance | pass |
| ------------------------------------ | ------------ | ---------- | ----- | --------- | ---- |
| total_selected_b_pulses              | 640737       | 640737     | 0     | 0         | True |
| sample_i_analysis_b_selected_pulses  | 252266       | 252266     | 0     | 0         | True |
| sample_ii_analysis_b_selected_pulses | 125096       | 125096     | 0     | 0         | True |

Pair-row anchor:

| pair  | n_pair_rows | report_value | delta | tolerance | pass |
| ----- | ----------- | ------------ | ----- | --------- | ---- |
| B2-B4 | 26387       | 26387        | 0     | 0         | True |
| B2-B6 | 12626       | 12626        | 0     | 0         | True |
| B2-B8 | 4943        | 4943         | 0     | 0         | True |
| B4-B6 | 12196       | 12196        | 0     | 0         | True |
| B4-B8 | 4542        | 4542         | 0     | 0         | True |
| B6-B8 | 4790        | 4790         | 0     | 0         | True |

## Held-out Methods

Residuals are scored by held-out run. Each fold computes pair medians, q-thresholds, and RF veto thresholds on train runs only, then applies them to the held-out run. The traditional method is a fixed q-template threshold policy chosen on train rows by topology. The ML method is a RandomForest tail-veto using q-template plus waveform shape summaries; it excludes run, event, raw times, raw residuals, and target residuals. A shuffled-label RF is the leakage/control row.

| method                       | topology        | n_pair_rows | n_runs | retention | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | full_rms_ns | tail_frac_abs_gt5ns | tail_frac_ci_low | tail_frac_ci_high |
| ---------------------------- | --------------- | ----------- | ------ | --------- | ---------- | ----------------- | ------------------ | ----------- | ------------------- | ---------------- | ----------------- |
| raw_no_veto                  | B2_containing   | 43956       | 21     | 1         | 3.52628    | 1.8591            | 19.1812            | 24.8251     | 0.202748            | 0.13146          | 0.345603          |
| raw_no_veto                  | all             | 65484       | 21     | 1         | 2.0905     | 1.79021           | 9.62758            | 20.6803     | 0.141775            | 0.0926718        | 0.248917          |
| raw_no_veto                  | downstream_only | 21528       | 21     | 1         | 1.73937    | 1.69684           | 1.78045            | 6.53768     | 0.0174192           | 0.0137558        | 0.0206266         |
| traditional_q_threshold_veto | B2_containing   | 24260       | 21     | 0.551916  | 1.71971    | 1.47577           | 6.84519            | 19.5407     | 0.114551            | 0.0655247        | 0.228037          |
| traditional_q_threshold_veto | all             | 36013       | 21     | 0.549951  | 1.63125    | 1.49762           | 2.51749            | 16.1008     | 0.0784439           | 0.046154         | 0.171349          |
| traditional_q_threshold_veto | downstream_only | 11753       | 21     | 0.54594   | 1.48648    | 1.44334           | 1.53041            | 2.86191     | 0.00348847          | 0.00201988       | 0.00556069        |
| ml_rf_qtemplate_veto         | B2_containing   | 24735       | 21     | 0.562722  | 1.29867    | 1.26345           | 1.32497            | 1.54265     | 0.00533657          | 0.00303538       | 0.00935495        |
| ml_rf_qtemplate_veto         | all             | 36975       | 21     | 0.564642  | 1.35615    | 1.3214            | 1.405              | 1.51753     | 0.00378634          | 0.00229636       | 0.00625202        |
| ml_rf_qtemplate_veto         | downstream_only | 12240       | 21     | 0.568562  | 1.4186     | 1.37125           | 1.4683             | 1.41564     | 0.000653595         | 0.000120805      | 0.0015787         |
| ml_rf_shuffled_label_control | B2_containing   | 35919       | 21     | 0.817158  | 3.16128    | 1.81109           | 18.3589            | 24.4789     | 0.196191            | 0.12254          | 0.325982          |
| ml_rf_shuffled_label_control | all             | 55091       | 21     | 0.841289  | 2.02871    | 1.74176           | 6.37264            | 20.0837     | 0.133597            | 0.0824942        | 0.224972          |
| ml_rf_shuffled_label_control | downstream_only | 19172       | 21     | 0.890561  | 1.70912    | 1.65315           | 1.76528            | 6.07827     | 0.0165345           | 0.0133548        | 0.0194294         |

By pair:

| method                       | pair  | topology        | n_pair_rows | n_runs | retention | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | full_rms_ns | tail_frac_abs_gt5ns | tail_frac_ci_low | tail_frac_ci_high |
| ---------------------------- | ----- | --------------- | ----------- | ------ | --------- | ---------- | ----------------- | ------------------ | ----------- | ------------------- | ---------------- | ----------------- |
| raw_no_veto                  | B2-B4 | B2_containing   | 26387       | 21     | 0.600305  | 3.44675    | 1.57139           | 19.9673            | 25.4671     | 0.19593             | 0.131239         | 0.323542          |
| raw_no_veto                  | B2-B6 | B2_containing   | 12626       | 21     | 0.287242  | 3.36933    | 2.16909           | 19.4567            | 23.3121     | 0.206875            | 0.133871         | 0.370572          |
| raw_no_veto                  | B2-B8 | B2_containing   | 4943        | 21     | 0.112453  | 4.76499    | 2.51288           | 23.9767            | 25.1053     | 0.228404            | 0.153002         | 0.403446          |
| raw_no_veto                  | B4-B6 | downstream_only | 12196       | 21     | 0.566518  | 1.81483    | 1.75116           | 1.86137            | 6.44232     | 0.0177927           | 0.013872         | 0.0215488         |
| raw_no_veto                  | B4-B8 | downstream_only | 4542        | 21     | 0.210981  | 2.03556    | 1.94942           | 2.09316            | 8.1716      | 0.0264201           | 0.0199202        | 0.0335394         |
| raw_no_veto                  | B6-B8 | downstream_only | 4790        | 21     | 0.222501  | 1.32261    | 1.27084           | 1.38195            | 4.80667     | 0.00772443          | 0.00459825       | 0.0115394         |
| traditional_q_threshold_veto | B2-B4 | B2_containing   | 14798       | 21     | 0.336655  | 1.45024    | 1.25636           | 6.58118            | 19.5013     | 0.105014            | 0.0592878        | 0.215307          |
| traditional_q_threshold_veto | B2-B6 | B2_containing   | 6907        | 20     | 0.157134  | 1.91762    | 1.68554           | 7.82184            | 18.6264     | 0.118865            | 0.0661831        | 0.245471          |
| traditional_q_threshold_veto | B2-B8 | B2_containing   | 2555        | 20     | 0.0581263 | 2.47855    | 2.0238            | 19.7678            | 21.9589     | 0.156947            | 0.0922276        | 0.320329          |
| traditional_q_threshold_veto | B4-B6 | downstream_only | 6737        | 21     | 0.312941  | 1.46094    | 1.4054            | 1.52135            | 2.01934     | 0.00282025          | 0.000965707      | 0.00524282        |
| traditional_q_threshold_veto | B4-B8 | downstream_only | 2336        | 21     | 0.10851   | 1.72048    | 1.62219           | 1.78651            | 4.36403     | 0.00556507          | 0.00206644       | 0.00989483        |
| traditional_q_threshold_veto | B6-B8 | downstream_only | 2680        | 21     | 0.124489  | 1.34869    | 1.2786            | 1.41727            | 3.00455     | 0.00410448          | 0.00107802       | 0.00756399        |
| ml_rf_qtemplate_veto         | B2-B4 | B2_containing   | 14544       | 21     | 0.330876  | 1.09213    | 1.05634           | 1.12328            | 1.38376     | 0.00453795          | 0.00231089       | 0.00854089        |
| ml_rf_qtemplate_veto         | B2-B6 | B2_containing   | 7384        | 20     | 0.167986  | 1.58865    | 1.5369            | 1.63962            | 1.69489     | 0.00487541          | 0.0024486        | 0.00863381        |
| ml_rf_qtemplate_veto         | B2-B8 | B2_containing   | 2807        | 20     | 0.0638593 | 1.77491    | 1.68132           | 1.85065            | 1.86675     | 0.0106876           | 0.00509933       | 0.0224959         |
| ml_rf_qtemplate_veto         | B4-B6 | downstream_only | 6711        | 21     | 0.311734  | 1.40257    | 1.32833           | 1.46335            | 1.37803     | 0.000596036         | 0                | 0.00160005        |
| ml_rf_qtemplate_veto         | B4-B8 | downstream_only | 2516        | 21     | 0.116871  | 1.63389    | 1.54391           | 1.70556            | 1.56564     | 0                   | 0                | 0                 |
| ml_rf_qtemplate_veto         | B6-B8 | downstream_only | 3013        | 21     | 0.139957  | 1.27078    | 1.21825           | 1.33705            | 1.34118     | 0.00132758          | 0                | 0.00323082        |
| ml_rf_shuffled_label_control | B2-B4 | B2_containing   | 21800       | 21     | 0.49595   | 2.99202    | 1.51329           | 18.5814            | 24.9143     | 0.189174            | 0.119911         | 0.312626          |
| ml_rf_shuffled_label_control | B2-B6 | B2_containing   | 10190       | 20     | 0.231823  | 3.00141    | 2.13884           | 19.056             | 23.1451     | 0.199706            | 0.132116         | 0.36204           |
| ml_rf_shuffled_label_control | B2-B8 | B2_containing   | 3929        | 20     | 0.0893848 | 4.77366    | 2.45568           | 25.9511            | 25.3745     | 0.226012            | 0.148553         | 0.418847          |
| ml_rf_shuffled_label_control | B4-B6 | downstream_only | 10973       | 21     | 0.509708  | 1.78612    | 1.69521           | 1.84249            | 5.87723     | 0.0162216           | 0.012442         | 0.0203026         |
| ml_rf_shuffled_label_control | B4-B8 | downstream_only | 3953        | 21     | 0.183621  | 2.02627    | 1.91462           | 2.1039             | 7.47047     | 0.0265621           | 0.0194559        | 0.0329685         |
| ml_rf_shuffled_label_control | B6-B8 | downstream_only | 4246        | 21     | 0.197232  | 1.3094     | 1.26254           | 1.37085            | 5.0587      | 0.00800754          | 0.00453098       | 0.0123036         |

Delta versus no veto:

| comparison                                     | topology        | delta_sigma68_ns | delta_tail_frac_abs_gt5ns | retention |
| ---------------------------------------------- | --------------- | ---------------- | ------------------------- | --------- |
| traditional_q_threshold_veto_minus_raw_no_veto | all             | -0.459259        | -0.0633312                | 0.549951  |
| ml_rf_qtemplate_veto_minus_raw_no_veto         | all             | -0.734358        | -0.137989                 | 0.564642  |
| ml_rf_shuffled_label_control_minus_raw_no_veto | all             | -0.0617902       | -0.00817795               | 0.841289  |
| traditional_q_threshold_veto_minus_raw_no_veto | B2_containing   | -1.80657         | -0.0881975                | 0.551916  |
| ml_rf_qtemplate_veto_minus_raw_no_veto         | B2_containing   | -2.22761         | -0.197412                 | 0.562722  |
| ml_rf_shuffled_label_control_minus_raw_no_veto | B2_containing   | -0.364995        | -0.00655677               | 0.817158  |
| traditional_q_threshold_veto_minus_raw_no_veto | downstream_only | -0.25289         | -0.0139307                | 0.54594   |
| ml_rf_qtemplate_veto_minus_raw_no_veto         | downstream_only | -0.320778        | -0.0167656                | 0.568562  |
| ml_rf_shuffled_label_control_minus_raw_no_veto | downstream_only | -0.0302493       | -0.000884646              | 0.890561  |

## Leakage Checks

| check                                             | value      | pass | interpretation                                                                                            |
| ------------------------------------------------- | ---------- | ---- | --------------------------------------------------------------------------------------------------------- |
| run_split_event_overlap                           | 0          | True | whole runs are held out before q thresholds and RF models are fit                                         |
| ml_forbidden_feature_intersection                 |            | True | production ML excludes run, event, raw time, raw residual, target residual, and full-sample pair residual |
| qtemplate_join_missing_pair_rows                  | 156        | True | small unmatched S01 q_template support is median-filled and reported; threshold is <=0.5% of pair rows    |
| qtemplate_join_missing_pair_fraction              | 0.00238226 | True | fraction of pair rows with at least one missing q_template side after run/EVT/stave aggregation           |
| shuffled_label_control_not_better_than_ml_b2_tail | 0.190855   | True | a shuffled-label RF should not reduce B2 tail fraction more than the nominal RF                           |
| ml_not_unphysical_zero_width                      | 1.29867    | True | guards against accidental target echo leakage                                                             |

## Finding

The q-template policies mostly act as B2/topology pathology vetoes, not as a clean downstream timing-quality improvement. B2-containing rows start with the largest `abs > 5 ns` tail fraction and receive the visible tail reduction, but only after rejecting a material fraction of the table. Downstream-only rows have small raw tails, so q-template vetoes have little room to improve them. The RF veto is useful as a diagnostic because it is run-held-out and beats the shuffled-label control where it matters, but it should be treated as a veto/support map, not a replacement residual correction. The q-template join leaves `156` pair rows (`0.238%`) with at least one unmatched side after the necessary `run/EVT/stave` aggregation; those rows are median-filled and tracked as a support limitation.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s04e_1781028505_1210_78b135ab_qtemplate_b2_tail_tables.py --config configs/s04e_1781028505_1210_78b135ab_qtemplate_b2_tail_tables.json
```
