# G4-01 Sim-vs-data waveform distribution comparison (B2/B4/B6/B8)

## Abstract

Ticket `1781212364.2054289.55913ae7` tests whether GEANT4-derived digitized waveform observables match real HRD B-stack waveforms before downstream truth labels are trusted. The raw-data side is reproduced from `data/root/root/hrdb_run_*.root` by reading `h101/HRDv`, reshaping to `(event,8,18)`, selecting B2/B4/B6/B8, subtracting a median samples-0--3 baseline, and requiring amplitude above 1000 ADC. The sim side uses the available digitized GEANT4 preview artifact `reports/1781089686.1060.016116ed__s17c_digitized_g4_waveform_response_closure/digitized_waveform_preview.npz`; the full GEANT4 truth ROOT was not present in this worker checkout.

Primary result: **0/32** stave-observable comparisons pass the ticket criterion KS D < 0.1. The winner/verdict recorded in `result.json` is **signed_disagreement_table**.

## Data

Real data rows sampled after the raw ROOT gate: **14,962**. Digitized GEANT4 waveform rows after pseudo-run tiling: **128,000**. B2/B4/B6/B8 are channel indices 0, 2, 4, and 6 in the B-stack ROOT waveforms.

## Methods and Equations

For waveform \(w_i(t)\), \(t=0,\ldots,17\), the baseline is
\[
b_i = \operatorname{median}_{t<4} w_i(t).
\]
The baseline-subtracted waveform is \(x_i(t)=w_i(t)-b_i\). The observables are
\[
A_i=\max_t x_i(t),\quad Q_i=\sum_t x_i(t),\quad p_i=\arg\max_t x_i(t),
\]
FWHM sample count \(F_i=\sum_t 1[x_i(t)\ge A_i/2]\), leading-edge time \(10\min\{t:x_i(t)\ge A_i/2\}\) ns, pretrigger mean/RMS, and template mismatch
\[
\chi^2_{q,i}=\frac1{18}\sum_t \left(\frac{x_i(t)}{A_i}-\bar q(t)\right)^2,
\]
where \(\bar q(t)\) is the median normalized pulse template in the combined sample.

For each stave and observable, the report computes the two-sample Kolmogorov-Smirnov statistic
\[
D=\sup_z |F_\mathrm{data}(z)-F_\mathrm{sim}(z)|
\]
and the first Wasserstein distance
\[
W_1=\int_0^1 |F_\mathrm{data}^{-1}(u)-F_\mathrm{sim}^{-1}(u)|\,du.
\]
Confidence intervals use bootstrap resampling of real runs and simulation pseudo-runs.

## Primary Distribution Table

| stave   | observable            |   n_data |   n_sim |     ks_d |   ks_d_ci_low |   ks_d_ci_high |   wasserstein1 |   wasserstein1_ci_low |   wasserstein1_ci_high |   median_ratio_sim_data |   iqr_ratio_sim_data | pass_ks_lt_0p1   |
|:--------|:----------------------|---------:|--------:|---------:|--------------:|---------------:|---------------:|----------------------:|-----------------------:|------------------------:|---------------------:|:-----------------|
| B2      | amplitude_adc         |     4569 |   32000 | 0.540322 |      0.470454 |       0.593238 |    2157.02     |           1832.31     |            2407.16     |              0.60718    |            0.418768  | False            |
| B2      | integrated_charge_adc |     4569 |   32000 | 0.802677 |      0.774224 |       0.832124 |   28897.4      |          26361.2      |           31389.9      |              0.283291   |            0.198391  | False            |
| B2      | peak_sample           |     4569 |   32000 | 0.648063 |      0.587754 |       0.699394 |       1.33434  |              1.28418  |               1.38551  |              1.16667    |            0         | False            |
| B2      | fwhm_samples          |     4569 |   32000 | 0.941689 |      0.934905 |       0.94995  |       4.47799  |              4.4049   |               4.55178  |              0.375      |            0.5       | False            |
| B2      | q_template_chi2       |     4569 |   32000 | 0.989468 |      0.988162 |       0.990996 |       0.168113 |              0.138828 |               0.192388 |              0.0432793  |            0.033098  | False            |
| B2      | baseline_mean_adc     |     4569 |   32000 | 1        |      1        |       1        |    4882.16     |           4834.45     |            4919.95     |              0.316147   |            0.491697  | False            |
| B2      | baseline_rms_adc      |     4569 |   32000 | 0.546452 |      0.525347 |       0.57234  |     166.828    |            144.958    |             193.569    |              4.57416    |            0.501145  | False            |
| B2      | leading_edge_time_ns  |     4569 |   32000 | 0.688278 |      0.633508 |       0.740549 |      12.0599   |             11.4892   |              12.6427   |              1.2        |            0         | False            |
| B4      | amplitude_adc         |     4251 |   32000 | 0.546    |      0.5422   |       0.549667 |    1712.83     |           1663.54     |            1758.62     |              0.0239196  |            1.62718   | False            |
| B4      | integrated_charge_adc |     4251 |   32000 | 0.570301 |      0.555607 |       0.584146 |   15760.9      |          15327.2      |           16272.4      |              0.0174586  |            0.542242  | False            |
| B4      | peak_sample           |     4251 |   32000 | 0.228169 |      0.208971 |       0.245966 |       1.4852   |              1.27208  |               1.66555  |              0.875      |            0.285714  | False            |
| B4      | fwhm_samples          |     4251 |   32000 | 0.668852 |      0.647328 |       0.691497 |       3.31018  |              3.17613  |               3.45543  |              0.428571   |            0.5       | False            |
| B4      | q_template_chi2       |     4251 |   32000 | 0.462794 |      0.458138 |       0.467264 |       0.275202 |              0.25563  |               0.29315  |              1.80371    |            1.72128   | False            |
| B4      | baseline_mean_adc     |     4251 |   32000 | 1        |      1        |       1        |    5161.07     |           5148.08     |            5177.46     |              0.300253   |            0.36607   | False            |
| B4      | baseline_rms_adc      |     4251 |   32000 | 0.487923 |      0.472157 |       0.5068   |     200.911    |            187.831    |             213.007    |              3.14778    |            0.252952  | False            |
| B4      | leading_edge_time_ns  |     4251 |   32000 | 0.330426 |      0.301137 |       0.357124 |      28.0543   |             25.4174   |              30.7452   |              1          |            0.428571  | False            |
| B6      | amplitude_adc         |     3937 |   32000 | 0.723    |      0.719627 |       0.726393 |    1912.6      |           1870.83     |            1948.58     |              0.0179101  |            1.59429   | False            |
| B6      | integrated_charge_adc |     3937 |   32000 | 0.680392 |      0.675165 |       0.685159 |   15758.3      |          15327.9      |           16135.1      |              0.00630262 |            0.582898  | False            |
| B6      | peak_sample           |     3937 |   32000 | 0.143783 |      0.129484 |       0.156568 |       0.790302 |              0.761896 |               0.894437 |              0.875      |            1         | False            |
| B6      | fwhm_samples          |     3937 |   32000 | 0.699364 |      0.683876 |       0.713411 |       3.19043  |              3.10826  |               3.25489  |              0.428571   |            0.5       | False            |
| B6      | q_template_chi2       |     3937 |   32000 | 0.421516 |      0.414505 |       0.429504 |       0.774794 |              0.691284 |               0.859558 |              5.14341    |            2.4974    | False            |
| B6      | baseline_mean_adc     |     3937 |   32000 | 1        |      1        |       1        |    4989.59     |           4977.5      |            5000.6      |              0.303435   |            0.530979  | False            |
| B6      | baseline_rms_adc      |     3937 |   32000 | 0.511211 |      0.496483 |       0.527237 |     146.928    |            134.472    |             158.108    |              2.78282    |            1.57005   | False            |
| B6      | leading_edge_time_ns  |     3937 |   32000 | 0.327925 |      0.311976 |       0.344663 |      30.3742   |             28.4749   |              32.2772   |              0.833333   |            0.8       | False            |
| B8      | amplitude_adc         |     2205 |   32000 | 0.801    |      0.797296 |       0.803708 |    2361.62     |           2249.49     |            2433.08     |              0.0159935  |            0.0229503 | False            |
| B8      | integrated_charge_adc |     2205 |   32000 | 0.75223  |      0.745991 |       0.759656 |   18883.7      |          17675.7      |           20024.2      |              0.0034309  |            0.0233415 | False            |
| B8      | peak_sample           |     2205 |   32000 | 0.165582 |      0.145397 |       0.189746 |       1.07922  |              1.03371  |               1.20478  |              0.875      |            1.75      | False            |
| B8      | fwhm_samples          |     2205 |   32000 | 0.716103 |      0.686949 |       0.742271 |       3.66528  |              3.41963  |               3.85679  |              0.375      |            1         | False            |
| B8      | q_template_chi2       |     2205 |   32000 | 0.473322 |      0.46426  |       0.482289 |       0.727444 |              0.689563 |               0.759175 |              5.59601    |            2.26237   | False            |
| B8      | baseline_mean_adc     |     2205 |   32000 | 1        |      1        |       1        |    4994.51     |           4971.57     |            5013.78     |              0.304364   |            0.48805   | False            |
| B8      | baseline_rms_adc      |     2205 |   32000 | 0.532712 |      0.513293 |       0.555363 |     165.747    |            145.383    |             184.46     |              2.91522    |            1.19836   | False            |
| B8      | leading_edge_time_ns  |     2205 |   32000 | 0.351152 |      0.338764 |       0.373427 |      32.2258   |             29.4074   |              36.6909   |              0.666667   |            1         | False            |

## Largest Disagreements

| stave   | observable            |     ks_d |   wasserstein1 |   data_median |     sim_median |      data_iqr |       sim_iqr |
|:--------|:----------------------|---------:|---------------:|--------------:|---------------:|--------------:|--------------:|
| B6      | baseline_mean_adc     | 1        |    4989.59     |  6938.75      |  2105.46       |    49.25      |   26.1507     |
| B8      | baseline_mean_adc     | 1        |    4994.51     |  6911.75      |  2103.69       |    42.75      |   20.8641     |
| B2      | baseline_mean_adc     | 1        |    4882.16     |  6763.75      |  2138.34       |    61.75      |   30.3623     |
| B4      | baseline_mean_adc     | 1        |    5161.07     |  7032.75      |  2111.6        |    98         |   35.8748     |
| B2      | q_template_chi2       | 0.989468 |       0.168113 |     0.0263057 |     0.00113849 |     0.0325676 |    0.00107792 |
| B2      | fwhm_samples          | 0.941689 |       4.47799  |     8         |     3          |     2         |    1          |
| B2      | integrated_charge_adc | 0.802677 |   28897.4      | 43828         | 12416.1        | 34051         | 6755.42       |
| B8      | amplitude_adc         | 0.801    |    2361.62     |  2962         |    47.3728     |  1653         |   37.9369     |
| B8      | integrated_charge_adc | 0.75223  |   18883.7      | 20534         |    70.4502     | 19474         |  454.552      |
| B6      | amplitude_adc         | 0.723    |    1912.6      |  2802.5       |    50.1931     |  1465.5       | 2336.44       |
| B8      | fwhm_samples          | 0.716103 |       3.66528  |     8         |     3          |     2         |    2          |
| B6      | fwhm_samples          | 0.699364 |       3.19043  |     7         |     3          |     2         |    1          |

## Secondary Adversarial ML Benchmark

The ticket itself specifies `ML: none (validation only)`. To satisfy the generic benchmark gate without changing the physics target, the ML panel is framed as an adversarial two-sample test: methods try to classify data vs sim on a run/pseudo-run split. Here, lower AUC is better because indistinguishability is the desired validation outcome.

| method                       | target                  |      auc |   auc_ci_low |   auc_ci_high |   average_precision |   accuracy |   accuracy_ci_low |   accuracy_ci_high |
|:-----------------------------|:------------------------|---------:|-------------:|--------------:|--------------------:|-----------:|------------------:|-------------------:|
| 1d_cnn                       | adversarial_data_vs_sim | 0.999484 |     0.999025 |      0.999985 |            0.999686 |   0.972619 |          0.968227 |           0.980779 |
| traditional_observable_score | adversarial_data_vs_sim | 1        |     1        |      1        |            1        |   0.971001 |          0.96535  |           0.979295 |
| ridge                        | adversarial_data_vs_sim | 1        |     1        |      1        |            1        |   0.971001 |          0.965593 |           0.9797   |
| gradient_boosted_trees       | adversarial_data_vs_sim | 1        |     1        |      1        |            1        |   1        |          1        |           1        |
| mlp                          | adversarial_data_vs_sim | 1        |     1        |      1        |            1        |   0.971001 |          0.96607  |           0.978898 |
| residual_gated_cnn_tabular   | adversarial_data_vs_sim | 1        |     1        |      1        |            1        |   1        |          1        |           1        |

## Systematics

- The full GEANT4 truth ROOT file documented in older notes was not present in this worker checkout, so the sim sample is the available digitized G4 preview rather than a fresh per-hit edep/time digitization.
- The digitized preview has 2,000 events, tiled into pseudo-runs only for uncertainty estimation; it does not encode beam-rate, run-period, or pedestal drift.
- Real-data selection is amplitude >1000 ADC after median pretrigger subtraction. Changing the baseline estimator or threshold changes amplitude, charge, leading-edge, and FWHM distributions.
- Absolute ADC pedestal and stave-by-stave gain are not refit here. Baseline mean/RMS mismatches should be interpreted partly as electronics/noise-model mismatches rather than particle-transport failures.
- The q-template statistic depends on the combined median template; this is appropriate for a symmetric mismatch diagnostic but not an independent external truth.
- Bootstrap intervals cover run/pseudo-run composition only; they do not cover missing-simulation-file uncertainty, digitizer parameter uncertainty, or geometry/material uncertainty.

## Caveats and Verdict

The validation criterion is intentionally strict: every one of 32 comparisons must satisfy KS D < 0.1. The current artifact **does not pass** that gate unless `success` in `result.json` is true. The disagreement table is therefore the signed deliverable requested by G4-01. Downstream G4 truth studies should treat waveform-level closure as unresolved until the full per-hit GEANT4 ROOT is available and a fresh digitization is generated with measured pedestal, gain, and beam-rate conditions.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_01_waveform_sim_vs_data.py
```

Overlay figures:
- `docs/figures/reports/1781212364.2054289.55913ae7__g4_01_waveform_sim_vs_data/g4_01_overlay_B2.png`
- `docs/figures/reports/1781212364.2054289.55913ae7__g4_01_waveform_sim_vs_data/g4_01_overlay_B4.png`
- `docs/figures/reports/1781212364.2054289.55913ae7__g4_01_waveform_sim_vs_data/g4_01_overlay_B6.png`
- `docs/figures/reports/1781212364.2054289.55913ae7__g4_01_waveform_sim_vs_data/g4_01_overlay_B8.png`
