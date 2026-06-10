# P07f: natural B2 saturation knees from duplicate readout

Ticket `1781019500.1759.55e62bed`. Raw B-stack ROOT was read directly; no Monte Carlo was used.

## Raw reproduction first

| quantity                              | expected     |   reproduced | delta   | pass   |
|:--------------------------------------|:-------------|-------------:|:--------|:-------|
| S00 selected B-stave pulse records    | 640737       |       640737 | 0       | True   |
| P07e high-amplitude B2 duplicate rows | 183132       |       183132 | 0       | True   |
| P07f duplicate-proxy knee rows        | data-derived |       565387 |         | True   |

## Method

Rows are physical B2 pulses with an odd duplicate readout. The duplicate channel is used as an independent size proxy to find where the even B2 amplitude bends away from its low-amplitude response.

- `traditional_duplicate_piecewise`: binned median odd-charge/B2-charge ratio versus B2 amplitude, fit with a constrained linear-to-bent piecewise model; the knee is the fitted upward bend point in B2 ADC.
- `ml_waveform_classifier`: leave-one-run-out ExtraTrees classifier trained on duplicate-derived saturation labels from the other runs, using only even-channel waveform features; the knee is where held-out saturation probability crosses 0.5 versus B2 amplitude.

Each row is held out by run. CIs in `knee_by_run.csv` are event bootstraps of the held-out run with the trained model fixed for the ML method. The summary CI resamples held-out runs.

## Knee summary

| method                          |   runs |   median_knee_adc | run_block_median_knee_adc_ci95   |   run_to_run_iqr_adc |   min_knee_adc |   max_knee_adc |
|:--------------------------------|-------:|------------------:|:---------------------------------|---------------------:|---------------:|---------------:|
| ml_waveform_classifier          |     32 |           8941.88 | [8807.15625, 9014.478125]        |              394.188 |        7480.5  |        9379.5  |
| traditional_duplicate_piecewise |     30 |           2916.17 | [2808.0, 6940.9991376582275]     |             4420.99  |        2497.35 |        7487.02 |

## Traditional run families

| family    |   runs |   median_knee_adc |   min_knee_adc |   max_knee_adc |
|:----------|-------:|------------------:|---------------:|---------------:|
| low-knee  |     18 |           2752.02 |        2497.35 |        3035.64 |
| high-knee |     12 |           7239.7  |        6827.13 |        7487.02 |

## Per-run knees

|   run |   ml_waveform_classifier |   traditional_duplicate_piecewise |
|------:|-------------------------:|----------------------------------:|
|    31 |                  8768.25 |                           7307.06 |
|    32 |                  8948.75 |                           7118.32 |
|    33 |                  8732.5  |                           7261.57 |
|    34 |                  9124    |                           7112.2  |
|    35 |                  8935    |                           2645.9  |
|    36 |                  8747.25 |                           2897.75 |
|    37 |                  9194.5  |                           2907.45 |
|    39 |                  9071.5  |                           2822.4  |
|    40 |                  8952    |                           2668.8  |
|    41 |                  9147    |                           2793.6  |
|    42 |                  8811    |                            nan    |
|    44 |                  9087.5  |                            nan    |
|    45 |                  8863.5  |                           3027.8  |
|    46 |                   nan    |                            nan    |
|    47 |                  8831.75 |                           6827.13 |
|    48 |                  9032.5  |                           2690.8  |
|    49 |                  9014.25 |                           2705.5  |
|    50 |                  9379.5  |                           7137.15 |
|    51 |                  9342.5  |                           7487.02 |
|    52 |                  8803.5  |                           7374.88 |
|    53 |                  9004.5  |                           7263.48 |
|    54 |                  9014.25 |                           7330.76 |
|    55 |                  9304.5  |                           7217.83 |
|    56 |                  9369    |                           7053.4  |
|    57 |                  8979    |                           2676.4  |
|    58 |                  8459.5  |                           2843.67 |
|    59 |                  8300.5  |                           2497.35 |
|    60 |                  7488.5  |                           2774.71 |
|    61 |                  7548    |                           2576.07 |
|    62 |                  7763.5  |                           2556.54 |
|    63 |                  8527.75 |                           2729.33 |
|    64 |                  8176.5  |                           2924.9  |
|    65 |                  7480.5  |                           3035.64 |

Full per-run event-bootstrap intervals and fit diagnostics are in `knee_by_run.csv`.

## Leakage checks

- Split: `leave-one-run-out by run`.
- ML features exclude run id, event id, all odd-channel variables, and held-out duplicate labels.
- Max exact even-waveform hash overlap between train and held-out runs: `0`.
- Median absolute ML-minus-traditional knee difference: `5089.4` ADC.
- Too-good trigger fired: `False`.

## Finding

The duplicate-ratio method does not support a single natural B2 knee. It finds two run families: a low-knee family near 2752 ADC and a high-knee family near 7240 ADC; runs [42, 44, 46] have no stable constrained duplicate-ratio bend. The held-out waveform ML classifier instead places its median knee at 8942 ADC with CI [8807.15625, 9014.478125] (ML minus traditional median +6026 ADC), so it does not validate the duplicate-ratio knee calibration. For production timing/PID, recovered B2 amplitudes should therefore carry run-family systematics and should not be accepted above a fixed 7000 ADC proxy without a per-run duplicate-readout check.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p07f_1781019500_1759_55e62bed_b2_saturation_knees.py --config configs/p07f_1781019500_1759_55e62bed_b2_saturation_knees.json
```
