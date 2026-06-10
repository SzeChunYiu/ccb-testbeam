# P01f: diagnose event-shuffled timing-control strength

**Ticket:** `1781018587.1208.05763e48`  
**Worker:** `testbeam-laptop-1`  
**No Monte Carlo:** raw B-stack ROOT only; resampling is held-out event-block bootstrap.

## Reproduction first
The script read raw ROOT from `data/root/root` and reproduced
**640,737** selected B-stave pulses versus
**640,737** expected before modelling.

The quoted P01e timing-control numbers were then rebuilt on the same raw scan:

| method                          | sigma68_ns | published_sigma68_ns | delta_ns | n_pair_residuals |
| ------------------------------- | ---------- | -------------------- | -------- | ---------------- |
| prior P01c reproduced CFD20     | 3.188      | 3.188                | 0.000    | 1224             |
| prior P01c reproduced ML latent | 1.989      | 1.989                | -0.000   | 1224             |

| method                              | sigma68_ns | ci_low | ci_high | delta_vs_cfd20_ns | n_events | n_pair_residuals |
| ----------------------------------- | ---------- | ------ | ------- | ----------------- | -------- | ---------------- |
| strict traditional hand-shape ridge | 1.962      | 1.865  | 2.063   | -1.227            | 408      | 1224             |
| strict ML AE latent ridge           | 1.965      | 1.891  | 2.054   | -1.223            | 408      | 1224             |
| strict ML event-shuffled target     | 2.056      | 1.949  | 2.173   | -1.133            | 408      | 1224             |
| strict CFD20                        | 3.188      | 3.052  | 3.303   | 0.000             | 408      | 1224             |

This reproduces the suspicious control: CFD20 is `3.188 ns`, while the ML
event-shuffled target still reaches `2.056 ns`.

## Variant battery
Each fold holds out one run in `42, 57, 64, 65`.
Rows below collapse seven seeds per shuffle family unless noted. The traditional
feature set is hand waveform shape plus log-amplitude and stave; the ML feature
set is AE-4 latent plus the same nuisance terms.

| feature_family | target_variant                        | diagnosis_family                   | seed_repeats | sigma68_median_ns | sigma68_min_ns | sigma68_max_ns | delta_vs_cfd20_median_ns |
| -------------- | ------------------------------------- | ---------------------------------- | ------------ | ----------------- | -------------- | -------------- | ------------------------ |
| ml_ae          | ml_ae_nominal                         | nominal                            | 1            | 1.952             | 1.952          | 1.952          | -1.214                   |
| ml_ae          | ml_ae_per_run_stave_amp_shuffle       | train-run/stave/amplitude nuisance | 28           | 2.003             | 1.787          | 2.105          | -1.191                   |
| ml_ae          | ml_ae_per_run_stave_shuffle           | train-run/stave nuisance           | 28           | 2.010             | 1.785          | 2.154          | -1.096                   |
| ml_ae          | ml_ae_train_run_stave_mean            | train-run-only target              | 4            | 2.017             | 1.807          | 2.129          | -1.112                   |
| ml_ae          | ml_ae_event_block_shuffle             | event/block composition            | 28           | 2.023             | 1.798          | 2.138          | -1.107                   |
| ml_ae          | ml_ae_same_event_permute              | same-event target algebra          | 28           | 3.187             | 2.866          | 3.401          | -0.006                   |
| ml_ae          | ml_ae_row_shuffle                     | global row target distribution     | 28           | 3.210             | 2.852          | 3.399          | 0.022                    |
| ml_ae          | ml_ae_same_event_sign_flip            | same-event target algebra          | 28           | 3.217             | 2.904          | 3.433          | 0.016                    |
| timing         | CFD20                                 | baseline                           | 1            | 3.167             | 3.167          | 3.167          | 0.000                    |
| traditional    | traditional_nominal                   | nominal                            | 1            | 1.948             | 1.948          | 1.948          | -1.218                   |
| traditional    | traditional_per_run_stave_amp_shuffle | train-run/stave/amplitude nuisance | 28           | 2.001             | 1.750          | 2.100          | -1.173                   |
| traditional    | traditional_event_block_shuffle       | event/block composition            | 28           | 2.013             | 1.767          | 2.165          | -1.098                   |
| traditional    | traditional_train_run_stave_mean      | train-run-only target              | 4            | 2.017             | 1.804          | 2.133          | -1.112                   |
| traditional    | traditional_per_run_stave_shuffle     | train-run/stave nuisance           | 28           | 2.017             | 1.779          | 2.169          | -1.113                   |
| traditional    | traditional_same_event_sign_flip      | same-event target algebra          | 28           | 3.170             | 2.894          | 3.453          | 0.025                    |
| traditional    | traditional_same_event_permute        | same-event target algebra          | 28           | 3.177             | 2.921          | 3.443          | -0.001                   |
| traditional    | traditional_row_shuffle               | global row target distribution     | 28           | 3.199             | 2.886          | 3.401          | 0.026                    |

## Leakage audit
| check                       | value | pass_all | detail                                                                                    |
| --------------------------- | ----- | -------- | ----------------------------------------------------------------------------------------- |
| amplitude_bin_feature_used  | 0     | True     | strict features are waveform shape or AE latent plus log amplitude and stave one-hot only |
| feature_audit               | 0     | True     | no run id, event id, event order, amplitude-bin id, or held-out target columns            |
| train_heldout_event_overlap | 0     | True     | must be zero                                                                              |
| train_heldout_run_overlap   | 0     | True     | must be zero                                                                              |

## Pass/fail rules
| rule                                     | value      | threshold  | pass  | interpretation                                                                   |
| ---------------------------------------- | ---------- | ---------- | ----- | -------------------------------------------------------------------------------- |
| raw_count_reproduced                     | 640737.000 | 640737.000 | True  | raw ROOT selection gate passed before modelling                                  |
| nominal_ml_beats_strong_traditional      | 0.003      | 0.000      | False | latent timing claim should exceed a hand-shape residual model with separated CIs |
| event_shuffle_not_close_to_nominal       | 0.090      | 0.200      | False | event-shuffled control should be clearly worse than the nominal ML probe         |
| control_gain_fraction_below_limit        | 1.176      | 0.600      | False | shuffled controls should not recover most of the nominal CFD20 gain              |
| quoted_event_shuffle_strength_reproduced | 2.056      | 2.056      | True  | the suspicious P01e control is reproduced exactly before diagnosis               |

## Verdict
Decision: **fail for physical interpretation**. The event-shuffled target strength is not an exact row
leak: global row shuffles and same-event sign/permutation controls fall back to
CFD20-like widths, while event-block, per-run/stave, per-run/stave/amplitude, and
train-run-only targets keep most of the gain. That points to train-run waveform
composition, stave/amplitude structure, and event-block target construction as
the dominant explanation. A residual timing probe should only be interpreted
physically when the nominal model beats the strong traditional baseline and
every shuffled/stratified target control is well separated from the nominal
improvement.
