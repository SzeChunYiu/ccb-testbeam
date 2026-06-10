# P07g: saturation recovery acceptance rule from bias envelope

Ticket `1781020303.539.78bf7a44`. Raw Sample-II B-stack ROOT was read directly; no Monte Carlo was used.

## Reproduction first

| quantity                                               | expected             |    reproduced | delta                  | pass   |
|:-------------------------------------------------------|:---------------------|--------------:|:-----------------------|:-------|
| Sample-II B2 selected pulses                           | 88213                | 88213         | 0                      | True   |
| P07e w2_8/gbr_masked res68_abs_frac                    | 0.08142854693675028  |     0.0784709 | -0.0029576342860176408 | True   |
| P07e w2_8/gbr_masked median_bias_frac                  | 0.028761577610479743 |     0.0278757 | -0.000885864813333772  | True   |
| Natural A_B2>=7000 with >=2 downstream selected events | data-derived         |   249         |                        | True   |

## Method

The correction under test is the P07e retained-window `w2_8` B2 recovery. Each held-out run is excluded before fitting the retained-window template/GBR and before calibrating accept/veto thresholds.

- `traditional_envelope`: retained-window robust Huber/template recovery plus fixed cuts on predicted saturation lift, peak sample, corrected q-template RMSE, and B2 odd-duplicate charge consistency.
- `ml_conformal_risk`: retained-window GBR recovery plus a gradient-boosted absolute-error predictor with a train-run conformal residual margin and a catastrophic-error classifier.

Artificial 4000 ADC clipping supplies amplitude truth for accepted-event bias/res68/catastrophic metrics. Natural `A_B2 >= 7000` events with at least two downstream selected B staves supply q-template and timing-tail deltas versus the observed saturated B2 waveform.

## Held-out accept/veto performance

| rule                 |    n |   acceptance_rate | acceptance_rate_ci95                      |   amp_res68_abs_frac | amp_res68_abs_frac_ci95                    |   amp_bias_median_frac |   catastrophic_rate |   q_template_shift_natural |   timing_tail_delta_natural |   calibration_coverage |
|:---------------------|-----:|------------------:|:------------------------------------------|---------------------:|:-------------------------------------------|-----------------------:|--------------------:|---------------------------:|----------------------------:|-----------------------:|
| ml_conformal_risk    | 7625 |          0.448741 | [0.4017962308598351, 0.49414349750479]    |            0.0666105 | [0.06246543479743603, 0.07283969652998146] |             0.0376492  |          0.00839344 |                 0.00719852 |                  -0.0128098 |               0.967869 |
| traditional_envelope | 8760 |          0.515537 | [0.44539584789808917, 0.5987279315150802] |            0.0953872 | [0.09322043009998941, 0.09665471060079311] |            -0.00427067 |          0.006621   |                 0          |                   0         |               0.709132 |

CIs are paired run-block bootstrap 95% intervals over the held-out runs. Calibration coverage is the fraction of accepted artificial events inside the declared 10% error envelope for the traditional rule and inside the ML conformal upper bound for the ML rule.

## Rule parameters

|   run | rule                 |   max_lift |   max_q_rmse |   odd_low |   odd_high |   risk_upper_threshold |   cat_probability_threshold |   conformal_q90 |
|------:|:---------------------|-----------:|-------------:|----------:|-----------:|-----------------------:|----------------------------:|----------------:|
|    58 | traditional_envelope |       0.3  |         0.24 |      0.02 |        1.4 |                 nan    |                      nan    |     nan         |
|    58 | ml_conformal_risk    |     nan    |       nan    |    nan    |      nan   |                   0.16 |                        0.08 |       0.0941387 |
|    59 | traditional_envelope |       0.45 |         0.18 |      0.02 |        1.4 |                 nan    |                      nan    |     nan         |
|    59 | ml_conformal_risk    |     nan    |       nan    |    nan    |      nan   |                   0.16 |                        0.1  |       0.0880401 |
|    60 | traditional_envelope |       0.45 |         0.18 |      0.02 |        1.4 |                 nan    |                      nan    |     nan         |
|    60 | ml_conformal_risk    |     nan    |       nan    |    nan    |      nan   |                   0.16 |                        0.14 |       0.0876709 |
|    61 | traditional_envelope |       0.45 |         0.18 |      0.02 |        1.4 |                 nan    |                      nan    |     nan         |
|    61 | ml_conformal_risk    |     nan    |       nan    |    nan    |      nan   |                   0.16 |                        0.1  |       0.0890971 |
|    62 | traditional_envelope |       0.45 |         0.18 |      0.02 |        1.8 |                 nan    |                      nan    |     nan         |
|    62 | ml_conformal_risk    |     nan    |       nan    |    nan    |      nan   |                   0.16 |                        0.1  |       0.0869226 |
|    63 | traditional_envelope |       0.45 |         0.18 |      0.02 |        1.8 |                 nan    |                      nan    |     nan         |
|    63 | ml_conformal_risk    |     nan    |       nan    |    nan    |      nan   |                   0.16 |                        0.08 |       0.0897581 |
|    65 | traditional_envelope |       0.45 |         0.18 |      0.02 |        1.4 |                 nan    |                      nan    |     nan         |
|    65 | ml_conformal_risk    |     nan    |       nan    |    nan    |      nan   |                   0.16 |                        0.1  |       0.092236  |

## Leakage checks

| run   | check                                    |   value | flag   |
|:------|:-----------------------------------------|--------:|:-------|
| all   | heldout_train_event_overlap              |       0 | False  |
| all   | primary_features_exclude_run_event_truth |       1 | False  |
| all   | too_good_trigger                         |       0 | False  |
| 58    | shuffled_abs_error_risk_acceptance_rate  |       0 | False  |
| 59    | shuffled_abs_error_risk_acceptance_rate  |       0 | False  |
| 60    | shuffled_abs_error_risk_acceptance_rate  |       0 | False  |
| 61    | shuffled_abs_error_risk_acceptance_rate  |       0 | False  |
| 62    | shuffled_abs_error_risk_acceptance_rate  |       0 | False  |
| 63    | shuffled_abs_error_risk_acceptance_rate  |       0 | False  |
| 65    | shuffled_abs_error_risk_acceptance_rate  |       0 | False  |

## Finding

The ML conformal rule accepts 0.449 of held-out artificial rows with amplitude res68 0.0666, median bias 0.0376, catastrophic rate 0.0084, and natural timing-tail delta -0.0128. The traditional envelope accepts 0.516 with res68 0.0954. Preferred rule: ml_conformal_risk.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p07g_1781020303_539_78bf7a44_acceptance_rule.py --config configs/p07g_1781020303_539_78bf7a44_acceptance_rule.json
```
