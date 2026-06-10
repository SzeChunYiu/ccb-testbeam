# P01e: stricter leakage audit for latent timing probe

**Ticket:** 1781010798.1019.19c63d1a

## Reproduction first
The script read raw B-stack ROOT files from `data/root/root` before modelling.
The P01/S00 selection reproduced **640,737**
selected B-stave pulses versus **640,737** expected.

The prior P01c timing probe was then rebuilt with the original amplitude-bin nuisance
feature before any strict audit:

| method                          | sigma68_ns | published_sigma68_ns | delta_ns | n_pair_residuals | uses_amplitude_bin_feature |
| ------------------------------- | ---------- | -------------------- | -------- | ---------------- | -------------------------- |
| prior P01c reproduced CFD20     | 3.188      | 3.188                | 0.000    | 1224             | True                       |
| prior P01c reproduced ML latent | 1.989      | 1.989                | -0.000   | 1224             | True                       |

## Strict leave-one-run-out audit
Folds hold out each P01c candidate run in `42, 57, 64, 65`.
The strict models use no amplitude-bin feature. CIs are 95% event-block bootstraps.

| method                              | sigma68_ns | ci_low | ci_high | delta_vs_cfd20_ns | n_events | n_pair_residuals |
| ----------------------------------- | ---------- | ------ | ------- | ----------------- | -------- | ---------------- |
| strict traditional hand-shape ridge | 1.962      | 1.882  | 2.064   | -1.227            | 408      | 1224             |
| strict ML AE latent ridge           | 1.965      | 1.885  | 2.058   | -1.223            | 408      | 1224             |
| strict ML event-shuffled target     | 2.056      | 1.948  | 2.165   | -1.133            | 408      | 1224             |
| strict CFD20                        | 3.188      | 3.051  | 3.319   | 0.000             | 408      | 1224             |

By held-out run:

| heldout_run | method                              | sigma68_ns | ci_low | ci_high | n_events | timing_train_rows |
| ----------- | ----------------------------------- | ---------- | ------ | ------- | -------- | ----------------- |
| 42          | strict CFD20                        | 3.305      | 3.053  | 3.571   | 68       | 15666             |
| 42          | strict traditional hand-shape ridge | 1.704      | 1.546  | 1.988   | 68       | 15666             |
| 42          | strict ML AE latent ridge           | 1.757      | 1.472  | 2.047   | 68       | 15666             |
| 57          | strict CFD20                        | 3.265      | 2.807  | 3.631   | 64       | 15678             |
| 57          | strict traditional hand-shape ridge | 2.015      | 1.787  | 2.239   | 64       | 15678             |
| 57          | strict ML AE latent ridge           | 2.027      | 1.773  | 2.247   | 64       | 15678             |
| 64          | strict CFD20                        | 3.147      | 2.977  | 3.328   | 210      | 15240             |
| 64          | strict traditional hand-shape ridge | 2.004      | 1.826  | 2.130   | 210      | 15240             |
| 64          | strict ML AE latent ridge           | 1.980      | 1.857  | 2.082   | 210      | 15240             |
| 65          | strict CFD20                        | 2.993      | 2.677  | 3.405   | 66       | 15672             |
| 65          | strict traditional hand-shape ridge | 1.958      | 1.723  | 2.186   | 66       | 15672             |
| 65          | strict ML AE latent ridge           | 1.941      | 1.610  | 2.147   | 66       | 15672             |

Traditional method: ridge residual correction from hand waveform shape features plus
log-amplitude and stave one-hot. ML method: masked-denoising AE-4 trained only on
train runs, followed by the same ridge residual correction on latent variables plus
log-amplitude and stave one-hot.

## Leakage checks
| check                       | value | pass_all | detail                                                                                    |
| --------------------------- | ----- | -------- | ----------------------------------------------------------------------------------------- |
| amplitude_bin_feature_used  | 0     | True     | strict features are waveform shape or AE latent plus log amplitude and stave one-hot only |
| feature_audit               | 0     | True     | no run id, event id, event order, amplitude-bin id, or held-out target columns            |
| train_heldout_event_overlap | 0     | True     | must be zero                                                                              |
| train_heldout_run_overlap   | 0     | True     | must be zero                                                                              |

The shuffled-event target row is a negative control: the train targets are permuted
as event blocks before fitting the ML residual model. Train-run-only calibration
curves are in `fig_train_run_only_calibration.png` and `train_run_only_calibration.csv`.

## Frozen S02/S03 comparison
These are fixed reference numbers from prior raw-ROOT studies; their scopes differ
from the four-run P01e audit and are listed explicitly.

| method                 | scope                              | sigma68_ns | source                                                             |
| ---------------------- | ---------------------------------- | ---------- | ------------------------------------------------------------------ |
| S02 global template    | run65 only                         | 2.889      | reports/1781000705.514762.105c186b__s02b_template_timewalk_closure |
| S02 ML ridge           | run65 only                         | 1.846      | configs/s02c_run_drift_timewalk.json                               |
| S03 analytic timewalk  | run65 only                         | 1.495      | configs/s03b_amp_binned_monotonic_timewalk.yaml                    |
| S03c analytic timewalk | Sample-II leave-one-run-out pooled | 1.551      | reports/1781005627.1877.378c7a87/pooled_run_bootstrap.csv          |

## Verdict
The strict ML pooled sigma68 is **1.965 ns** versus
**1.962 ns** for the strong traditional residual model
and **2.056 ns** for the event-shuffled target control.
Decision: **not accepted as a robust improvement**. The original P01c number is reproducible, but the stricter
run-fold and shuffled-event controls are the numbers to trust for this audit.

No Monte Carlo was used.
