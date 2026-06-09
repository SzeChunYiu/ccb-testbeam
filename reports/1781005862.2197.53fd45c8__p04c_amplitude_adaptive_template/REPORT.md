# P04c: stronger amplitude-adaptive template baseline

- **Ticket ID:** 1781005862.2197.53fd45c8
- **Worker:** testbeam-laptop-4
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

- **Peak/integral baselines:** per-stave log-linear calibrations from even peak and positive-lobe integral.
- **P04 fixed-bin template:** per-stave amplitude-bin median templates with time-shift fitting, retained as a legacy reference.
- **P04c adaptive-template scale:** per-stave median templates in finer amplitude bins, linearly interpolated in log-amplitude and fit over a time-shift grid, then per-stave train-only log calibration.
- **P04c strong traditional ridge:** a train-only per-stave ridge calibration on explicit adaptive-template diagnostics (`template scale`, `shift`, `fit MSE`) plus peak/integral/shape summaries. It uses no run id, event id, or odd-channel samples.
- **ML:** `HistGradientBoostingRegressor` on the 18 even waveform samples plus even peak/charge/shape summaries and stave one-hot; separate log-target models for amplitude and charge.

## 4. Held-out benchmark

Primary metric is the 68th percentile of absolute fractional error (`res68`); lower is better. CIs are held-out bootstrap intervals over the evaluated pulse records.

### Amplitude target

| method                        |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   |   full_rms_frac |   within_10pct |
|:------------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|----------------:|---------------:|
| peak_calibrated               | 26857 |       -0.0666998   |       0.123782   | [0.12213787285603617, 0.1251004497674263]    |       0.526429  |       0.581078 |
| fixed_bin_template_calibrated | 26857 |        0.245005    |       0.582505   | [0.5710870110614047, 0.5922042688605998]     |       0.968177  |       0.168597 |
| adaptive_template_scale       | 26857 |        0.24404     |       0.577549   | [0.564170614506139, 0.5918852201851339]      |       0.961479  |       0.16491  |
| adaptive_template_ridge       | 26857 |        0.00948455  |       0.0857557  | [0.08440349880769346, 0.08710003541873318]   |       0.294238  |       0.732695 |
| run_stave_blind_median        | 26857 |        0.627042    |       1.22972    | [1.2009687125555792, 1.2587041562253547]     |       2.99528   |       0.116804 |
| ml_hgb                        | 26857 |        0.000378022 |       0.00912262 | [0.008914812519211215, 0.009274945340559929] |       0.0345878 |       0.981569 |

### Charge target

| method                        |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                  |   full_rms_frac |   within_10pct |
|:------------------------------|------:|-------------------:|-----------------:|:--------------------------------------------|----------------:|---------------:|
| integral_calibrated           | 26857 |       -0.0911845   |        0.195412  | [0.19359815268039232, 0.19751859964953214]  |       1.66374   |       0.403321 |
| fixed_bin_template_calibrated | 26857 |        0.104333    |        0.556466  | [0.5423834520064015, 0.5672860928257762]    |       2.59249   |       0.178538 |
| adaptive_template_scale       | 26857 |        0.10173     |        0.549106  | [0.5361386877374352, 0.564370153185557]     |       2.55607   |       0.180214 |
| adaptive_template_ridge       | 26857 |        0.0162047   |        0.155377  | [0.15296791070032645, 0.1573421307984234]   |       0.723593  |       0.514391 |
| run_stave_blind_median        | 26857 |        0.791998    |        1.89793   | [1.8547140913331057, 1.9402374403293199]    |      16.2951    |       0.128346 |
| ml_hgb                        | 26857 |        0.000598551 |        0.0150719 | [0.01484209066350834, 0.015293306984993794] |       0.0467735 |       0.969245 |

### High-amplitude and B2 checks

| subset          | method                  |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   |   within_10pct |
|:----------------|:------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|---------------:|
| stave_B2        | peak_calibrated         | 24528 |       -0.0653136   |       0.119238   | [0.11806067412996538, 0.12083200973176386]   |      0.599397  |
| even_amp_ge7000 | peak_calibrated         |  2299 |        0.00791854  |       0.0250517  | [0.02356797003366716, 0.026806138344397157]  |      0.888647  |
| stave_B2        | adaptive_template_scale | 24528 |        0.273882    |       0.608029   | [0.5968657630435772, 0.6251066897612229]     |      0.163813  |
| even_amp_ge7000 | adaptive_template_scale |  2299 |       -0.266682    |       0.303734   | [0.29900770183233855, 0.3082514152435602]    |      0.0213136 |
| stave_B2        | adaptive_template_ridge | 24528 |        0.0106748   |       0.0825035  | [0.08072328545464437, 0.08397908770603153]   |      0.743232  |
| even_amp_ge7000 | adaptive_template_ridge |  2299 |        0.00882839  |       0.0574458  | [0.05521774714216731, 0.060385448108503784]  |      0.806873  |
| stave_B2        | ml_hgb                  | 24528 |        0.000349956 |       0.00872017 | [0.008532985279072914, 0.008886825077710783] |      0.981735  |
| even_amp_ge7000 | ml_hgb                  |  2299 |        0.000426816 |       0.00802688 | [0.007635515764635977, 0.008476083804471105] |      0.995215  |

## 5. Leakage audit

- Held-out runs `57, 65` are absent from training: `True`.
- Feature columns include no run/event ids and no odd-channel target samples: `True`.
- Rows with invalid independent target removed after reproduction: 255.
- Run/stave-only median predictor amplitude res68: 1.2297.
- Shuffled-target ML amplitude res68: 0.8131.
- Train/held-out run overlap: `[]`.
- Train/held-out `(run,event,stave)` key overlap: `0`.

The ML result is deliberately not interpreted as absolute detector truth: it is a same-event duplicate-readout closure test. The unusually small ML error is plausible for a duplicate readout but too strong to promote to a physics energy claim without an external charge/energy reference.

## 6. Finding

On independent odd-readout closure, ML amplitude res68 is 0.0091 versus the best traditional amplitude baseline at 0.0858; charge res68 is 0.0151 versus 0.1554. The adaptive template family tests the model-definition hypothesis directly: any remaining ML advantage is treated as duplicate-readout waveform closure, not an absolute true-energy calibration.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template/p04c_amplitude_adaptive_template.py --config reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template/p04c_config.yaml
```
