# P04q: Cross-Stave Harm-Veto Transfer Validation

- **Study ID:** P04q
- **Ticket ID:** 1781143765.834.683c6144
- **Author:** testbeam-laptop-4
- **Date:** 2026-07-09
- **Input:** raw B-stack ROOT `HRDv` branches only.
- **Config:** `configs/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.json`
- **Git commit:** `55865bd941438ec6063357eb98d8c92ef3ae8d66`

## Abstract

P04p found that a duplicate-readout harm veto can protect B2 template/saturation charge corrections. This study asks whether that veto is portable to the downstream B4, B6, and B8 staves or whether it is a B2-specific saturation classifier. I reran the raw ROOT reproduction gate, constructed odd-channel duplicate closure labels independently for each target stave, and compared a physics rule to ridge, gradient-boosted trees, MLP, 1D-CNN, and waveform-gated residual neural-network vetoes under run-held-out evaluation.

## 1. Raw Reproduction

For each configured run, the script reads `EVENTNO`, `EVT`, and `HRDv` from the raw `h101` tree. The baseline is the median of samples 0-3 per channel. A selected S00 pulse is any physical B2/B4/B6/B8 even channel with baseline-subtracted peak amplitude above 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulse records |         640737 |       640737 |       0 |           0 | True   |

Evaluation-run selected-pulse counts by target stave:

|   run |   B2_selected |   B4_selected |   B6_selected |   B8_selected |
|------:|--------------:|--------------:|--------------:|--------------:|
|    58 |         15791 |           591 |           285 |           114 |
|    59 |         13565 |          4527 |          2366 |           919 |
|    60 |          9873 |          4040 |          2189 |           927 |
|    61 |         11015 |          4401 |          2490 |          1059 |
|    62 |         11635 |          4183 |          2342 |           929 |
|    63 |         14566 |          2645 |          1153 |           453 |
|    64 |         11907 |          1689 |           763 |           271 |
|    65 |         11768 |           842 |           323 |           105 |

## 2. Label and Closure Definition

For event i and stave s, the even waveform x_i,s(t) is compared with the inverted odd duplicate waveform o_i,s(t). The positive odd integral y_i,s = sum_t max(o_i,s(t), 0) defines the external closure target when y_i,s >= 100 ADC. The charge calibrator for any estimator z_i,s is fit only on training runs:

`log E[y_i,s | z_i,s] = beta_0 + beta_1 log z_i,s + beta_2 (log z_i,s)^2 + epsilon_i`,

using the robust Huber polynomial calibrator inherited from P04p. Timing closure is the CFD20 even time minus the CFD20 odd time after subtracting the train-run median offset. The production estimator is the template/saturation scale; the reference estimator is the raw positive integral for charge and the raw peak CFD for timing. A harm label is positive when production worsens the absolute charge residual by at least 0.05, worsens the absolute timing residual by at least 1 ns, or has a large template/integral shift in the saturation-support region while charge closure worsens.

## 3. Splits and Methods

The primary transfer split trains on B2 rows from all non-held-out runs and evaluates B4/B6/B8 rows in the held-out run. A secondary within-stave split trains on the same target stave from all non-held-out runs. Thus no run appears in both train and test for any reported row, and the primary result also excludes target-stave labels from training.

The traditional method is a fixed support rule voting on saturation proxy, baseline excursion, template/integral shift, and high template loss. The ML/NN set is ridge, gradient-boosted trees, MLP, 1D-CNN, and the new `wavegate_resnet`, a waveform-gated residual tabular network that gates convolutional waveform features by support variables. Features exclude run id, event id, odd waveform, odd charge, odd timing, and held-out labels.

## 4. Primary Transfer Benchmark

Accepted events are those not flagged. Confidence intervals are 95% nonparametric bootstrap intervals over stave-run blocks.

| method                 |   precision |   recall |   accepted_coverage | accepted_coverage_ci95                     |   accepted_charge_res68_frac | accepted_charge_res68_frac_ci95            |   accepted_timing_abs68_ns | accepted_timing_abs68_ns_ci95               |   calibration_ece |   primary_rank |
|:-----------------------|------------:|---------:|--------------------:|:-------------------------------------------|-----------------------------:|:-------------------------------------------|---------------------------:|:--------------------------------------------|------------------:|---------------:|
| mlp                    |    0.855024 | 0.92901  |            0.571039 | [0.5498421575690862, 0.586756804050039]    |                    0.0554573 | [0.051226372397867585, 0.0599793195917437] |                  0.19946   | [0.12629747755297988, 0.36592551902946724]  |         0.0488977 |              1 |
| traditional_rule       |    0.677802 | 0.394474 |            0.770231 | [0.7548734357106963, 0.7826054363303399]   |                    0.0818909 | [0.07517496074085372, 0.09153510342366665] |                  0.0853792 | [0.0818296328295229, 0.08888386473606502]   |         0.0777995 |              2 |
| shuffled_target_gbt    |    0        | 0        |            1        | [1.0, 1.0]                                 |                    0.185172  | [0.1687852944116194, 0.2110447837862248]   |                  0.228423  | [0.19708201685632046, 0.2599265608298762]   |         0.0447251 |              3 |
| gradient_boosted_trees |    0.644233 | 0.90055  |            0.448125 | [0.41904540622834335, 0.4675444469223919]  |                    0.0583281 | [0.05277374494083041, 0.06385536879831465] |                  0.150726  | [0.10841978990026396, 0.27119822770517316]  |         0.151642  |              4 |
| wavegate_resnet        |    0.506897 | 0.73561  |            0.427067 | [0.38812582561734327, 0.46584806928941935] |                    0.0702745 | [0.06061631969249453, 0.0797690403656317]  |                  0.0651202 | [0.062046400336834256, 0.06874939544535968] |         0.191935  |              5 |
| ridge                  |    0.460909 | 0.763878 |            0.345689 | [0.3172755336189873, 0.3735671275881366]   |                    0.0767338 | [0.06333456482366974, 0.09047603853507577] |                  0.0675145 | [0.06276424764594367, 0.07183346551760147]  |         0.170579  |              6 |
| cnn_1d                 |    0.44432  | 0.789524 |            0.298472 | [0.26708835374903644, 0.33324625894660087] |                    0.0788344 | [0.06799039615136136, 0.09430446236503102] |                  0.0852041 | [0.07798502088433423, 0.09495283716912176]  |         0.247118  |              7 |

**Winner:** `mlp`. The winner is selected by a fixed lexicographic rule: among methods with accepted coverage >= 0.50, minimize accepted charge res68; break ties by accepted timing abs68 and calibration ECE.

## 5. Per-Stave Systematics

| stave   | method                 |   accepted_coverage |   accepted_charge_res68_frac |   accepted_timing_abs68_ns |   precision |   recall |   primary_rank |
|:--------|:-----------------------|--------------------:|-----------------------------:|---------------------------:|------------:|---------:|---------------:|
| B4      | mlp                    |            0.579152 |                    0.0596744 |                  0.427751  |    0.850804 | 0.921608 |              1 |
| B4      | traditional_rule       |            0.759403 |                    0.0830838 |                  0.0859904 |    0.626224 | 0.387803 |              2 |
| B4      | shuffled_target_gbt    |            1        |                    0.184468  |                  0.286166  |    0        | 0        |              3 |
| B4      | gradient_boosted_trees |            0.434549 |                    0.0633818 |                  0.312046  |    0.606528 | 0.882749 |              4 |
| B4      | wavegate_resnet        |            0.426302 |                    0.0782344 |                  0.0661163 |    0.448053 | 0.661613 |              5 |
| B4      | cnn_1d                 |            0.324941 |                    0.0849831 |                  0.0823524 |    0.402754 | 0.699798 |              6 |
| B4      | ridge                  |            0.348285 |                    0.0858449 |                  0.0727075 |    0.404995 | 0.679358 |              7 |
| B6      | mlp                    |            0.533669 |                    0.0472823 |                  0.099923  |    0.870724 | 0.948607 |              1 |
| B6      | traditional_rule       |            0.791604 |                    0.0838859 |                  0.0882106 |    0.807816 | 0.393291 |              2 |
| B6      | shuffled_target_gbt    |            1        |                    0.191718  |                  0.188624  |    0        | 0        |              3 |
| B6      | ridge                  |            0.288833 |                    0.0455246 |                  0.0644254 |    0.568595 | 0.944684 |              4 |
| B6      | gradient_boosted_trees |            0.455248 |                    0.0462306 |                  0.0887596 |    0.735974 | 0.936642 |              5 |
| B6      | cnn_1d                 |            0.214274 |                    0.0478568 |                  0.104291  |    0.526608 | 0.966654 |              6 |
| B6      | wavegate_resnet        |            0.381528 |                    0.0492159 |                  0.0659936 |    0.615802 | 0.889761 |              7 |
| B8      | mlp                    |            0.625288 |                    0.0570881 |                  0.134446  |    0.82905  | 0.908201 |              1 |
| B8      | wavegate_resnet        |            0.544275 |                    0.0658267 |                  0.0606343 |    0.493799 | 0.657895 |              2 |
| B8      | traditional_rule       |            0.768893 |                    0.0719518 |                  0.0738722 |    0.643116 | 0.434517 |              3 |
| B8      | shuffled_target_gbt    |            1        |                    0.165077  |                  0.162349  |    0        | 0        |              4 |
| B8      | gradient_boosted_trees |            0.495499 |                    0.0572757 |                  0.10823   |    0.6      | 0.884945 |              5 |
| B8      | ridge                  |            0.474984 |                    0.0717674 |                  0.0621145 |    0.430223 | 0.660343 |              6 |
| B8      | cnn_1d                 |            0.381411 |                    0.0754033 |                  0.0769772 |    0.401354 | 0.725826 |              7 |

The per-stave table is a systematic check on whether the pooled winner is driven by one target stave. A portable veto should preserve the same direction of improvement against the traditional rule across B4, B6, and B8; a B2-local artifact would typically collapse to sentinel-like behavior on one or more targets.

## 6. Falsification and Deltas

| method                 |   flag_rate_delta_vs_traditional | ci95                                         |   n_blocks |
|:-----------------------|---------------------------------:|:---------------------------------------------|-----------:|
| ridge                  |                         0.424542 | [0.391824202111775, 0.4604314583017549]      |         24 |
| gradient_boosted_trees |                         0.322106 | [0.295515881616974, 0.3485934282605625]      |         24 |
| mlp                    |                         0.199192 | [0.1781821470122741, 0.22124032576799538]    |         24 |
| cnn_1d                 |                         0.471759 | [0.43386762456647854, 0.5179432371097036]    |         24 |
| wavegate_resnet        |                         0.343164 | [0.30027270917830917, 0.3901532679718027]    |         24 |
| shuffled_target_gbt    |                        -0.229769 | [-0.24542871014323778, -0.21853089842385326] |         24 |

The shuffled-target GBT is retained as an explicit leakage/control sentinel. It uses the same feature matrix as the boosted-tree model after permuting training labels; if it had matched the leading model within uncertainty, the claimed even-waveform support signal would be rejected.

## 7. Caveats

- Odd duplicate readout is an external closure target, not a calibrated deposited-energy truth.
- The train source for the primary benchmark is B2, so target-stave template calibration uses B2 morphology; this is intentionally stringent for transfer, but it can understate a target-specific deployable model.
- Bootstrap intervals resample observed stave-run blocks and do not cover future detector configurations or unobserved beam settings.
- The CFD20 timing residual is a compact closure proxy and not a full pulse-fit time estimator.
- Neural-network hyperparameters are deliberately small for reproducibility on the laptop worker; the comparison is a practical benchmark, not an exhaustive architecture search.

## 8. Provenance

`manifest.json` records input checksums, command, seed, environment, and output hashes. Artifacts include `result.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `transfer_method_metrics.csv`, `within_stave_method_metrics.csv`, `transfer_method_by_stave.csv`, `transfer_method_by_run.csv`, `flag_rate_deltas.csv`, and leakage audit tables.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.py --config configs/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.json
```

## 10. Finding

The primary B2-to-B4/B6/B8 transfer winner is mlp: accepted charge res68 0.0555 at coverage 0.571, precision 0.855, recall 0.929, and timing abs68 0.199 ns. The traditional rule gives charge res68 0.0819 at coverage 0.770. The raw reproduction gate matched 640737 selected B-stave pulses exactly.
