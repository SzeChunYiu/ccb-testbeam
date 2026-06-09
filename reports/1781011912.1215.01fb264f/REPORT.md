# P04d: adaptive-template scale pathology

- **Ticket ID:** 1781011912.1215.01fb264f
- **Worker:** testbeam-laptop-3
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.
- **Run split:** held-out runs 57, 65; templates/calibrators/ML train only on the other configured runs.

## Raw reproduction first

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

The reproduction gate is the same raw `HRDv` selection used by P04c: baseline-subtracted even-channel B2/B4/B6/B8 peak above 1000 ADC.

## Methods

- **Traditional reference:** train-only per-stave log calibration of the even-channel peak to the odd duplicate-readout amplitude.
- **Scale variants:** adaptive shifted templates with the same amplitude bins and held-out split, varying fit window, additive baseline nuisance, unit-peak template normalization, and Huber loss.
- **Strong traditional method:** per-stave Huber log-amplitude calibrator on the best direct scale diagnostics plus peak, charge, and shape summaries.
- **ML method:** held-out `ExtraTreesRegressor` on the 18 even waveform samples and derived even-channel summaries; run/event ids and odd samples are excluded.

## Held-out amplitude benchmark

| method                                  |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   | run_block_res68_ci95                         |   within_10pct |
|:----------------------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|:---------------------------------------------|---------------:|
| peak_calibrated                         | 26857 |       -0.0666998   |       0.123782   | [0.12223528283253844, 0.1251105116260063]    | [0.10180915216194056, 0.1394391077099221]    |       0.581078 |
| template_direct_whole_l2                | 26857 |        0.243511    |       0.577167   | [0.5647581429310492, 0.5908272515000386]     | [0.42159288191274497, 0.7636846082721858]    |       0.164799 |
| template_signal_window_l2               | 26857 |        0.25405     |       0.607025   | [0.5959647586191805, 0.619997289987061]      | [0.44024412481112773, 0.8035677812459722]    |       0.156942 |
| template_peak_window_l2                 | 26857 |        0.255326    |       0.617194   | [0.6085838483377373, 0.6337715210811629]     | [0.45039341050459863, 0.8224403176960623]    |       0.15724  |
| template_signal_window_baseline_l2      | 26857 |        0.286132    |       0.714292   | [0.6981482418104028, 0.735492095296791]      | [0.5111464784117011, 0.9547032189822027]     |       0.142458 |
| template_peaknorm_signal_window_l2      | 26857 |        0.25199     |       0.601225   | [0.5872453054415359, 0.611954022920219]      | [0.4357133691457666, 0.7896088095858342]     |       0.158804 |
| template_peaknorm_signal_baseline_huber | 26857 |        0.261133    |       0.663712   | [0.6470336494224918, 0.6792510803401481]     | [0.4863565149243741, 0.8715256917781865]     |       0.151394 |
| strong_traditional_huber                | 26857 |        0.00287968  |       0.0202568  | [0.019866247534154707, 0.020631477371369913] | [0.019923532750230427, 0.020689830016525034] |       0.855196 |
| strong_traditional_ridge                | 26857 |        0.00971307  |       0.085725   | [0.08443887285631684, 0.08702549330942366]   | [0.08090500708412265, 0.09078169565172997]   |       0.731578 |
| stave_only_median                       | 26857 |        0.627042    |       1.22972    | [1.2005275030849718, 1.2597809076682316]     | [0.8701635097943986, 1.6368409039032183]     |       0.116804 |
| ml_extra_trees                          | 26857 |       -0.000132927 |       0.00270213 | [0.002627474645672008, 0.00278291291412633]  | [0.002467438388441916, 0.003011053332011981] |       0.981159 |

## Direct scale variant diagnosis

| variant                                 | fit_window   | baseline_nuisance   | peak_normalized_template   | loss   |   median_scale_over_even_amp |   heldout_res68_abs_frac |
|:----------------------------------------|:-------------|:--------------------|:---------------------------|:-------|-----------------------------:|-------------------------:|
| template_direct_whole_l2                | 0-17         | False               | False                      | l2     |                      1.0215  |                 0.577167 |
| template_peaknorm_signal_window_l2      | 4-13         | False               | True                       | l2     |                      1.00505 |                 0.601225 |
| template_signal_window_l2               | 4-13         | False               | False                      | l2     |                      1.02276 |                 0.607025 |
| template_peak_window_l2                 | 5-11         | False               | False                      | l2     |                      1.02218 |                 0.617194 |
| template_peaknorm_signal_baseline_huber | 4-13         | True                | True                       | huber  |                      1.01965 |                 0.663712 |
| template_signal_window_baseline_l2      | 4-13         | True                | False                      | l2     |                      1.0475  |                 0.714292 |

## Per-held-out-run check

| method                   | subset   |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                     |   within_10pct |
|:-------------------------|:---------|------:|-------------------:|-----------------:|:-----------------------------------------------|---------------:|
| peak_calibrated          | run_57   | 13819 |       -0.0498185   |       0.101811   | [0.0997641627312005, 0.10381056489140032]      |       0.672842 |
| peak_calibrated          | run_65   | 13038 |       -0.0862171   |       0.13944    | [0.13701666906510665, 0.14087551563434905]     |       0.483817 |
| template_direct_whole_l2 | run_57   | 13819 |        0.116472    |       0.421594   | [0.4150250974330507, 0.42911199286720997]      |       0.183081 |
| template_direct_whole_l2 | run_65   | 13038 |        0.387883    |       0.763733   | [0.7452732636218811, 0.7817154047757509]       |       0.145421 |
| strong_traditional_huber | run_57   | 13819 |        0.000728534 |       0.0206902  | [0.01988666572044556, 0.021620530652570656]    |       0.842319 |
| strong_traditional_huber | run_65   | 13038 |        0.0050864   |       0.0199257  | [0.019496671857675223, 0.02043730679857672]    |       0.868845 |
| ml_extra_trees           | run_57   | 13819 |       -0.000197448 |       0.00301106 | [0.0028590987886339897, 0.0031252840690072677] |       0.977205 |
| ml_extra_trees           | run_65   | 13038 |       -7.14874e-05 |       0.00246803 | [0.0023818105105939584, 0.0025576553199531255] |       0.985351 |

## Leakage audit

- Held-out runs absent from training: `True`.
- Feature columns include no run/event ids and no odd-channel target samples: `True`.
- Invalid odd-target rows removed after raw reproduction: 255.
- Train/held-out run overlap: `[]`.
- Train/held-out `(run,event,stave)` key overlap: `0`.
- Stave-only median amplitude res68: 1.2297.
- Shuffled-target ML amplitude res68: 0.8078.

## Finding

The direct adaptive-template scale pathology is not primarily fixed by changing the window, adding a baseline nuisance, peak-normalizing the template, or switching the shift-selection loss: the best direct variant is template_direct_whole_l2 at res68=0.5772, still worse than peak_calibrated at 0.1238.  The useful traditional repair is post-fit calibration with diagnostics: strong_traditional_huber reaches res68=0.0203.  ML remains much smaller at res68=0.0027, but the shuffled-target and stave-only sentinels fail as expected, so this is treated as duplicate-readout waveform closure rather than an external energy result.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04d_adaptive_template_scale_pathology.py --config configs/p04d_adaptive_template_scale_pathology.json
```
