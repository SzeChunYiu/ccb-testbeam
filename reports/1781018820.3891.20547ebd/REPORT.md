# P04g: dropout-injected amplitude charge recovery closure

Ticket `1781018820.3891.20547ebd`. Raw B-stack ROOT was read directly; no Monte Carlo detector simulation was used.

## Raw reproduction first

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | True |

## Method

Clean pulses are real selected even-channel B-stack pulses. Dropouts set controlled leading-edge, peak, trailing, or peak-plus-trailing samples to the baseline-subtracted zero level. Training excludes held-out runs before any calibration or ML fit.

Traditional estimators are calibrated peak, calibrated positive integral, train-run adaptive template scaling, rising-edge Huber regression, and linear interpolation of missing samples. ML estimators are an ExtraTrees denoising/inpainting regressor and a histogram-gradient residual model for direct amplitude/charge correction.

Held-out runs: `[57, 65]`. Bootstrap intervals resample held-out `(run,event,stave)` blocks and keep all dropout variants paired.

## Held-out summary

| method | n | amp_bias_median_frac | amp_res68_abs_frac | charge_bias_median_frac | charge_res68_abs_frac | time_abs68_samples | charge_catastrophic_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ml_residual_hgb | 5112 | 0.0015637 | 0.020519 | 0.00075962 | 0.015401 | 0.051726 | 0.020344 |
| ml_inpaint_et | 5112 | -0.0011407 | 0.024487 | 0.00023582 | 0.017431 | 0.073175 | 0.025822 |
| rising_edge_huber | 5112 | -0.00010143 | 0.034841 | 0.00012608 | 0.023681 | 0.060177 | 0.071596 |
| interpolation_calibrated | 5112 | 0.002901 | 0.1787 | -0.0070369 | 0.10384 | 0.051726 | 0.10857 |
| peak_calibrated | 5112 | 0.0029013 | 0.1787 | -0.0017012 | 0.12565 | 0.060177 | 0.17625 |
| integral_calibrated | 5112 | 0.027762 | 0.34504 | -0.0017012 | 0.12565 | 0.060177 | 0.17625 |
| adaptive_template | 5112 | -0.033021 | 0.4327 | 0.016398 | 0.37644 | 3.3752 | 0.62793 |

## ML minus best traditional deltas

| comparison | metric | delta | delta_ci95 |
| --- | --- | --- | --- |
| ml_inpaint_et minus rising_edge_huber | amp_res68_abs_frac | -0.010354 | [-0.011716596261228885, -0.008893680595002581] |
| ml_inpaint_et minus rising_edge_huber | charge_res68_abs_frac | -0.0062506 | [-0.007618244584015748, -0.005169676613766637] |
| ml_inpaint_et minus interpolation_calibrated | time_abs68_samples | 0.021449 | [0.015902122330401246, 0.027885261581427612] |
| ml_residual_hgb minus rising_edge_huber | amp_res68_abs_frac | -0.014322 | [-0.015543156810682423, -0.012631397200513707] |
| ml_residual_hgb minus rising_edge_huber | charge_res68_abs_frac | -0.0082806 | [-0.009254125227486431, -0.00743847341670726] |

## Stress splits

| subset | method | n | amp_res68_abs_frac | charge_res68_abs_frac | time_abs68_samples | charge_catastrophic_rate |
| --- | --- | --- | --- | --- | --- | --- |
| amp_ge7000 | ml_residual_hgb | 392 | 0.028581 | 0.021393 | 0.089127 | 0.002551 |
| amp_ge7000 | ml_inpaint_et | 392 | 0.055348 | 0.023878 | 0.12072 | 0.0076531 |
| amp_ge7000 | interpolation_calibrated | 392 | 0.19819 | 0.10032 | 0.089127 | 0.056122 |
| amp_ge7000 | adaptive_template | 392 | 0.47636 | 0.36506 | 1.043 | 0.93112 |
| dropout_leading_edge | ml_inpaint_et | 1278 | 0.015042 | 0.022776 | 0.1233 | 0.029734 |
| dropout_leading_edge | ml_residual_hgb | 1278 | 0.0030596 | 0.028382 | 0.15549 | 0.025039 |
| dropout_leading_edge | interpolation_calibrated | 1278 | 0.0030171 | 0.06381 | 0.15549 | 0.061815 |
| dropout_leading_edge | adaptive_template | 1278 | 0.4284 | 0.37731 | 3.3729 | 0.61659 |
| dropout_peak_sample | ml_residual_hgb | 1278 | 0.028921 | 0.0081977 | 0.03564 | 0.017997 |
| dropout_peak_sample | ml_inpaint_et | 1278 | 0.027722 | 0.014132 | 0.056585 | 0.023474 |
| dropout_peak_sample | interpolation_calibrated | 1278 | 0.22636 | 0.11451 | 0.03564 | 0.1205 |
| dropout_peak_sample | adaptive_template | 1278 | 0.42903 | 0.37621 | 3.3676 | 0.62911 |
| dropout_peak_trailing | ml_inpaint_et | 1278 | 0.035586 | 0.016752 | 0.061969 | 0.028169 |
| dropout_peak_trailing | ml_residual_hgb | 1278 | 0.044774 | 0.020739 | 0.068823 | 0.020344 |
| dropout_peak_trailing | interpolation_calibrated | 1278 | 0.24778 | 0.12208 | 0.068823 | 0.13067 |
| dropout_peak_trailing | adaptive_template | 1278 | 0.44305 | 0.37472 | 3.3676 | 0.62833 |
| dropout_trailing_sample | ml_residual_hgb | 1278 | 0.0026005 | 0.0076673 | 0 | 0.017997 |
| dropout_trailing_sample | ml_inpaint_et | 1278 | 0.021506 | 0.016213 | 0.065064 | 0.021909 |
| dropout_trailing_sample | interpolation_calibrated | 1278 | 0.20967 | 0.11385 | 0 | 0.12128 |
| dropout_trailing_sample | adaptive_template | 1278 | 0.42531 | 0.37675 | 3.4017 | 0.63772 |

Full held-out metrics are in `heldout_summary.csv`; run, stave, amplitude, peak-position, and dropout-case splits are in `heldout_by_subset.csv`.

## Leakage audit

- Held-out runs absent from training: `True`.
- Feature matrix excludes run id, event id, clean amplitude, clean charge, clean waveform, and post-injection labels: `True`.
- Train/evaluation `(run,event,stave)` overlap: `0`.
- Exact corrupted-waveform hash overlap between train and held-out evaluation rows: `0`.
- Shuffled-label ML charge res68 on held-out rows: `0.051584`.
- Too-good trigger fired: `False`.

## Finding

On 5112 held-out injected dropout rows, best amplitude recovery is ml_residual_hgb with res68 0.0205; best charge recovery is ml_residual_hgb with res68 0.0154. The simple interpolation baseline has charge res68 0.1038, so the preferred correction should be judged against interpolation rather than raw peak loss. Leakage sentinels show no held-out run or event-block overlap, and shuffled-label ML is far worse than the fitted ML residual.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04g_1781018820_3891_20547ebd_dropout_charge_recovery.py --config configs/p04g_1781018820_3891_20547ebd_dropout_charge_recovery.json
```
