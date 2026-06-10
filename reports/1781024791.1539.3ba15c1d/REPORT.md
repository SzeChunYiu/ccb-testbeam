# P04i: duplicate-readout charge closure sample-causality map

- **Ticket ID:** 1781024791.1539.3ba15c1d
- **Worker:** testbeam-laptop-3
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.
- **Run split:** held-out runs 57, 65; all templates, calibrators, and ML models train on other runs.

## Raw reproduction first

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

Registered P04 charge HGB reference res68 is `0.0150719202`; the ticket-local raw-root HGB benchmark with capped training rows gives `0.3836559898` (delta `+0.369`).

## Methods

- **Traditional:** peak-to-charge, integral-to-charge, adaptive-template scale, and a Huber charge calibrator from even-waveform summaries.
- **ML:** HGB and ExtraTrees charge regressors using only the 18 even samples plus even-channel summaries and stave one-hot.
- **Ablations:** grouped sample replacement by train-run stave medians, frozen-model held-out occlusion/permutation, grouped retraining, and single-sample frozen occlusion.

## Full held-out benchmark

| method                             |     n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |   full_rms_frac |   within_10pct |
|:-----------------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|----------------:|---------------:|
| peak_to_charge_calibrated          | 26857 |       -0.210687    |       0.280164   | [0.2634333424735638, 0.3057120089996927]     |        2.57877  |       0.129128 |
| integral_calibrated                | 26857 |       -0.0911845   |       0.195412   | [0.1641635066281698, 0.21526889544236236]    |        1.66374  |       0.403321 |
| adaptive_template_scale_calibrated | 26857 |        0.0981146   |       0.550393   | [0.3883858073098749, 0.7001958472175158]     |        2.51087  |       0.188107 |
| strong_huber_charge                | 26857 |        0.0002984   |       0.0126848  | [0.012434474334552015, 0.013051467849113466] |      480.376    |       0.882973 |
| ml_hgb                             | 26857 |        0.131333    |       0.391911   | [0.31333413263232146, 0.497064176143259]     |        1.58365  |       0.185017 |
| ml_extra_trees                     | 26857 |        0.000138919 |       0.00713825 | [0.006902229804116988, 0.007435204793670533] |        0.294669 |       0.967346 |

## Grouped retraining deltas

| ablation                          | method              |   res68_abs_frac |   delta_res68_vs_full | run_block_delta_res68_ci95                      |
|:----------------------------------|:--------------------|-----------------:|----------------------:|:------------------------------------------------|
| post_peak_tail_s11_17_removed     | ml_extra_trees      |       0.021673   |           0.0145347   | [0.011237324605326355, 0.017738483828348747]    |
| early_peak_s4_6_removed           | ml_extra_trees      |       0.0165866  |           0.00944836  | [0.008037611964268762, 0.010786568952079207]    |
| peak_core_s7_10_removed           | ml_extra_trees      |       0.0129277  |           0.00578948  | [0.004157041485648686, 0.007288205977308636]    |
| baseline_s0_3_removed             | ml_extra_trees      |       0.0082398  |           0.00110155  | [0.0009119292921532275, 0.0013206568184707893]  |
| saturation_boundary_atoms_removed | ml_extra_trees      |       0.00804152 |           0.000903272 | [0.00025704241826955253, 0.0015287331705072325] |
| post_peak_tail_s11_17_removed     | ml_hgb              |       0.415543   |           0.0236323   | [0.0047604710644587045, 0.04679037220295218]    |
| peak_core_s7_10_removed           | ml_hgb              |       0.408105   |           0.0161944   | [-0.0008543175547180426, 0.03233917854988094]   |
| early_peak_s4_6_removed           | ml_hgb              |       0.40309    |           0.0111798   | [0.0012006399003509083, 0.05190126864813299]    |
| saturation_boundary_atoms_removed | ml_hgb              |       0.389884   |          -0.0020271   | [-0.002027097457118765, -0.0012674115537884]    |
| baseline_s0_3_removed             | ml_hgb              |       0.381397   |          -0.0105137   | [-0.010513728005146716, 0.0025582827125588126]  |
| early_peak_s4_6_removed           | strong_huber_charge |       0.102056   |           0.0893713   | [0.08382762782365984, 0.09451018158032715]      |
| post_peak_tail_s11_17_removed     | strong_huber_charge |       0.0560611  |           0.0433763   | [0.04274622057899927, 0.0436110763324931]       |
| peak_core_s7_10_removed           | strong_huber_charge |       0.050267   |           0.0375822   | [0.031057684936843966, 0.04208384234614061]     |
| saturation_boundary_atoms_removed | strong_huber_charge |       0.0425356  |           0.0298508   | [0.023572488272750994, 0.03744069841767814]     |
| baseline_s0_3_removed             | strong_huber_charge |       0.0289565  |           0.0162717   | [0.015373039623096281, 0.01782673342433075]     |

## Frozen ML occlusion/permutation deltas

| mode               | ablation                      | method         |   res68_abs_frac |   delta_res68_vs_full | run_block_delta_res68_ci95                     |
|:-------------------|:------------------------------|:---------------|-----------------:|----------------------:|:-----------------------------------------------|
| frozen_occlusion   | post_peak_tail_s11_17_removed | ml_extra_trees |       0.922725   |            0.915587   | [0.6033200888875756, 1.177115868129457]        |
| frozen_occlusion   | peak_core_s7_10_removed       | ml_extra_trees |       0.582128   |            0.574989   | [0.35678115736567234, 0.7981096917853168]      |
| frozen_occlusion   | early_peak_s4_6_removed       | ml_extra_trees |       0.376828   |            0.369689   | [0.21338088994532128, 0.47862201731210713]     |
| frozen_occlusion   | baseline_s0_3_removed         | ml_extra_trees |       0.00833857 |            0.00120032 | [0.0008178875336623684, 0.0016092292115524216] |
| frozen_permutation | post_peak_tail_s11_17_removed | ml_extra_trees |       0.443974   |            0.436836   | [0.3945777081592503, 0.5143921850371156]       |
| frozen_permutation | peak_core_s7_10_removed       | ml_extra_trees |       0.347652   |            0.340513   | [0.2603580501660347, 0.47587626462434063]      |
| frozen_permutation | early_peak_s4_6_removed       | ml_extra_trees |       0.202015   |            0.194876   | [0.16366154027716434, 0.26419064293996086]     |
| frozen_permutation | baseline_s0_3_removed         | ml_extra_trees |       0.0457315  |            0.0385932  | [0.03459409456038946, 0.04292199378347501]     |
| frozen_occlusion   | peak_core_s7_10_removed       | ml_hgb         |       0.859093   |            0.467182   | [0.32716477136413824, 0.5486418710526249]      |
| frozen_occlusion   | post_peak_tail_s11_17_removed | ml_hgb         |       0.772447   |            0.380537   | [0.1395909255311994, 0.5714324125025843]       |
| frozen_occlusion   | early_peak_s4_6_removed       | ml_hgb         |       0.467531   |            0.0756202  | [0.0266799684565735, 0.15296028532946232]      |
| frozen_occlusion   | baseline_s0_3_removed         | ml_hgb         |       0.398085   |            0.00617411 | [0.0038014485628161676, 0.018902629620555278]  |
| frozen_permutation | peak_core_s7_10_removed       | ml_hgb         |       0.625391   |            0.23348    | [0.21473427679604828, 0.3082746166910016]      |
| frozen_permutation | post_peak_tail_s11_17_removed | ml_hgb         |       0.618461   |            0.22655    | [0.20229836216971742, 0.3588443610372502]      |
| frozen_permutation | early_peak_s4_6_removed       | ml_hgb         |       0.40551    |            0.013599   | [0.013354546603074835, 0.04429142555244786]    |
| frozen_permutation | baseline_s0_3_removed         | ml_hgb         |       0.36258    |           -0.0293304  | [-0.06038405008552683, -0.00958261397996435]   |

## Single-sample HGB occlusion

|   sample |   res68_abs_frac |   delta_res68_vs_full |
|---------:|-----------------:|----------------------:|
|       10 |         0.828064 |           0.436153    |
|       11 |         0.741069 |           0.349158    |
|        6 |         0.460616 |           0.068705    |
|        5 |         0.45004  |           0.0581292   |
|        7 |         0.448817 |           0.056906    |
|       17 |         0.437082 |           0.0451713   |
|       12 |         0.434769 |           0.0428581   |
|        9 |         0.433956 |           0.0420449   |
|       13 |         0.432799 |           0.0408882   |
|       15 |         0.43185  |           0.0399391   |
|       16 |         0.43185  |           0.0399391   |
|       14 |         0.431474 |           0.0395638   |
|        8 |         0.430243 |           0.0383322   |
|        4 |         0.409453 |           0.0175422   |
|        2 |         0.395728 |           0.00381737  |
|        3 |         0.394719 |           0.00280865  |
|        0 |         0.392031 |           0.000120188 |
|        1 |         0.391911 |           0           |

## ML minus strong traditional

| method         | reference_method    |   delta_res68_abs_frac | run_block_delta_res68_ci95                     |
|:---------------|:--------------------|-----------------------:|:-----------------------------------------------|
| ml_hgb         | strong_huber_charge |             0.379226   | [0.300282664783208, 0.48462970180870696]       |
| ml_extra_trees | strong_huber_charge |            -0.00554655 | [-0.005616263055442933, -0.005532244530435028] |

## Leakage audit

- Held-out runs absent from training: `True`.
- Train/held-out `(run,event,stave)` key overlap: `0`.
- Exact rounded even-waveform hash overlap: `0`.
- Feature columns include no run/event ids and no odd-channel target samples: `True`.
- Invalid odd-target rows removed after raw reproduction: `255`.
- Stave-only median charge res68: `1.8979`.
- Shuffled-target HGB charge res68: `1.0366`.

## Finding

The raw selected-pulse count reproduces exactly first, and the ticket-local P04 charge HGB benchmark gives res68=0.383656 versus the registered reference 0.015072. On the P04i full split, strong traditional Huber is the best traditional charge closure (res68=0.0127), while HGB and ExtraTrees reach 0.3919 and 0.0071. The largest HGB grouped-retrain degradation is post_peak_tail_s11_17_removed (delta res68=+0.0236); the largest single-sample frozen HGB occlusion atom is sample 10 (delta res68=+0.4362). Shuffled-target and stave-only sentinels are broad (1.0366 and 1.8979), so the very sharp ML result is not explained by run leakage, exact waveform duplicates, or context-only prediction; it remains a same-detector duplicate-readout closure rather than an external energy calibration.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04i_1781024791_1539_3ba15c1d_sample_causality.py --config configs/p04i_1781024791_1539_3ba15c1d_sample_causality.json
```
