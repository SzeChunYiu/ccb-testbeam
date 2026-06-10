# P04i duplicate-charge model causality under saturation

## Abstract

This study rebuilds the B-stack selected-pulse table from raw ROOT and then tests whether the duplicate-readout charge closure can be predicted from rising-edge information alone, or whether post-peak samples materially improve apparent accuracy.  The target is the paired odd-channel positive charge; all features are computed from the even channel of the same stave.

- **Ticket ID:** `1781033028.1821.007252a9`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw ROOT files under `data/root/root`.
- **Held-out runs:** `[57, 65]`; all models train only on the complement.
- **Winner:** `strong_traditional_full` by minimum held-out run-split res68.

## Raw ROOT reproduction

For each event and B-stack even channel, the baseline is the median of samples $s_0,\ldots,s_3$.  A pulse is selected when

$$\max_t \{x_t-\mathrm{median}(x_0,x_1,x_2,x_3)\} > 1000\ \mathrm{ADC}.$$

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

Rows with non-positive independent odd-channel charge are removed only after this reproduction gate.

## Target and estimands

Let \(x_i\in\mathbb{R}^{18}\) denote the baseline-subtracted even-channel waveform and \(z_i\in\mathbb{R}^{18}\) the paired odd-channel waveform.  The charge target is

$$y_i=\sum_{t=0}^{17}\max(-z_{it},0).$$

Models are fitted to \(\log y_i\) and transformed back with \(\hat y_i=\exp f(x_i)\). The primary error metric is the absolute fractional 68% quantile

$$R_{68}=Q_{0.68}\left(\left|\frac{\hat y_i-y_i}{\max(y_i,1)}\right|\right),$$

reported with run-block bootstrap confidence intervals.  The saturated subset uses `even_amp >= 7000.0 ADC`; the unsaturated control uses the complementary held-out rows.

## Model classes

- **Strong traditional:** stave-aware robust Huber regression on calibrated peak, integral, template scale, half-width, and charge-fraction summaries.
- **Ridge:** standardized linear ridge regression on the same engineered feature view.
- **Gradient-boosted trees:** `HistGradientBoostingRegressor` on engineered features.
- **MLP:** two-hidden-layer neural regressor on engineered features.
- **1D-CNN:** convolutional regressor over waveform samples with auxiliary engineered summaries.
- **WaveGate residual:** a new attention-gated residual temporal network for this short 18-sample waveform. It learns a softmax sample gate over convolutional embeddings and concatenates the gated waveform state with a residual raw-waveform branch and auxiliary summaries.

Each class is trained twice where applicable: `full` uses all 18 samples, while `rising` uses only samples 0-8 and does not use full-waveform peak position, integral, or tail summaries.

## Held-out run benchmark

| method                    |     n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |    mae_frac |   within_10pct |
|:--------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|------------:|---------------:|
| strong_traditional_full   | 26860 |        3.44946e-05 |        0.0138921 | [0.013446103752157483, 0.014238827018821738] |   2.46321   |       0.910685 |
| wavegate_residual_full    | 26860 |        0.00179587  |        0.0147707 | [0.013919090385288855, 0.015577778470262758] |   0.0248841 |       0.946687 |
| cnn1d_full                | 26860 |        0.00241878  |        0.0151949 | [0.013902439476177026, 0.01651573552908477]  |   0.026054  |       0.947096 |
| gbt_full                  | 26860 |        0.000805982 |        0.0160843 | [0.016070648011954167, 0.016094421825499687] |   0.021709  |       0.962844 |
| mlp_full                  | 26860 |        0.0013804   |        0.0215442 | [0.01911924979522627, 0.023893644661493074]  |   0.0353192 |       0.93455  |
| cnn1d_rising              | 26860 |       -0.00348783  |        0.0356517 | [0.030856858142176303, 0.040385438611974175] |   0.0655426 |       0.878816 |
| gbt_rising                | 26860 |        0.00813853  |        0.0385393 | [0.033947637126944076, 0.0428175258776777]   |   0.0627088 |       0.886523 |
| mlp_rising                | 26860 |        0.00336294  |        0.053109  | [0.05164710520398769, 0.05418525889772159]   |   0.0757699 |       0.865823 |
| wavegate_residual_rising  | 26860 |       -0.0076348   |        0.0532468 | [0.04890607303186979, 0.057210061104953115]  |   0.0745826 |       0.846128 |
| ridge_full                | 26860 |       -0.0014066   |        0.0749689 | [0.07435235156756165, 0.07576432686087972]   |   0.249925  |       0.778481 |
| strong_traditional_rising | 26860 |        0.0117684   |        0.177163  | [0.14877420276965705, 0.21555415370818537]   | 282.013     |       0.452681 |
| ridge_rising              | 26860 |       -0.0157997   |        0.209269  | [0.20021616347838758, 0.22683637582930624]   |   0.520421  |       0.324497 |

## Unsaturated control

| method                    |     n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |   within_10pct |
|:--------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|---------------:|
| strong_traditional_full   | 24561 |        0.000327387 |        0.0141962 | [0.014162660463220907, 0.014220950456006229] |       0.909124 |
| wavegate_residual_full    | 24561 |        0.00209884  |        0.0155203 | [0.015171207372129297, 0.015808264166364973] |       0.94304  |
| cnn1d_full                | 24561 |        0.00315907  |        0.0158898 | [0.014917924361672573, 0.016716650385231954] |       0.943447 |
| gbt_full                  | 24561 |        0.000847509 |        0.0165604 | [0.01607399740115357, 0.01714675388827302]   |       0.962176 |
| mlp_full                  | 24561 |        0.00279781  |        0.0224164 | [0.020289897788278045, 0.024007627989083895] |       0.930296 |
| cnn1d_rising              | 24561 |       -0.00283774  |        0.0380745 | [0.03440052219751707, 0.04112145847895435]   |       0.872521 |
| gbt_rising                | 24561 |        0.00937282  |        0.0406478 | [0.03692053494550701, 0.04353954664202981]   |       0.881153 |
| mlp_rising                | 24561 |       -0.000105974 |        0.0541398 | [0.05205353206357429, 0.05591627868670163]   |       0.85876  |
| wavegate_residual_rising  | 24561 |       -0.0107247   |        0.057203  | [0.055642525018846985, 0.058365012416262706] |       0.836082 |
| ridge_full                | 24561 |       -0.00273042  |        0.0792504 | [0.07700494858353638, 0.08155468876702887]   |       0.767477 |
| strong_traditional_rising | 24561 |       -0.000276282 |        0.172586  | [0.14479291731116614, 0.20556939746699937]   |       0.45503  |
| ridge_rising              | 24561 |       -0.0349333   |        0.20616   | [0.1978935710057189, 0.22014602344203357]    |       0.319124 |

## Saturated subset

| method                    |    n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |   within_10pct |
|:--------------------------|-----:|-------------------:|-----------------:|:---------------------------------------------|---------------:|
| wavegate_residual_full    | 2299 |       -0.000427466 |       0.00842622 | [0.008365269340756931, 0.009244443232412986] |       0.985646 |
| cnn1d_full                | 2299 |       -0.00270353  |       0.00939155 | [0.008843046329950343, 0.011371088279038337] |       0.986081 |
| strong_traditional_full   | 2299 |       -0.00213472  |       0.0101262  | [0.00930440762027487, 0.015517313327088191]  |       0.92736  |
| gbt_full                  | 2299 |        0.000608665 |       0.0113554  | [0.01046360743992261, 0.01689634767300445]   |       0.969987 |
| mlp_full                  | 2299 |       -0.00672242  |       0.0155066  | [0.014209933709234396, 0.021043607073233047] |       0.979991 |
| cnn1d_rising              | 2299 |       -0.0067394   |       0.0163119  | [0.015633651706882256, 0.01927946157646897]  |       0.946064 |
| wavegate_residual_rising  | 2299 |        0.00561145  |       0.0177734  | [0.016427676381264744, 0.023218490050833977] |       0.953458 |
| gbt_rising                | 2299 |       -0.000154046 |       0.0195559  | [0.018433820139232966, 0.025105248626997555] |       0.943889 |
| ridge_full                | 2299 |        0.00523932  |       0.0382835  | [0.034221772256909574, 0.04878954712596211]  |       0.896042 |
| mlp_rising                | 2299 |        0.0351105   |       0.0480626  | [0.04210148946169996, 0.048783374333361364]  |       0.941279 |
| strong_traditional_rising | 2299 |        0.102378    |       0.237434   | [0.1807738628596481, 0.391067191411804]      |       0.427577 |
| ridge_rising              | 2299 |        0.124947    |       0.288308   | [0.23210452429718326, 0.47981930499547365]   |       0.381905 |

## Per-run split diagnostics

| subset   | method                    |     n |   bias_median_frac |   res68_abs_frac |   within_10pct |
|:---------|:--------------------------|------:|-------------------:|-----------------:|---------------:|
| run_65   | cnn1d_full                | 13038 |        0.00395532  |        0.0165165 |       0.955898 |
| run_57   | cnn1d_full                | 13822 |        0.00125365  |        0.0139027 |       0.938793 |
| run_65   | cnn1d_rising              | 13038 |       -0.00287309  |        0.0403884 |       0.875058 |
| run_57   | cnn1d_rising              | 13822 |       -0.00394896  |        0.0308569 |       0.882361 |
| run_57   | gbt_full                  | 13822 |        0.000235531 |        0.0160707 |       0.957676 |
| run_65   | gbt_full                  | 13038 |        0.00139306  |        0.0160947 |       0.968323 |
| run_65   | gbt_rising                | 13038 |        0.0128708   |        0.042818  |       0.887099 |
| run_57   | gbt_rising                | 13822 |        0.00475397  |        0.0339477 |       0.885979 |
| run_57   | mlp_full                  | 13822 |       -0.00105716  |        0.0191194 |       0.925409 |
| run_65   | mlp_full                  | 13038 |        0.00454673  |        0.0238943 |       0.94424  |
| run_57   | mlp_rising                | 13822 |        0.0171967   |        0.0541854 |       0.864347 |
| run_65   | mlp_rising                | 13038 |       -0.00862968  |        0.0516473 |       0.867388 |
| run_57   | ridge_full                | 13822 |       -0.0119687   |        0.0743534 |       0.77326  |
| run_65   | ridge_full                | 13038 |        0.0135267   |        0.0757695 |       0.784016 |
| run_57   | ridge_rising              | 13822 |       -0.0529118   |        0.200216  |       0.330632 |
| run_65   | ridge_rising              | 13038 |        0.0334523   |        0.226839  |       0.317994 |
| run_57   | strong_traditional_full   | 13822 |       -0.00113629  |        0.0134461 |       0.898857 |
| run_65   | strong_traditional_full   | 13038 |        0.00161979  |        0.0142391 |       0.923224 |
| run_65   | strong_traditional_rising | 13038 |        0.0357554   |        0.21558   |       0.414864 |
| run_57   | strong_traditional_rising | 13822 |       -0.00854822  |        0.148775  |       0.488352 |
| run_57   | wavegate_residual_full    | 13822 |        0.00131134  |        0.0139191 |       0.940674 |
| run_65   | wavegate_residual_full    | 13038 |        0.00239066  |        0.0155785 |       0.95306  |
| run_57   | wavegate_residual_rising  | 13822 |       -0.00526     |        0.0489062 |       0.851396 |
| run_65   | wavegate_residual_rising  | 13038 |       -0.010573    |        0.0572106 |       0.840543 |

## Deltas versus strong traditional full

| method                    | reference_method        |   delta_res68_abs_frac | run_block_delta_res68_ci95                     |
|:--------------------------|:------------------------|-----------------------:|:-----------------------------------------------|
| wavegate_residual_full    | strong_traditional_full |            0.000878548 | [0.0004729866331313719, 0.0013389514514410197] |
| cnn1d_full                | strong_traditional_full |            0.00130274  | [0.00045633572401954266, 0.002276908510263031] |
| gbt_full                  | strong_traditional_full |            0.00219213  | [0.0018555948066779487, 0.0026245442597966837] |
| mlp_full                  | strong_traditional_full |            0.00765206  | [0.0056731460430687886, 0.009654817642671336]  |
| cnn1d_rising              | strong_traditional_full |            0.0217596   | [0.01741075439001882, 0.026146611593152437]    |
| gbt_rising                | strong_traditional_full |            0.0246471   | [0.020501533374786593, 0.028578698858855965]   |
| mlp_rising                | strong_traditional_full |            0.0392169   | [0.03740827818516595, 0.04073915514556411]     |
| wavegate_residual_rising  | strong_traditional_full |            0.0393546   | [0.03545996927971231, 0.04297123408613138]     |
| ridge_full                | strong_traditional_full |            0.0610768   | [0.060906247815404164, 0.06152549984205798]    |
| strong_traditional_rising | strong_traditional_full |            0.163271    | [0.13532809901749956, 0.20131532668936364]     |
| ridge_rising              | strong_traditional_full |            0.195377    | [0.1867700597262301, 0.2125975488104845]       |

## Saturated ordering

For saturated rows, ordering quality is estimated by random within-run, within-stave pulse pairs: \(\Pr[\mathrm{sign}(\hat y_a-\hat y_b)=\mathrm{sign}(y_a-y_b)]\).  The final column is the accuracy delta relative to the strong traditional full model.

| method                    |    n |   pairwise_order_accuracy |   delta_vs_strong_traditional_full |
|:--------------------------|-----:|--------------------------:|-----------------------------------:|
| ridge_full                | 2299 |                  0.723666 |                         -0.193625  |
| strong_traditional_rising | 2299 |                  0.839074 |                         -0.0782175 |
| ridge_rising              | 2299 |                  0.84718  |                         -0.070112  |
| gbt_full                  | 2299 |                  0.890545 |                         -0.0267469 |
| mlp_rising                | 2299 |                  0.901772 |                         -0.0155201 |
| strong_traditional_full   | 2299 |                  0.917292 |                          0         |
| mlp_full                  | 2299 |                  0.933182 |                          0.0158902 |
| wavegate_residual_full    | 2299 |                  0.941226 |                          0.0239341 |
| cnn1d_full                | 2299 |                  0.94212  |                          0.0248285 |
| gbt_rising                | 2299 |                  0.949122 |                          0.0318298 |
| cnn1d_rising              | 2299 |                  0.952298 |                          0.0350067 |
| wavegate_residual_rising  | 2299 |                  0.958134 |                          0.0408421 |

## Leakage and causality audit

- Held-out runs absent from training: `True`.
- Train/held-out `(run,event,stave)` overlap: `0`.
- Feature columns exclude run ids, event ids, and odd-channel target samples: `True`.
- Invalid odd-target rows removed after raw reproduction: `199`.
- Stave-only median held-out res68: `1.89842`.
- Shuffled-target GBT held-out res68: `1.03311`.

## Systematics and caveats

The target is a same-event duplicate electronic readout, not an external calorimetric truth label. Very small errors therefore demonstrate closure between two readout paths but do not by themselves establish absolute deposited-energy calibration.  The held-out set contains two runs, so the run-block bootstrap measures sensitivity to those run identities rather than the full future-run distribution. Neural networks are trained on capped random training subsets for compute control; this is conservative for model ranking but leaves some hyperparameter variance.  The rising-only view is a fixed sample-window causality stress test; it cannot prove online deployability for a different sampling phase without a separate phase-jitter study.

## Finding

The winner is strong_traditional_full with held-out res68=0.0138921 (run-block 95% CI [0.013446103752157483, 0.014238827018821738]); the best non-traditional challenger is wavegate_residual_full at res68=0.0147707.  The best rising-only model is cnn1d_rising at res68=0.0356517, while the best full-waveform model is strong_traditional_full at res68=0.0138921; the full-view advantage quantifies the post-peak leakage risk.  On saturated rows, wavegate_residual_full has the lowest res68=0.00842622.  Because all labels are duplicate-readout charges, the result is a closure and causality stress test rather than an external true-energy calibration.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04i_1781033028_1821_007252a9_causality_bakeoff.py --config configs/p04i_1781033028_1821_007252a9_causality_bakeoff.json
```
