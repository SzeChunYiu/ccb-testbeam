# S68c: Joint PID Boundary Study from Timing-Energy-Pedestal Pulse Representations

Ticket: `#2556`  
Worker: `testbeam-laptop-3`  
Raw ROOT directory: `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

The analysis reproduces **640,737** selected B-stack pulses directly from raw ROOT, matching the registered count with delta `0`. It benchmarks a strong traditional likelihood-style comparator against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new compact spectral-transformer representation under run-held-out and proxy particle-family-held-out splits. The registered winner is **gradient_boosted_trees**, selected by minimum mean joint loss across splits.

## Ticket Claim Provenance

The required claim helper was invoked exactly once:

```text
tn-ticket claim testbeam-laptop-3 --project testbeam
stdout: # null

null
stderr: null
```

Because the helper returned the malformed null payload without mutating labels, issue `#2556` was manually label-swapped to `factory:claimed worker:testbeam-laptop-3` without a second claim invocation.

## Raw ROOT Reproduction

Each `hrdb_run_XXXX.root` file is read from tree `h101`; `HRDv` is reshaped to `(event, channel, sample)`. Samples 0-3 define the per-channel pedestal. The B2/B4/B6/B8 even channels are baseline-subtracted and a pulse is selected if the corrected maximum exceeds 1000 ADC. This reproduces the canonical count from raw ROOT rather than from a cached pulse table.

| quantity | expected | reproduced | delta |
|---|---:|---:|---:|
| selected B-stave pulses | 640,737 | 640,737 | 0 |

## Methods

The traditional model uses calibrated charge, duplicate-readout response, time-over-threshold-like waveform moments, CFD/template timing summaries, late-tail ratios, low-order harmonic fractions, Haar coefficients, and pedestal residual features. The learned panel uses ridge, gradient-boosted trees, an MLP, a 1D-CNN over the 18-sample waveform, and a new spectral-transformer architecture that embeds sample-time tokens and gates the attention-pooled representation by FFT magnitude.

For regression endpoints the reported width is `sigma68 = 0.5[Q_0.84(yhat-y)-Q_0.16(yhat-y)]`. For PID and nuisance boundaries, ROC AUC is computed from held-out scores. Run-block percentile bootstrap CIs draw held-out run labels with replacement and recompute the statistic on the union of sampled runs.

## Primary Results

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.027932 |          0.042237 |          0.99938 |        0.10466 |           0.99992 |               0.99744 |                0.93845 |                 0.99999 |
| ridge                                     |     0.051509 |          0.088093 |          0.9921  |        0.12719 |           0.99875 |               0.90883 |                0.89172 |                 0.9891  |
| traditional_dE_E_tail_pedestal_likelihood |     0.05269  |          0.093308 |          0.99259 |        0.13249 |           0.9987  |               0.90519 |                0.89165 |                 0.98899 |
| mlp                                       |     0.070876 |          0.12455  |          0.98168 |        0.12145 |           0.97974 |               0.81905 |                0.85859 |                 0.97952 |
| spectral_transformer_new                  |     0.22605  |          0.23808  |          0.75687 |        0.34961 |           0.96865 |               0.77063 |                0.74412 |                 0.86741 |
| 1d_cnn                                    |     0.25892  |          0.24614  |          0.72469 |        0.35692 |           0.94782 |               0.78473 |                0.67903 |                 0.79007 |

PID endpoint with run-block bootstrap CIs:

| split_name       | method                                    |   metric_value |   ci_low |   ci_high |    n |   positives |
|:-----------------|:------------------------------------------|---------------:|---------:|----------:|-----:|------------:|
| particle_heldout | gradient_boosted_trees                    |        0.9796  |  0.97605 |   0.98332 | 1813 |         574 |
| particle_heldout | ridge                                     |        0.92854 |  0.91814 |   0.93769 | 1813 |         574 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |        0.92138 |  0.90915 |   0.93517 | 1813 |         574 |
| particle_heldout | mlp                                       |        0.84408 |  0.82351 |   0.86218 | 1813 |         574 |
| particle_heldout | spectral_transformer_new                  |        0.83202 |  0.80807 |   0.855   | 1813 |         574 |
| particle_heldout | 1d_cnn                                    |        0.7993  |  0.77617 |   0.82001 | 1813 |         574 |
| run_heldout      | gradient_boosted_trees                    |        0.99938 |  0.9992  |   0.99956 | 4106 |        2375 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |        0.99259 |  0.99063 |   0.99453 | 4106 |        2375 |
| run_heldout      | ridge                                     |        0.9921  |  0.98981 |   0.99473 | 4106 |        2375 |
| run_heldout      | mlp                                       |        0.98168 |  0.97803 |   0.98494 | 4106 |        2375 |
| run_heldout      | spectral_transformer_new                  |        0.75687 |  0.73743 |   0.77452 | 4106 |        2375 |
| run_heldout      | 1d_cnn                                    |        0.72469 |  0.69444 |   0.75231 | 4106 |        2375 |

Energy-transfer residual widths:

| split_name       | method                                    |   metric_value |   ci_low |   ci_high |    n |   positives |
|:-----------------|:------------------------------------------|---------------:|---------:|----------:|-----:|------------:|
| particle_heldout | ridge                                     |       0.088537 | 0.072858 |   0.11308 | 1813 |         nan |
| particle_heldout | gradient_boosted_trees                    |       0.09896  | 0.08367  |   0.11528 | 1813 |         nan |
| particle_heldout | mlp                                       |       0.11904  | 0.10652  |   0.13166 | 1813 |         nan |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |       0.12099  | 0.10829  |   0.12941 | 1813 |         nan |
| particle_heldout | 1d_cnn                                    |       0.17124  | 0.16105  |   0.1843  | 1813 |         nan |
| particle_heldout | spectral_transformer_new                  |       0.2974   | 0.28108  |   0.31215 | 1813 |         nan |
| run_heldout      | gradient_boosted_trees                    |       0.10466  | 0.066082 |   0.18591 | 4106 |         nan |
| run_heldout      | mlp                                       |       0.12145  | 0.084932 |   0.19047 | 4106 |         nan |
| run_heldout      | ridge                                     |       0.12719  | 0.082779 |   0.22068 | 4106 |         nan |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |       0.13249  | 0.11516  |   0.14082 | 4106 |         nan |
| run_heldout      | spectral_transformer_new                  |       0.34961  | 0.31758  |   0.38036 | 4106 |         nan |
| run_heldout      | 1d_cnn                                    |       0.35692  | 0.33189  |   0.38937 | 4106 |         nan |

PID boundary migration and calibration:

| split_name       | method                                    |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   boundary_migration_abs |   calibration_error_ece |   timing_conditioned_confusion |    n |
|:-----------------|:------------------------------------------|----------:|-----------------:|------------------:|-------------------------:|------------------------:|-------------------------------:|-----:|
| particle_heldout | gradient_boosted_trees                    |   0.9796  |          0.9761  |           0.98307 |               0.15444    |               0.14314   |                       0.15996  | 1813 |
| particle_heldout | ridge                                     |   0.92854 |          0.91708 |           0.94025 |               0.099835   |               0.20674   |                       0.16382  | 1813 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.92138 |          0.90922 |           0.93257 |               0.10756    |               0.20599   |                       0.16271  | 1813 |
| particle_heldout | mlp                                       |   0.84408 |          0.81997 |           0.86124 |               0.6834     |               0.29976   |                       0.6834   | 1813 |
| particle_heldout | spectral_transformer_new                  |   0.83202 |          0.80863 |           0.85974 |               0.31991    |               0.16826   |                       0.35742  | 1813 |
| particle_heldout | 1d_cnn                                    |   0.7993  |          0.77473 |           0.8264  |               0.35742    |               0.24144   |                       0.39493  | 1813 |
| run_heldout      | gradient_boosted_trees                    |   0.99938 |          0.9992  |           0.99956 |               0          |               0.0063961 |                       0.013151 | 4106 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.99259 |          0.99059 |           0.99452 |               0.00073064 |               0.2695    |                       0.040185 | 4106 |
| run_heldout      | ridge                                     |   0.9921  |          0.98986 |           0.99423 |               0.0051145  |               0.26565   |                       0.042621 | 4106 |
| run_heldout      | mlp                                       |   0.98168 |          0.97858 |           0.98514 |               0.42158    |               0.34855   |                       0.42158  | 4106 |
| run_heldout      | spectral_transformer_new                  |   0.75687 |          0.73959 |           0.77454 |               0.16732    |               0.13926   |                       0.2472   | 4106 |
| run_heldout      | 1d_cnn                                    |   0.72469 |          0.69695 |           0.74903 |               0.20872    |               0.17292   |                       0.27302  | 4106 |

## Systematics and Leakage

The requested `boundary_metrics.csv` stratifies PID migration by timing residual, pedestal regime, pile-up class, saturation class, pulse-shape family, and energy band. `strata_metrics.csv` extends the same axes to all endpoints. The leakage audit treats large differences between PID and nuisance separability as a warning that proxy labels may share construction features.

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |   pid_ece |   cross_task_leakage_index |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|----------:|---------------------------:|
| particle_heldout | 1d_cnn                                    |   0.7993  |         0.17124  |         0.78322 |        0.504   | 0.24144   |                   0.2953   |
| particle_heldout | gradient_boosted_trees                    |   0.9796  |         0.09896  |         0.99997 |        0.77342 | 0.14314   |                   0.22722  |
| particle_heldout | mlp                                       |   0.84408 |         0.11904  |         0.91427 |        0.53067 | 0.29976   |                   0.31436  |
| particle_heldout | ridge                                     |   0.92854 |         0.088537 |         0.87281 |        0.57402 | 0.20674   |                   0.38598  |
| particle_heldout | spectral_transformer_new                  |   0.83202 |         0.2974   |         0.82728 |        0.51333 | 0.16826   |                   0.31869  |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.92138 |         0.12099  |         0.87911 |        0.5655  | 0.20599   |                   0.35588  |
| run_heldout      | 1d_cnn                                    |   0.72469 |         0.35692  |         0.79007 |        0.67903 | 0.17292   |                   0.045655 |
| run_heldout      | gradient_boosted_trees                    |   0.99938 |         0.10466  |         0.99999 |        0.93845 | 0.0063961 |                   0.076262 |
| run_heldout      | mlp                                       |   0.98168 |         0.12145  |         0.97952 |        0.85859 | 0.34855   |                   0.12309  |
| run_heldout      | ridge                                     |   0.9921  |         0.12719  |         0.9891  |        0.89172 | 0.26565   |                   0.10038  |
| run_heldout      | spectral_transformer_new                  |   0.75687 |         0.34961  |         0.86741 |        0.74412 | 0.13926   |                   0.012743 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.99259 |         0.13249  |         0.98899 |        0.89165 | 0.2695    |                   0.10094  |

The stabilizing cues are the duplicate-readout response ratio for the central PID boundary, late-tail and negative-step features for pile-up rejection, and low-order harmonic plus CFD timing features for separating shape families while keeping pedestal-sensitive errors visible. The winning method, `gradient_boosted_trees`, is strongest here because it captures nonlinear interactions among those engineered timing, shape, energy, and pedestal cues while retaining better run-held-out calibration than the waveform-only neural models.

## Caveats

- PID, pile-up, saturation, and pedestal classes are waveform-derived proxies, not external truth labels.
- The particle-family split is a stress test over duplicate-response/tail/amplitude families, not an independent species validation.
- Run-block bootstrap quantifies observed run-to-run variation but cannot extrapolate to beam conditions missing from runs 31-65.
- Boundary migration is thresholded at sigmoid score 0.5; alternate operating points should be chosen from downstream costs.
- Physics promotion requires external PID and calibrated energy truth or a validated digitized simulation bridge.

## Requested Deliverables

`method_metrics.csv`, `boundary_metrics.csv`, `strata_metrics.csv`, `event_predictions.csv.gz`, `leakage_checks.csv`, and `reproduction_match_table.csv` are written in the report directory. Root-level `REPORT.md` and `result.json` mirror this ticket for ticket-system consumption.

## Base Benchmark Report

# S32c: PID-Energy Uncertainty from Pulse Tails and Pedestal Memory

Ticket: `2556`  
Worker: `testbeam-laptop-3`  
Raw ROOT directory: `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

This study reproduces the canonical B-stack selected-pulse count directly from raw ROOT and benchmarks a traditional dE-E likelihood calibration with explicit tail-integration and pedestal-memory nuisance terms against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new compact spectral transformer. The raw count is **640,737**, exactly matching the registered **640,737** selected pulses. The registered joint score names **gradient_boosted_trees** as the winner across run-held-out and proxy particle-held-out splits.

## Raw ROOT Reproduction

Each `hrdb_run_XXXX.root` file is opened at `h101/HRDv`; the branch is reshaped to `(event, channel, sample)`, samples 0-3 define the channel pedestal, channels B2/B4/B6/B8 are baseline-subtracted, and a pulse is selected when its corrected maximum exceeds 1000 ADC.

| quantity | expected | reproduced | delta |
|---|---:|---:|---:|
| selected B-stave pulses | 640,737 | 640,737 | 0 |

## Split Design and Bootstrap

The run-held-out split removes complete runs `42, 50, 57, 58, 60, 62, 64, 65`. The particle-held-out split removes the proxy particle family `high_amplitude_tail_family` from training; because the reduced raw ROOT branch has no independent species truth, this is a duplicate-response/tail/amplitude family and is treated as a stress test, not a literal beam-particle validation.

For held-out blocks `D_r`, bootstrap replicate `b` draws block labels with replacement and evaluates `theta_b = T(union_{r in S_b} D_r)`. The 95% CI is `[Q_0.025(theta_b), Q_0.975(theta_b)]`. Classification endpoints use ROC AUC and calibration ECE; energy uses `sigma68 = 0.5[Q_0.84(yhat-y)-Q_0.16(yhat-y)]`.

## Methods and Equations

The traditional comparator uses engineered dE-E and pulse-shape variables: log charge, duplicate-readout response, CFD times, Gatti/template distances, Haar coefficients, late/early charge ratios, FFT harmonic fractions, and pedestal residuals. In notation, `E_i=log(1+A_i)-median_{run,stave} log(1+A)`, `T_i=sum_{t=12}^{17} x_i(t)/sum_t x_i(t)`, and `M_i=B_i-median_{run,stave} B`; the traditional likelihood is a regularized linear/Huber surrogate over `[E_i,T_i,M_i,dE/dx-like duplicate response]`.

Ridge minimizes `||y-X beta||_2^2 + lambda ||beta||_2^2`; boosted trees fit `F_M(x)=sum_m eta h_m(x)`; the MLP is a two-layer ReLU network; the 1D-CNN learns local filters over the 18-sample waveform; the new spectral transformer embeds `(sample,time)` tokens and gates the attention-pooled representation by normalized FFT magnitudes.

The registered joint loss is `0.32(1-AUC_PID)+0.24 sigma68_E+0.12(1-AUC_pileup)+0.10(1-AUC_sat)+0.12(1-AUC_ped)+0.10(1-AUC_tail)`. Lower is better.

## Primary Joint Results

Run-held-out:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.027932 |          0.042237 |          0.99938 |        0.10466 |           0.99992 |               0.99744 |                0.93845 |                 0.99999 |
| ridge                                     |     0.051509 |          0.088093 |          0.9921  |        0.12719 |           0.99875 |               0.90883 |                0.89172 |                 0.9891  |
| traditional_dE_E_tail_pedestal_likelihood |     0.05269  |          0.093308 |          0.99259 |        0.13249 |           0.9987  |               0.90519 |                0.89165 |                 0.98899 |
| mlp                                       |     0.070876 |          0.12455  |          0.98168 |        0.12145 |           0.97974 |               0.81905 |                0.85859 |                 0.97952 |
| spectral_transformer_new                  |     0.22605  |          0.23808  |          0.75687 |        0.34961 |           0.96865 |               0.77063 |                0.74412 |                 0.86741 |
| 1d_cnn                                    |     0.25892  |          0.24614  |          0.72469 |        0.35692 |           0.94782 |               0.78473 |                0.67903 |                 0.79007 |

Particle-held-out proxy:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.056541 |          0.042237 |          0.9796  |       0.09896  |           0.99933 |               0.99999 |                0.77342 |                 0.99997 |
| ridge                                     |     0.12468  |          0.088093 |          0.92854 |       0.088537 |           0.9987  |               0.93133 |                0.57402 |                 0.87281 |
| traditional_dE_E_tail_pedestal_likelihood |     0.13393  |          0.093308 |          0.92138 |       0.12099  |           0.9987  |               0.92467 |                0.5655  |                 0.87911 |
| mlp                                       |     0.17822  |          0.12455  |          0.84408 |       0.11904  |           0.96828 |               0.77102 |                0.53067 |                 0.91427 |
| 1d_cnn                                    |     0.23337  |          0.24614  |          0.7993  |       0.17124  |           0.97068 |               0.68417 |                0.504   |                 0.78322 |
| spectral_transformer_new                  |     0.2501   |          0.23808  |          0.83202 |       0.2974   |           0.99237 |               0.53621 |                0.51333 |                 0.82728 |

## Endpoint Bootstrap CIs

| split_name       | endpoint              | method                                    |   metric_value |   ci_low |   ci_high |    n |   positives |
|:-----------------|:----------------------|:------------------------------------------|---------------:|---------:|----------:|-----:|------------:|
| run_heldout      | pid_separation        | gradient_boosted_trees                    |       0.99938  | 0.9992   |   0.99956 | 4106 |        2375 |
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |       0.99259  | 0.99063  |   0.99453 | 4106 |        2375 |
| run_heldout      | pid_separation        | ridge                                     |       0.9921   | 0.98981  |   0.99473 | 4106 |        2375 |
| run_heldout      | pid_separation        | mlp                                       |       0.98168  | 0.97803  |   0.98494 | 4106 |        2375 |
| run_heldout      | pid_separation        | spectral_transformer_new                  |       0.75687  | 0.73743  |   0.77452 | 4106 |        2375 |
| run_heldout      | pid_separation        | 1d_cnn                                    |       0.72469  | 0.69444  |   0.75231 | 4106 |        2375 |
| run_heldout      | energy_scale          | gradient_boosted_trees                    |       0.10466  | 0.066082 |   0.18591 | 4106 |             |
| run_heldout      | energy_scale          | mlp                                       |       0.12145  | 0.084932 |   0.19047 | 4106 |             |
| run_heldout      | energy_scale          | ridge                                     |       0.12719  | 0.082779 |   0.22068 | 4106 |             |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |       0.13249  | 0.11516  |   0.14082 | 4106 |             |
| run_heldout      | energy_scale          | spectral_transformer_new                  |       0.34961  | 0.31758  |   0.38036 | 4106 |             |
| run_heldout      | energy_scale          | 1d_cnn                                    |       0.35692  | 0.33189  |   0.38937 | 4106 |             |
| run_heldout      | pileup_sideband       | gradient_boosted_trees                    |       0.99992  | 0.99985  |   0.99997 | 4106 |         675 |
| run_heldout      | pileup_sideband       | ridge                                     |       0.99875  | 0.99697  |   0.99967 | 4106 |         675 |
| run_heldout      | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |       0.9987   | 0.99714  |   0.99963 | 4106 |         675 |
| run_heldout      | pileup_sideband       | mlp                                       |       0.97974  | 0.97446  |   0.98553 | 4106 |         675 |
| run_heldout      | pileup_sideband       | spectral_transformer_new                  |       0.96865  | 0.96334  |   0.97353 | 4106 |         675 |
| run_heldout      | pileup_sideband       | 1d_cnn                                    |       0.94782  | 0.94042  |   0.95618 | 4106 |         675 |
| run_heldout      | saturation_clipping   | gradient_boosted_trees                    |       0.99744  | 0.99374  |   0.99892 | 4106 |         267 |
| run_heldout      | saturation_clipping   | ridge                                     |       0.90883  | 0.85145  |   0.93992 | 4106 |         267 |
| run_heldout      | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |       0.90519  | 0.85362  |   0.93582 | 4106 |         267 |
| run_heldout      | saturation_clipping   | mlp                                       |       0.81905  | 0.70988  |   0.87117 | 4106 |         267 |
| run_heldout      | saturation_clipping   | 1d_cnn                                    |       0.78473  | 0.6402   |   0.84558 | 4106 |         267 |
| run_heldout      | saturation_clipping   | spectral_transformer_new                  |       0.77063  | 0.64091  |   0.82982 | 4106 |         267 |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees                    |       0.93845  | 0.91739  |   0.95832 | 4106 |         861 |
| run_heldout      | pedestal_noise_color  | ridge                                     |       0.89172  | 0.85234  |   0.92161 | 4106 |         861 |
| run_heldout      | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |       0.89165  | 0.85855  |   0.92644 | 4106 |         861 |
| run_heldout      | pedestal_noise_color  | mlp                                       |       0.85859  | 0.82366  |   0.89487 | 4106 |         861 |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new                  |       0.74412  | 0.70885  |   0.77499 | 4106 |         861 |
| run_heldout      | pedestal_noise_color  | 1d_cnn                                    |       0.67903  | 0.65702  |   0.69903 | 4106 |         861 |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees                    |       0.99999  | 0.99998  |   1       | 4106 |         800 |
| run_heldout      | pulse_shape_harmonics | ridge                                     |       0.9891   | 0.98652  |   0.99136 | 4106 |         800 |
| run_heldout      | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |       0.98899  | 0.98608  |   0.99164 | 4106 |         800 |
| run_heldout      | pulse_shape_harmonics | mlp                                       |       0.97952  | 0.97266  |   0.98495 | 4106 |         800 |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new                  |       0.86741  | 0.83039  |   0.8928  | 4106 |         800 |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                                    |       0.79007  | 0.74707  |   0.81775 | 4106 |         800 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    |       0.9796   | 0.97605  |   0.98332 | 1813 |         574 |
| particle_heldout | pid_separation        | ridge                                     |       0.92854  | 0.91814  |   0.93769 | 1813 |         574 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |       0.92138  | 0.90915  |   0.93517 | 1813 |         574 |
| particle_heldout | pid_separation        | mlp                                       |       0.84408  | 0.82351  |   0.86218 | 1813 |         574 |
| particle_heldout | pid_separation        | spectral_transformer_new                  |       0.83202  | 0.80807  |   0.855   | 1813 |         574 |
| particle_heldout | pid_separation        | 1d_cnn                                    |       0.7993   | 0.77617  |   0.82001 | 1813 |         574 |
| particle_heldout | energy_scale          | ridge                                     |       0.088537 | 0.072858 |   0.11308 | 1813 |             |
| particle_heldout | energy_scale          | gradient_boosted_trees                    |       0.09896  | 0.08367  |   0.11528 | 1813 |             |
| particle_heldout | energy_scale          | mlp                                       |       0.11904  | 0.10652  |   0.13166 | 1813 |             |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |       0.12099  | 0.10829  |   0.12941 | 1813 |             |
| particle_heldout | energy_scale          | 1d_cnn                                    |       0.17124  | 0.16105  |   0.1843  | 1813 |             |
| particle_heldout | energy_scale          | spectral_transformer_new                  |       0.2974   | 0.28108  |   0.31215 | 1813 |             |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    |       0.99933  | 0.99885  |   0.99966 | 1813 |         765 |
| particle_heldout | pileup_sideband       | ridge                                     |       0.9987   | 0.99812  |   0.99915 | 1813 |         765 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |       0.9987   | 0.99821  |   0.99915 | 1813 |         765 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  |       0.99237  | 0.98937  |   0.99495 | 1813 |         765 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    |       0.97068  | 0.96021  |   0.98039 | 1813 |         765 |
| particle_heldout | pileup_sideband       | mlp                                       |       0.96828  | 0.95933  |   0.97632 | 1813 |         765 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    |       0.99999  | 0.99994  |   1       | 1813 |          55 |
| particle_heldout | saturation_clipping   | ridge                                     |       0.93133  | 0.88705  |   0.97164 | 1813 |          55 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |       0.92467  | 0.86172  |   0.96821 | 1813 |          55 |
| particle_heldout | saturation_clipping   | mlp                                       |       0.77102  | 0.70248  |   0.8329  | 1813 |          55 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    |       0.68417  | 0.62161  |   0.75422 | 1813 |          55 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  |       0.53621  | 0.47338  |   0.61297 | 1813 |          55 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    |       0.77342  | 0.7133   |   0.82417 | 1813 |         114 |
| particle_heldout | pedestal_noise_color  | ridge                                     |       0.57402  | 0.50223  |   0.64412 | 1813 |         114 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |       0.5655   | 0.49978  |   0.63863 | 1813 |         114 |
| particle_heldout | pedestal_noise_color  | mlp                                       |       0.53067  | 0.50443  |   0.55644 | 1813 |         114 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  |       0.51333  | 0.45319  |   0.57153 | 1813 |         114 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    |       0.504    | 0.43374  |   0.56399 | 1813 |         114 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    |       0.99997  | 0.99993  |   1       | 1813 |        1115 |
| particle_heldout | pulse_shape_harmonics | mlp                                       |       0.91427  | 0.89976  |   0.92867 | 1813 |        1115 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |       0.87911  | 0.86043  |   0.89568 | 1813 |        1115 |
| particle_heldout | pulse_shape_harmonics | ridge                                     |       0.87281  | 0.85178  |   0.88857 | 1813 |        1115 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  |       0.82728  | 0.80413  |   0.84654 | 1813 |        1115 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    |       0.78322  | 0.75838  |   0.80991 | 1813 |        1115 |

## PID Calibration and Energy Residuals

| split_name       | method                                    |     auc |       ece |    n |   positives |
|:-----------------|:------------------------------------------|--------:|----------:|-----:|------------:|
| particle_heldout | 1d_cnn                                    | 0.7993  | 0.24144   | 1813 |         574 |
| particle_heldout | gradient_boosted_trees                    | 0.9796  | 0.14314   | 1813 |         574 |
| particle_heldout | mlp                                       | 0.84408 | 0.29976   | 1813 |         574 |
| particle_heldout | ridge                                     | 0.92854 | 0.20674   | 1813 |         574 |
| particle_heldout | spectral_transformer_new                  | 0.83202 | 0.16826   | 1813 |         574 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | 0.92138 | 0.20599   | 1813 |         574 |
| run_heldout      | 1d_cnn                                    | 0.72469 | 0.17292   | 4106 |        2375 |
| run_heldout      | gradient_boosted_trees                    | 0.99938 | 0.0063961 | 4106 |        2375 |
| run_heldout      | mlp                                       | 0.98168 | 0.34855   | 4106 |        2375 |
| run_heldout      | ridge                                     | 0.9921  | 0.26565   | 4106 |        2375 |
| run_heldout      | spectral_transformer_new                  | 0.75687 | 0.13926   | 4106 |        2375 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | 0.99259 | 0.2695    | 4106 |        2375 |

Energy residual rows are the `energy_scale` endpoint in the CI table; they are log-amplitude residuals after run/stave centering, not an externally calibrated MeV scale.

## Paired Bootstrap Deltas vs Traditional

| split_name       | endpoint              | method                   |   delta_vs_traditional |      ci_low |     ci_high | delta_definition                                             |
|:-----------------|:----------------------|:-------------------------|-----------------------:|------------:|------------:|:-------------------------------------------------------------|
| particle_heldout | energy_scale          | 1d_cnn                   |             0.05316    |  0.043754   |  0.062896   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | gradient_boosted_trees   |            -0.021229   | -0.032923   | -0.0083521  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | mlp                      |            -0.00033368 | -0.012021   |  0.013147   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | ridge                    |            -0.029636   | -0.040953   | -0.014477   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | spectral_transformer_new |             0.1772     |  0.16025    |  0.19229    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | 1d_cnn                   |            -0.062154   | -0.19254    |  0.053295   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees   |             0.20941    |  0.11949    |  0.31093    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | mlp                      |            -0.034168   | -0.10156    |  0.045248   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | ridge                    |             0.0089435  | -0.02014    |  0.041372   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new |            -0.04879    | -0.15587    |  0.051348   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | 1d_cnn                   |            -0.12196    | -0.14853    | -0.097611   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | gradient_boosted_trees   |             0.058496   |  0.045123   |  0.073482   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | mlp                      |            -0.077297   | -0.10731    | -0.053012   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | ridge                    |             0.0071182  |  0.0032569  |  0.012183   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | spectral_transformer_new |            -0.089024   | -0.11452    | -0.06498    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | 1d_cnn                   |            -0.028036   | -0.040481   | -0.017803   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | gradient_boosted_trees   |             0.00062827 |  0.00013131 |  0.0011303  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | mlp                      |            -0.030794   | -0.039446   | -0.023616   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | ridge                    |             3.639e-06  | -3.1894e-05 |  3.5389e-05 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | spectral_transformer_new |            -0.006349   | -0.008949   | -0.0041371  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                   |            -0.095056   | -0.11946    | -0.07456    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees   |             0.12073    |  0.10468    |  0.13832    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | mlp                      |             0.03611    |  0.016505   |  0.057826   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | ridge                    |            -0.0062615  | -0.0077912  | -0.0045708  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new |            -0.051589   | -0.067748   | -0.036644   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | 1d_cnn                   |            -0.23785    | -0.30243    | -0.16365    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | gradient_boosted_trees   |             0.076189   |  0.030251   |  0.13283    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | mlp                      |            -0.1525     | -0.21624    | -0.084079   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | ridge                    |             0.0067879  | -0.00065279 |  0.016643   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | spectral_transformer_new |            -0.38754    | -0.46164    | -0.30677    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | 1d_cnn                   |             0.22626    |  0.1967     |  0.26581    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | gradient_boosted_trees   |            -0.017387   | -0.067899   |  0.055212   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | mlp                      |            -0.0018171  | -0.048279   |  0.070026   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | ridge                    |             0.0073796  | -0.044261   |  0.085599   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | spectral_transformer_new |             0.21817    |  0.17734    |  0.2608     | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | 1d_cnn                   |            -0.21245    | -0.2316     | -0.19009    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees   |             0.047859   |  0.03345    |  0.062826   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | mlp                      |            -0.032522   | -0.041211   | -0.023862   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | ridge                    |             0.00032268 | -0.0038027  |  0.0048544  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new |            -0.14686    | -0.16966    | -0.12924    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | 1d_cnn                   |            -0.26821    | -0.29811    | -0.24056    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | gradient_boosted_trees   |             0.006897   |  0.0049797  |  0.0087679  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | mlp                      |            -0.010931   | -0.014681   | -0.0070959  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | ridge                    |            -0.00046657 | -0.0013651  |  0.00044649 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | spectral_transformer_new |            -0.23664    | -0.25422    | -0.21837    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | 1d_cnn                   |            -0.050839   | -0.059231   | -0.042308   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | gradient_boosted_trees   |             0.0012387  |  0.00028529 |  0.0031345  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | mlp                      |            -0.019016   | -0.02468    | -0.013147   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | ridge                    |             6.1178e-05 |  2.4919e-06 |  0.00014545 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | spectral_transformer_new |            -0.02989    | -0.034368   | -0.025393   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                   |            -0.19735    | -0.23859    | -0.16822    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees   |             0.011001   |  0.0084217  |  0.013249   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | mlp                      |            -0.0097244  | -0.015905   | -0.0049137  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | ridge                    |             9.8292e-05 | -0.00021662 |  0.00046011 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new |            -0.12291    | -0.15732    | -0.093827   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | 1d_cnn                   |            -0.12606    | -0.19548    | -0.086338   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | gradient_boosted_trees   |             0.097683   |  0.061434   |  0.14917    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | mlp                      |            -0.089748   | -0.14863    | -0.048262   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | ridge                    |             0.0036149  |  0.00076438 |  0.0071771  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | spectral_transformer_new |            -0.14022    | -0.20743    | -0.10562    | AUC gain for classification; sigma68 increase for regression |

## Stratified Systematics

The full `strata_metrics.csv` file stratifies each endpoint by late-tail amplitude, pedestal history, pulse-shape harmonic content, timing residual, pile-up flag, saturation flag, and energy bin. The excerpt below shows the winner on the two most relevant PID/energy axes.

| split_name       | endpoint       | stratum_axis         | stratum          |    n | metric   |    value |
|:-----------------|:---------------|:---------------------|:-----------------|-----:|:---------|---------:|
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_high        | 1748 | sigma68  | 0.098352 |
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_mid         |   65 | sigma68  | 0.12866  |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_memory  |  512 | sigma68  | 0.082864 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_mid     |  722 | sigma68  | 0.085857 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_quiet   |  579 | sigma68  | 0.15214  |
| particle_heldout | energy_scale   | pulse_shape_bin      | low_harmonic     |  810 | sigma68  | 0.09752  |
| particle_heldout | energy_scale   | pulse_shape_bin      | mid_harmonic     |  992 | sigma68  | 0.089693 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_core      |  586 | sigma68  | 0.10561  |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_mid       |  507 | sigma68  | 0.090623 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_tail      |  720 | sigma68  | 0.078596 |
| particle_heldout | energy_scale   | pileup_flag          | pileup_proxy     |  765 | sigma68  | 0.079879 |
| particle_heldout | energy_scale   | pileup_flag          | single_proxy     | 1048 | sigma68  | 0.095957 |
| particle_heldout | energy_scale   | saturation_flag      | linear_proxy     | 1758 | sigma68  | 0.096233 |
| particle_heldout | energy_scale   | saturation_flag      | saturation_proxy |   55 | sigma68  | 0.22602  |
| particle_heldout | energy_scale   | energy_bin           | energy_high      | 1695 | sigma68  | 0.091651 |
| particle_heldout | energy_scale   | energy_bin           | energy_mid       |  102 | sigma68  | 0.11466  |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_high        | 1748 | auc      | 0.97928  |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_mid         |   65 | auc      | 0.99704  |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_memory  |  512 | auc      | 0.97714  |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_mid     |  722 | auc      | 0.98565  |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_quiet   |  579 | auc      | 0.97611  |
| particle_heldout | pid_separation | pulse_shape_bin      | low_harmonic     |  810 | auc      | 0.97305  |
| particle_heldout | pid_separation | pulse_shape_bin      | mid_harmonic     |  992 | auc      | 0.96267  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_core      |  586 | auc      | 0.97358  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_mid       |  507 | auc      | 0.94086  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_tail      |  720 | auc      | 0.98971  |
| particle_heldout | pid_separation | pileup_flag          | pileup_proxy     |  765 | auc      | 0.98607  |
| particle_heldout | pid_separation | pileup_flag          | single_proxy     | 1048 | auc      | 0.9699   |
| particle_heldout | pid_separation | saturation_flag      | linear_proxy     | 1758 | auc      | 0.98349  |
| particle_heldout | pid_separation | saturation_flag      | saturation_proxy |   55 | auc      | 0.87981  |

## Leakage, Feature, and Attention Audits

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |   pid_ece |   cross_task_leakage_index | interpretation                                                                          |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|----------:|---------------------------:|:----------------------------------------------------------------------------------------|
| particle_heldout | 1d_cnn                                    |   0.7993  |         0.17124  |         0.78322 |        0.504   | 0.24144   |                   0.2953   | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | gradient_boosted_trees                    |   0.9796  |         0.09896  |         0.99997 |        0.77342 | 0.14314   |                   0.22722  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | mlp                                       |   0.84408 |         0.11904  |         0.91427 |        0.53067 | 0.29976   |                   0.31436  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | ridge                                     |   0.92854 |         0.088537 |         0.87281 |        0.57402 | 0.20674   |                   0.38598  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | spectral_transformer_new                  |   0.83202 |         0.2974   |         0.82728 |        0.51333 | 0.16826   |                   0.31869  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.92138 |         0.12099  |         0.87911 |        0.5655  | 0.20599   |                   0.35588  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | 1d_cnn                                    |   0.72469 |         0.35692  |         0.79007 |        0.67903 | 0.17292   |                   0.045655 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | gradient_boosted_trees                    |   0.99938 |         0.10466  |         0.99999 |        0.93845 | 0.0063961 |                   0.076262 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | mlp                                       |   0.98168 |         0.12145  |         0.97952 |        0.85859 | 0.34855   |                   0.12309  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | ridge                                     |   0.9921  |         0.12719  |         0.9891  |        0.89172 | 0.26565   |                   0.10038  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | spectral_transformer_new                  |   0.75687 |         0.34961  |         0.86741 |        0.74412 | 0.13926   |                   0.012743 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.99259 |         0.13249  |         0.98899 |        0.89165 | 0.2695    |                   0.10094  | proxy-label coupling audit; high values require external truth before physics promotion |

Feature-family audit:

| feature                   | family                         |
|:--------------------------|:-------------------------------|
| tail_10_17_over_total     | charge_comparison_psd          |
| tail_12_17_over_total     | charge_comparison_psd          |
| tail_14_17_over_total     | charge_comparison_psd          |
| early_0_4_over_total      | charge_comparison_psd          |
| middle_5_9_over_total     | charge_comparison_psd          |
| late_minus_early_asym     | charge_comparison_psd          |
| rise_10_50                | rise_time_width                |
| rise_20_80                | rise_time_width                |
| width20                   | rise_time_width                |
| width50                   | rise_time_width                |
| max_rise_step             | zero_crossing_derivative       |
| max_fall_step             | zero_crossing_derivative       |
| zero_crossings_derivative | zero_crossing_derivative       |
| mean_time                 | mean_time_moments              |
| time_variance             | mean_time_moments              |
| time_skewness             | mean_time_moments              |
| time_kurtosis             | mean_time_moments              |
| fft_k1_fraction           | frequency_domain_fft           |
| fft_k2_fraction           | frequency_domain_fft           |
| fft_high_over_low         | frequency_domain_fft           |
| cfd20_time                | constant_fraction_shape_ratios |
| cfd50_time                | constant_fraction_shape_ratios |
| le_ratio_s4_s7            | constant_fraction_shape_ratios |
| le_ratio_s5_s7            | constant_fraction_shape_ratios |
| cf_ratio_s6_s8            | constant_fraction_shape_ratios |
| haar_l0_d00               | wavelet_haar                   |
| haar_l0_d01               | wavelet_haar                   |
| haar_l0_d02               | wavelet_haar                   |
| haar_l0_d03               | wavelet_haar                   |
| haar_l0_d04               | wavelet_haar                   |
| haar_l0_d05               | wavelet_haar                   |
| haar_l0_d06               | wavelet_haar                   |
| haar_l0_d07               | wavelet_haar                   |
| haar_l1_d00               | wavelet_haar                   |
| haar_l1_d01               | wavelet_haar                   |
| haar_l1_d02               | wavelet_haar                   |
| haar_l1_d03               | wavelet_haar                   |
| haar_l2_d00               | wavelet_haar                   |
| haar_l2_d01               | wavelet_haar                   |
| haar_l3_d00               | wavelet_haar                   |

The spectral-transformer row is the attention-style sensitivity audit: its gains or losses are compared with the feature-engineered traditional baseline and the 1D-CNN under identical splits. This script does not export per-head attention maps; with 18 samples and proxy labels, endpoint-stable performance is treated as stronger evidence than visual attention weights.

## Caveats

- PID, pile-up, saturation, and pedestal labels are deterministic raw-waveform proxies, not external truth labels.
- The particle-held-out split uses proxy particle families because species truth is absent from the reduced HRD ROOT branch.
- Run-block bootstrap covers observed run-to-run variation but cannot cover beam settings not present in runs 31-65.
- High AUC values can reflect proximity between feature definitions and proxy labels; the leakage table is therefore part of the result, not a cosmetic diagnostic.
- The winner is valid for this registered proxy benchmark; physics promotion requires external PID/energy truth or digitized GEANT4 closure.

## Verdict

`result.json` names **gradient_boosted_trees** as the winner because it minimizes mean registered joint loss across the run-held-out and proxy particle-held-out splits. The scientifically useful conclusion is that tail and pedestal memory terms are necessary diagnostics: they improve uncertainty accounting, but they also expose where proxy labels can leak cross-task information.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s32c_1783884181_2159_4b0d44ea_pid_energy_uncertainty_tail_pedestal_memory.py --config configs/s32c_1783884181_2159_4b0d44ea_pid_energy_uncertainty_tail_pedestal_memory.json
```
