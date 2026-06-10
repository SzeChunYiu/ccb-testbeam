# S03c follow-up: train-only run-family covariates

- **Ticket:** 1781020939.1214.51534983
- **Follow-up to:** 1781011359.822.3751464b
- **Worker:** testbeam-laptop-3
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Bootstrap:** resample held-out runs, not individual residuals
- **Config:** `configs/s03c_1781020939_1214_51534983_run_family_covariates.yaml`

## Question

Does the S03c Ridge residual correction gain persist after adding run-family nuisance summaries, when those summaries are computed only from training runs for every held-out-run fold?

## Raw reproduction gate

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a run-65 anchor was reproduced from the same raw pass.

| method                     |   value |   ci_low |   ci_high |   n_pair_residuals |   s03a_report_value |   delta_ns | pass   |
|:---------------------------|--------:|---------:|----------:|-------------------:|--------------------:|-----------:|:-------|
| template_phase_base        | 2.88915 |  2.63915 |   3.20541 |                198 |             2.88915 |          0 | True   |
| analytic_timewalk          | 1.49464 |  1.3419  |   1.64288 |                198 |             1.49464 |          0 | True   |
| s03b_binned_timewalk       | 1.56958 |  1.35928 |   1.81958 |                198 |             1.56958 |          0 | True   |
| ml_ridge_on_template_phase | 1.39153 |  1.30313 |   1.58629 |                198 |             1.39153 |          0 | True   |

The prior S03c follow-up number was then rederived before the new covariate test.

| method              |   s03c_reference_value |   reproduced_value |   delta_ns | pass   |
|:--------------------|-----------------------:|-------------------:|-----------:|:-------|
| template_phase_base |                2.74141 |            2.74141 |          0 | True   |
| ml_ridge_no_family  |                1.53692 |            1.53692 |          0 | True   |

## Methods

The traditional comparator is the established analytic timewalk Ridge plus a low-dimensional analytic Ridge using amplitude/rise/stave features and train-only run-family summaries. The ML method is the waveform-feature Ridge residual corrector with the same train-only summary block. Summary covariates include per-family, per-stave training residual medians/IQRs and amplitude/shape support summaries; no held-out run rows enter these summaries, including inside inner CV.

## Held-out run results

|   heldout_run | method                           |   value |   ci_low |   ci_high |   n_pair_residuals | analytic_candidate   |   analytic_alpha |   traditional_family_alpha |   ml_family_alpha |
|--------------:|:---------------------------------|--------:|---------:|----------:|-------------------:|:---------------------|-----------------:|---------------------------:|------------------:|
|            58 | analytic_timewalk                | 1.18748 |  1.13394 |   1.35829 |                219 | amp_only             |              100 |                        100 |               100 |
|            58 | ml_ridge_no_family               | 1.27047 |  1.15566 |   1.42137 |                219 | amp_only             |              100 |                        100 |               100 |
|            58 | ml_waveform_family_summary_ridge | 1.27697 |  1.16119 |   1.42758 |                219 | amp_only             |              100 |                        100 |               100 |
|            58 | template_phase_base              | 2.6428  |  2.6428  |   2.77317 |                219 | amp_only             |              100 |                        100 |               100 |
|            58 | traditional_family_summary_ridge | 1.40986 |  1.25226 |   1.60024 |                219 | amp_only             |              100 |                        100 |               100 |
|            59 | analytic_timewalk                | 1.45871 |  1.39611 |   1.52426 |               2289 | amp_only             |              100 |                         10 |               100 |
|            59 | ml_ridge_no_family               | 1.49843 |  1.43218 |   1.55618 |               2289 | amp_only             |              100 |                         10 |               100 |
|            59 | ml_waveform_family_summary_ridge | 1.5115  |  1.44745 |   1.56946 |               2289 | amp_only             |              100 |                         10 |               100 |
|            59 | template_phase_base              | 2.99232 |  2.99232 |   3.12333 |               2289 | amp_only             |              100 |                         10 |               100 |
|            59 | traditional_family_summary_ridge | 1.71278 |  1.64458 |   1.76016 |               2289 | amp_only             |              100 |                         10 |               100 |
|            60 | analytic_timewalk                | 1.3437  |  1.28679 |   1.40042 |               2424 | amp_only             |              100 |                        100 |               100 |
|            60 | ml_ridge_no_family               | 1.30605 |  1.2663  |   1.34788 |               2424 | amp_only             |              100 |                        100 |               100 |
|            60 | ml_waveform_family_summary_ridge | 1.27513 |  1.23154 |   1.31867 |               2424 | amp_only             |              100 |                        100 |               100 |
|            60 | template_phase_base              | 2.66393 |  2.66393 |   2.7113  |               2424 | amp_only             |              100 |                        100 |               100 |
|            60 | traditional_family_summary_ridge | 1.37048 |  1.31802 |   1.42213 |               2424 | amp_only             |              100 |                        100 |               100 |
|            61 | analytic_timewalk                | 2.12996 |  1.99183 |   2.20856 |               2799 | amp_only             |              100 |                        100 |               100 |
|            61 | ml_ridge_no_family               | 1.96998 |  1.89338 |   2.0593  |               2799 | amp_only             |              100 |                        100 |               100 |
|            61 | ml_waveform_family_summary_ridge | 1.96377 |  1.88676 |   2.05137 |               2799 | amp_only             |              100 |                        100 |               100 |
|            61 | template_phase_base              | 2.70351 |  2.70351 |   2.70351 |               2799 | amp_only             |              100 |                        100 |               100 |
|            61 | traditional_family_summary_ridge | 2.17551 |  2.11289 |   2.25412 |               2799 | amp_only             |              100 |                        100 |               100 |
|            62 | analytic_timewalk                | 1.469   |  1.41729 |   1.51851 |               2421 | amp_only             |              100 |                        100 |               100 |
|            62 | ml_ridge_no_family               | 1.44698 |  1.39192 |   1.50556 |               2421 | amp_only             |              100 |                        100 |               100 |
|            62 | ml_waveform_family_summary_ridge | 1.31688 |  1.26761 |   1.37696 |               2421 | amp_only             |              100 |                        100 |               100 |
|            62 | template_phase_base              | 2.90117 |  2.90117 |   3.02631 |               2421 | amp_only             |              100 |                        100 |               100 |
|            62 | traditional_family_summary_ridge | 1.43266 |  1.37097 |   1.49211 |               2421 | amp_only             |              100 |                        100 |               100 |
|            63 | analytic_timewalk                | 1.39132 |  1.31062 |   1.46447 |               1110 | amp_only             |              100 |                        100 |               100 |
|            63 | ml_ridge_no_family               | 1.37073 |  1.28924 |   1.43801 |               1110 | amp_only             |              100 |                        100 |               100 |
|            63 | ml_waveform_family_summary_ridge | 1.35802 |  1.28869 |   1.41876 |               1110 | amp_only             |              100 |                        100 |               100 |
|            63 | template_phase_base              | 2.87872 |  2.87872 |   3.01249 |               1110 | amp_only             |              100 |                        100 |               100 |
|            63 | traditional_family_summary_ridge | 1.4364  |  1.376   |   1.51409 |               1110 | amp_only             |              100 |                        100 |               100 |
|            65 | analytic_timewalk                | 1.49464 |  1.33356 |   1.63452 |                198 | amp_only             |              100 |                        100 |               100 |
|            65 | ml_ridge_no_family               | 1.39153 |  1.29753 |   1.58739 |                198 | amp_only             |              100 |                        100 |               100 |
|            65 | ml_waveform_family_summary_ridge | 1.39695 |  1.30268 |   1.59239 |                198 | amp_only             |              100 |                        100 |               100 |
|            65 | template_phase_base              | 2.88915 |  2.63915 |   3.20541 |                198 | amp_only             |              100 |                        100 |               100 |
|            65 | traditional_family_summary_ridge | 1.53054 |  1.35683 |   1.72867 |                198 | amp_only             |              100 |                        100 |               100 |

Pooled intervals resample the seven held-out runs.

| method                           |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| ml_waveform_family_summary_ridge | 1.51164 |  1.32842 |   1.81355 |              11460 |             0.0176265 |
| ml_ridge_no_family               | 1.53692 |  1.34421 |   1.80907 |              11460 |             0.0173647 |
| analytic_timewalk                | 1.55109 |  1.37007 |   1.92518 |              11460 |             0.0191099 |
| traditional_family_summary_ridge | 1.67619 |  1.41509 |   1.94787 |              11460 |             0.0189354 |
| template_phase_base              | 2.74141 |  2.68422 |   2.98617 |              11460 |             0.0813264 |

## Leakage checks

Every promoted split is by run. The family summaries are recomputed from training runs only, event-id train/held-out overlap is audited, and shuffled-target controls rebuild both the fitted target and target-derived summary covariates from shuffled training targets.

| check                                                |   min_sigma68_ns |   median_sigma68_ns |   max_sigma68_ns |
|:-----------------------------------------------------|-----------------:|--------------------:|-----------------:|
| analytic_timewalk_shuffled_target                    |          2.58932 |             2.85011 |          3.04719 |
| feature_audit_no_run_event_order_or_cross_stave_time |          0       |             0       |          0       |
| ml_family_summary_shuffled_target                    |          2.66408 |             2.88749 |          3.02873 |
| template_phase                                       |          2.6428  |             2.87872 |          2.99232 |
| traditional_family_summary_shuffled_target           |          2.64659 |             2.88652 |          3.08837 |
| train_heldout_event_id_overlap                       |          0       |             0       |          0       |

## Verdict

Template phase is `2.741 ns` with run-bootstrap CI `[2.684, 2.986] ns`.
The no-family S03c Ridge reproduction is `1.537 ns`, matching the prior `1.537 ns` reference within `0 ns`.
The traditional family-summary Ridge is `1.676 ns` with CI `[1.415, 1.948] ns`.
The ML waveform family-summary Ridge is `1.512 ns` with CI `[1.328, 1.814] ns`, a gain of `1.230 ns` versus template phase.
Conclusion: `ridge_gain_persists_with_train_only_run_family_covariates_no_leakage_flag`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03c_1781020939_1214_51534983_run_family_covariates.py --config configs/s03c_1781020939_1214_51534983_run_family_covariates.yaml
```
