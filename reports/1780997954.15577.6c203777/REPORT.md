# Study report: P04 - amplitude / deposited-charge regression

- **Ticket ID:** 1780997954.15577.6c203777
- **Worker:** testbeam-laptop-1
- **Input:** raw `data/root/root/hrdb_run_*.root` only; checksums in `manifest.json`.
- **Held-out runs:** 57, 65; all model calibration/training excludes those runs.

## 1. Raw reproduction gate

Before fitting any regressor, the script rebuilds the S00 selected-pulse gate from raw `HRDv`: `max(even channel - median(samples 0..3)) > 1000 ADC` for B2/B4/B6/B8.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

This is the reproduced ticket number used as the entry gate for the P04 benchmark.

## 2. Leakage-safe target

The trivial target `even-channel peak` is not used, because peak/integral/template features from the same waveform would define the label. Instead, the target is the paired odd readout, which is an inverted duplicate channel: amplitude is `max(-odd_waveform)` and charge is `sum(max(-odd_waveform, 0))`. Inputs are only the even-channel waveform and derived even-channel features; event number, run number, and odd-channel samples are excluded from model features.

## 3. Methods

- **Peak baseline:** per-stave log-linear calibration from even peak to odd-readout amplitude.
- **Integral baseline:** per-stave log-linear calibration from even positive-lobe integral to odd-readout charge.
- **Template-fit baseline:** per-stave, amplitude-binned median template from training runs; shifted-template least-squares scale on the even waveform, then per-stave log-linear calibration.
- **ML:** `HistGradientBoostingRegressor` on the 18 even waveform samples plus even peak/charge/shape summaries and stave one-hot; separate log-target models for amplitude and charge.

## 4. Held-out benchmark

Primary metric is the 68th percentile of absolute fractional error (`res68`); lower is better. CIs are held-out bootstrap intervals over the evaluated pulse records.

### Amplitude target

| method                  |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                  |   full_rms_frac |   within_10pct |
|:------------------------|------:|-------------------:|-----------------:|:--------------------------------------------|----------------:|---------------:|
| peak_calibrated         | 26857 |       -0.0666998   |       0.123782   | [0.12213787285603617, 0.1251004497674263]   |       0.526429  |       0.581078 |
| template_fit_calibrated | 26857 |        0.242351    |       0.58318    | [0.5726859061574294, 0.5939710507016998]    |       0.951988  |       0.168448 |
| run_stave_blind_median  | 26857 |        0.627042    |       1.22972    | [1.2003952823000563, 1.260665362035225]     |       2.99528   |       0.116804 |
| ml_hgb                  | 26857 |        0.000378022 |       0.00912262 | [0.008954850714475764, 0.00931279941200229] |       0.0345878 |       0.981569 |

### Charge target

| method                  |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   |   full_rms_frac |   within_10pct |
|:------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|----------------:|---------------:|
| integral_calibrated     | 26857 |       -0.0911845   |        0.195412  | [0.1935967908531242, 0.19754452662066144]    |       1.66374   |       0.403321 |
| template_fit_calibrated | 26857 |        0.0982004   |        0.55034   | [0.5363636122646894, 0.5642690338331129]     |       2.52073   |       0.187847 |
| run_stave_blind_median  | 26857 |        0.791998    |        1.89793   | [1.8576532321089652, 1.939693336222785]      |      16.2951    |       0.128346 |
| ml_hgb                  | 26857 |        0.000598551 |        0.0150719 | [0.014843082483203526, 0.015295865584628966] |       0.0467735 |       0.969245 |

### High-amplitude and B2 checks

| subset          | method                  |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   |   within_10pct |
|:----------------|:------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|---------------:|
| stave_B2        | peak_calibrated         | 24528 |       -0.0653136   |       0.119238   | [0.11806067412996538, 0.12083200973176386]   |      0.599397  |
| even_amp_ge7000 | peak_calibrated         |  2299 |        0.00791854  |       0.0250517  | [0.02356797003366716, 0.026806138344397157]  |      0.888647  |
| stave_B2        | template_fit_calibrated | 24528 |        0.271401    |       0.610372   | [0.5970208834141527, 0.6234866989503157]     |      0.16524   |
| even_amp_ge7000 | template_fit_calibrated |  2299 |       -0.266321    |       0.309014   | [0.30351391464838506, 0.3147325987062877]    |      0.0191388 |
| stave_B2        | ml_hgb                  | 24528 |        0.000349956 |       0.00872017 | [0.008543754460089762, 0.008906409037743672] |      0.981735  |
| even_amp_ge7000 | ml_hgb                  |  2299 |        0.000426816 |       0.00802688 | [0.0076764787403712, 0.008483735708090422]   |      0.995215  |

## 5. Leakage audit

- Held-out runs `57, 65` are absent from training: `True`.
- Feature columns include no run/event ids and no odd-channel target samples: `True`.
- Rows with invalid independent target removed after reproduction: 255.
- Run/stave-only median predictor amplitude res68: 1.2297.
- Shuffled-target ML amplitude res68: 0.8131.

The ML result is deliberately not interpreted as absolute detector truth: it is a same-event duplicate-readout closure test. The unusually small ML error is plausible for a duplicate readout but too strong to promote to a physics energy claim without an external charge/energy reference.

## 6. Finding

On independent odd-readout closure, ML amplitude res68 is 0.0091 versus the best traditional amplitude baseline at 0.1238; charge res68 is 0.0151 versus 0.1954. The duplicate readout is already very strongly predicted by calibrated peak/integral baselines, and the much smaller ML error is treated as a duplicate-readout closure result rather than an absolute true-energy calibration.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04_amplitude_charge_regression.py --config configs/p04_amplitude_charge_regression.yaml
```
