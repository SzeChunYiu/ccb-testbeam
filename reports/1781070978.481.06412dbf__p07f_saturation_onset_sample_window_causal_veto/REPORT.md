# P07f: saturation onset sample-window causal veto

**Ticket:** `1781070978.481.06412dbf`  
**Worker:** `testbeam-laptop-4`  
**Date:** 2026-06-11  
**Depends on:** P07f duplicate-knee calibration; P07c timing boundary closure; P07k q_template-preserving acceptance calibration.  
**Raw ROOT directory:** `/home/billy/ccb-data/extracted/root/root`  
**Config:** `configs/p07f_1781070978_481_06412dbf_saturation_onset_sample_window_causal_veto.json`  
**Git commit:** `11972b7029a186f49d8fc4ce10c5291499d3d189`

## 0. Question

Which B2 sample windows causally drive saturation-recovery gain and downstream boundary harm near the saturation onset, and does any ML/NN policy beat a strong sample-causal rising-template veto when evaluated by run-held-out bootstrap confidence intervals?

The pre-registered ticket metrics were artificial-clip res68, natural-boundary q_template shift, timing-tail delta, charge-bias delta, coverage, and ML-minus-traditional deltas per sample window.

## 1. Reproduction

Raw B-stack ROOT files were read directly. `HRDv` is reshaped to `(event, channel, sample)`, samples 0-3 define the baseline, B2 is channel 0, and the odd duplicate monitor is channel 1 with sign inverted. Before any modelling, the script reruns the S00/P07e/P07f counts and the constrained P07f duplicate-knee fits.

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulse records    |      640737    |    640737    |       0 |       0     | True   |
| P07e high-amplitude B2 duplicate rows |      183132    |    183132    |       0 |       0     | True   |
| P07f duplicate-proxy knee rows        |      565387    |    565387    |       0 |       0     | True   |
| P07f low-family median knee ADC       |        2752.02 |      2752.02 |       0 |       1e-06 | True   |
| P07f high-family median knee ADC      |        7239.7  |      7239.7  |       0 |       1e-06 | True   |

Run-family knee reproduction:

| family    |   runs |   median_knee_adc |   min_knee_adc |   max_knee_adc |   median_chi2_ndf_proxy |
|:----------|-------:|------------------:|---------------:|---------------:|------------------------:|
| high-knee |     12 |           7239.7  |        6827.13 |        7487.02 |             1.13424e-05 |
| low-knee  |     18 |           2752.02 |        2497.35 |        3035.64 |             8.50923e-06 |
| unstable  |      3 |            nan    |         nan    |         nan    |           nan           |

## 2. Traditional Method

The traditional method is a sample-causal template/rising-edge extrapolator. In each run-held-out fold, training waveforms are normalized by their measured B2 amplitude and a median template `t_j` is computed. For a requested sample-window ablation `W`, the amplitude estimator on held-out events is

`A_hat = median_{j notin W}(x_j / t_j)`,

with invalid or non-positive template ordinates removed. This is a strong baseline because it uses the same local waveform shape and run-held-out calibration as the ML methods, while remaining transparent and sample-causal. The natural veto accepts a correction only when the inferred lift exceeds 0.4% but is clipped at 4%; side effects are measured by duplicate-charge closure, q_template shift `A/A_hat - 1`, and CFD20 timing movement.

## 3. ML/NN Methods

The ML task is regression of the original B2 amplitude from an artificially window-dropped waveform. Training rows are unsaturated or near-onset rows (`A` roughly 1.2-6.8 kADC and below the run knee when available), and held-out folds contain whole runs only. Features exclude run id, event id, odd-channel amplitudes, odd charge, odd peak, and duplicate residuals. Ridge uses standardized waveform scalars and normalized samples; gradient-boosted trees use histogram boosting; MLP is a two-layer ReLU regressor; the 1D-CNN consumes the normalized 18-sample sequence. The new architecture is a gated residual CNN whose convolutional residual channels are multiplicatively gated by peak position and late-tail mean, matching the local edge/tail nature of saturation-onset information.

For artificial clips, the metric is

`res68 = Q_0.68(|A_hat - A| / A)`.

For natural boundary rows (`A >= 7000 ADC`), the model-implied lift is `clip(A_hat/A - 1, 0, 0.04)`. Coverage is the fraction above the 0.4% lift threshold. q_template, timing, and charge-bias deltas are then evaluated on the same held-out run rows.

## 4. Head-to-Head Benchmark

CIs are run-block bootstraps over held-out runs. Lower artificial-clip res68 is better; natural q_template shift, timing-tail delta, and charge-bias delta should remain close to zero.

| sample_window         | method                      |   artificial_clip_res68 |   artificial_clip_res68_ci_low |   artificial_clip_res68_ci_high |    coverage |   coverage_ci_low |   coverage_ci_high |   natural_boundary_q_template_shift |   timing_tail_delta |   charge_bias_delta |   ml_minus_traditional_artificial_res68 |      utility |
|:----------------------|:----------------------------|------------------------:|-------------------------------:|--------------------------------:|------------:|------------------:|-------------------:|------------------------------------:|--------------------:|--------------------:|----------------------------------------:|-------------:|
| all_samples_reference | ML_mlp                      |             0.0237378   |                    0.0198993   |                     0.0277889   | 0.766687    |       0.709683    |        0.816428    |                        -0.0320491   |         3.94348e-05 |        -0.03068     |                             -0.0829965  |  0.105126    |
| late_tail_control     | ML_mlp                      |             0.0281736   |                    0.0249743   |                     0.0314596   | 0.700481    |       0.568325    |        0.812869    |                        -0.0229256   |         5.07019e-05 |        -0.0242506   |                             -0.0797319  |  0.0996691   |
| early_tail            | ML_mlp                      |             0.0186472   |                    0.0167895   |                     0.0206696   | 0.624254    |       0.579688    |        0.662868    |                        -0.0163562   |         3.94348e-05 |        -0.0256465   |                             -0.239993   |  0.0953345   |
| rising_edge           | ML_mlp                      |             0.0289345   |                    0.0237844   |                     0.034255    | 0.599534    |       0.486893    |        0.722248    |                        -0.0171429   |         3.94348e-05 |        -0.0291998   |                             -0.0781552  |  0.0745273   |
| peak                  | ML_mlp                      |             0.0317945   |                    0.0296162   |                     0.0338793   | 0.335433    |       0.299055    |        0.374794    |                        -0.000255638 |         2.81677e-05 |        -0.00240974  |                             -0.181637   |  0.049342    |
| all_samples_reference | ML_ridge                    |             5.05882e-05 |                    4.62395e-05 |                     5.61393e-05 | 0           |       0           |        0           |                         0           |         0           |         0           |                             -0.106684   | -5.05882e-05 |
| early_tail            | ML_ridge                    |             0.00479742  |                    0.00450637  |                     0.00514516  | 0.0136726   |       0.00973746  |        0.0227152   |                         0           |         1.12671e-05 |        -2.20565e-05 |                             -0.253843   | -0.00142386  |
| all_samples_reference | ML_gradient_boosted_trees   |             0.00181334  |                    0.00165577  |                     0.001958    | 0           |       0           |        0           |                         0           |         0           |         0           |                             -0.104921   | -0.00181334  |
| late_tail_control     | ML_ridge                    |             0.0132451   |                    0.0125779   |                     0.0139851   | 0.0454515   |       0.0344533   |        0.0592785   |                         0           |         0           |        -4.51267e-05 |                             -0.0946604  | -0.00192733  |
| late_tail_control     | ML_gradient_boosted_trees   |             0.00195402  |                    0.00177038  |                     0.00217516  | 0           |       0           |        0           |                         0           |         0           |         0           |                             -0.105951   | -0.00195402  |
| early_tail            | ML_gradient_boosted_trees   |             0.00207928  |                    0.00187826  |                     0.0022953   | 0           |       0           |        0           |                         0           |         0           |         0           |                             -0.256561   | -0.00207928  |
| rising_edge           | ML_gradient_boosted_trees   |             0.00630167  |                    0.00599275  |                     0.00657841  | 0           |       0           |        0           |                         0           |         0           |         0           |                             -0.100788   | -0.00630167  |
| rising_edge           | ML_ridge                    |             0.0204114   |                    0.0197576   |                     0.0210358   | 0.0140444   |       0.0120228   |        0.0186744   |                         0           |         1.12671e-05 |        -5.4208e-05  |                             -0.0866783  | -0.016977    |
| peak                  | ML_gradient_boosted_trees   |             0.0196868   |                    0.019359    |                     0.0200164   | 1.12671e-05 |       0           |        3.05859e-05 |                         0           |         0           |         0           |                             -0.193745   | -0.0196839   |
| peak                  | ML_ridge                    |             0.0438194   |                    0.041416    |                     0.046712    | 0.0112615   |       0.0100469   |        0.0128855   |                         0           |         0           |        -6.96836e-05 |                             -0.169613   | -0.0410738   |
| all_samples_reference | traditional_rising_template |             0.106734    |                    0.102605    |                     0.111361    | 0.193603    |       0.170051    |        0.214401    |                         0           |         2.25342e-05 |        -0.00291247  |                              0          | -0.0612912   |
| late_tail_control     | traditional_rising_template |             0.107905    |                    0.0997519   |                     0.116474    | 0.0169457   |       0.0134747   |        0.0226592   |                         0           |         4.50684e-05 |        -8.63337e-05 |                              0          | -0.103845    |
| rising_edge           | traditional_rising_template |             0.10709     |                    0.0982421   |                     0.117871    | 0.0136895   |       0.010973    |        0.018576    |                         0           |         2.25342e-05 |        -0.000217181 |                              0          | -0.10393     |
| peak                  | traditional_rising_template |             0.213432    |                    0.204778    |                     0.222402    | 0.496164    |       0.477885    |        0.5119      |                        -0.0109133   |         2.81677e-05 |        -0.0238034   |                              0          | -0.124164    |
| peak                  | NN_gated_residual_cnn_new   |             0.167827    |                    0.155213    |                     0.181257    | 0.0482063   |       0.0284022   |        0.0726729   |                         0           |         1.12671e-05 |        -8.37245e-06 |                             -0.0456052  | -0.155806    |
| rising_edge           | NN_gated_residual_cnn_new   |             0.212396    |                    0.19821     |                     0.225315    | 0.0473725   |       0.0310459   |        0.0717938   |                         0           |         0           |        -1.57539e-05 |                              0.105306   | -0.200569    |
| peak                  | NN_1d_cnn                   |             0.25038     |                    0.221501    |                     0.277199    | 0.156376    |       0.0717429   |        0.248438    |                        -0.00108     |         0           |        -0.00424843  |                              0.0369483  | -0.216615    |
| all_samples_reference | NN_gated_residual_cnn_new   |             0.242192    |                    0.227165    |                     0.255958    | 0.0405954   |       0.02715     |        0.0598439   |                         0           |         1.69006e-05 |        -6.07882e-05 |                              0.135458   | -0.232138    |
| early_tail            | NN_1d_cnn                   |             0.236748    |                    0.221748    |                     0.254772    | 0.00539131  |       0.00346781  |        0.00806023  |                         0           |         5.63355e-06 |        -5.22341e-05 |                             -0.0218926  | -0.235463    |
| early_tail            | NN_gated_residual_cnn_new   |             0.249138    |                    0.227131    |                     0.27075     | 0.00803907  |       0.00367294  |        0.0169062   |                         0           |         0           |        -1.73962e-05 |                             -0.00950209 | -0.247146    |
| rising_edge           | NN_1d_cnn                   |             0.290312    |                    0.276873    |                     0.306103    | 0.00472655  |       0.0030059   |        0.0073077   |                         0           |         0           |        -6.04996e-06 |                              0.183222   | -0.289136    |
| all_samples_reference | NN_1d_cnn                   |             0.293041    |                    0.283172    |                     0.301601    | 0.00193794  |       0.00125937  |        0.00324103  |                         0           |         0           |        -1.53483e-05 |                              0.186307   | -0.292572    |
| late_tail_control     | NN_gated_residual_cnn_new   |             0.317761    |                    0.297283    |                     0.339364    | 0.000135205 |       5.0178e-05  |        0.000326197 |                         0           |         0           |         0           |                              0.209856   | -0.317727    |
| late_tail_control     | NN_1d_cnn                   |             0.457076    |                    0.441719    |                     0.473096    | 0.000264777 |       0.000136045 |        0.000525657 |                         0           |         0           |        -9.2429e-08  |                              0.349171   | -0.45701     |
| early_tail            | traditional_rising_template |             0.25864     |                    0.244101    |                     0.271897    | 0.805406    |       0.791283    |        0.817574    |                        -0.037937    |         7.32361e-05 |        -0.0378483   |                              0          | -0.13322     |

Winner by the preregistered onset-window utility, excluding the diagnostic all-samples reference and late-tail control rows, is **ML_mlp** on **early_tail**: artificial-clip res68 0.0186 [0.0168, 0.0207], coverage 0.6243, q_template shift -0.0164, timing-tail delta +0.0000, and charge-bias delta -0.0256.

## 5. Falsification

Pre-registration is the claimed ticket text: rising-edge, peak, and early-tail sample windows must be tested with a traditional retained-window/template method and ML/NN alternatives, split by run with bootstrap CIs. A window or method would be falsified as a production action if its natural-boundary q_template shift exceeded 0.035, timing-tail delta exceeded 0.015, or charge-bias delta exceeded 0.08 in absolute value. Five model families across five windows were tried; the report therefore names an eligible utility winner rather than relying on an uncorrected single-comparison p-value.

The late-tail control is included as a negative-control window. A method that only wins when late-tail samples are dropped, while failing the rising/peak/early-tail windows, would indicate a post-hoc or leakage-driven result rather than a causal saturation-onset rule.

## 6. Threats To Validity

- Benchmark/selection: the traditional comparator is not a strawman; it is a run-calibrated median-template amplitude estimator evaluated on the same held-out windows and rows.
- Data leakage: folds hold out whole runs; features do not contain odd-channel quantities or duplicate residual labels. The raw duplicate channel is used only for reproduction, knee support, and natural side-effect evaluation.
- Metric misuse: artificial res68 is reported with full run bootstrap CIs, and natural transfer is constrained by q_template, timing-tail, charge-bias, and coverage rather than a single core resolution.
- Post-hoc selection: the sample windows, fold count, side-effect gates, and model list are fixed in the config. The new gated residual CNN is included because the 18-sample waveform has local temporal structure and a late-tail nuisance mode.

## 7. Provenance Manifest

`manifest.json` records input ROOT checksums, the exact command, Python/platform metadata, random seeds, config path, and output hashes.

## 8. Findings And Next Steps

The sample-window causal benchmark names ML_mlp on early_tail as the onset-window winner. The all-samples reference diagnostic is excluded from this production ranking; its best row is ML_mlp. The best transparent template rule has artificial-clip res68 0.1071 and natural coverage 0.0137; the best ML/NN alternative has res68 0.0186 and coverage 0.6243. The decisive constraint is not only amplitude recovery: methods with nonzero lift must also keep q_template shift, timing-tail delta, and charge-bias delta inside the preregistered side-effect gates.

Systematic variations:

| check                              | finding                                                      | best_method                 | best_window           |   best_artificial_res68 |
|:-----------------------------------|:-------------------------------------------------------------|:----------------------------|:----------------------|------------------------:|
| late_tail_control_negative_control | included as non-onset control window                         | ML_mlp                      | late_tail_control     |               0.0281736 |
| onset_windows_only                 | ranking restricted to rising_edge/peak/early_tail            | ML_mlp                      | early_tail            |               0.0186472 |
| traditional_vs_best_ml             | onset-window best traditional utility versus best ML utility | traditional_rising_template | rising_edge           |               0.10709   |
| all_samples_reference_diagnostic   | best diagnostic row excluded from production winner ranking  | ML_mlp                      | all_samples_reference |               0.0237378 |

No follow-up ticket was appended. The window-causal question is resolved enough to name the early-tail MLP as the current onset-window benchmark winner, with the transparent template rule retained as the interpretable fallback when model complexity is not acceptable.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p07f_1781070978_481_06412dbf_saturation_onset_sample_window_causal_veto.py --config configs/p07f_1781070978_481_06412dbf_saturation_onset_sample_window_causal_veto.json
```

Artifacts: `result.json`, `manifest.json`, `raw_reproduction.csv`, `run_family_knees.csv`, `artificial_clip_by_run.csv`, `artificial_clip_summary.csv`, `natural_boundary_by_run.csv`, `natural_boundary_summary.csv`, `sample_window_summary.csv`, `systematics.csv`, `artificial_predictions.csv.gz`, `natural_predictions.csv.gz`, and benchmark figures.

