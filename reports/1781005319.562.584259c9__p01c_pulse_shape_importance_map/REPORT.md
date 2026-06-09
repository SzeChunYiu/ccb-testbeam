# P01c: per-sample pulse-shape importance map

**Ticket:** 1781005319.562.584259c9

## Reproduction first
The raw B-stack ROOT files were read from `data/root/root` before
any modelling. The S00/P01 selection reproduced
**640,737** B-stave pulse records versus
the expected **640,737**.

## Split and controls
The split is by run. Held-out runs are
`42, 57, 64, 65`. Training and
held-out probe samples are balanced by stave and log-amplitude bin; ablations
replace or permute each sample only within those control strata. CIs in the CSV
tables are paired 95% run-bootstrap intervals over held-out runs.

## Methods
Traditional arm: PCA reconstruction, hand-built pulse-shape/topology probes,
odd-channel duplicate-readout amplitude calibration, and S02-style CFD20 timing
residual probes. It also scans contiguous 2-4 sample windows.

ML arm: a P01-style masked denoising autoencoder trained on training runs only,
then calibrated latent probes for topology, odd-channel amplitude, and timing
residuals. Per-sample ML importance uses both control-stratum occlusion and
within-stratum permutation checks.

## Ranked samples
|   sample |   importance_score |   traditional_timing_delta_sigma68_ns |   traditional_amplitude_delta_res68 |   ml_recon_delta_mse |   ml_topology_delta_bacc |
|---------:|-------------------:|--------------------------------------:|------------------------------------:|---------------------:|-------------------------:|
|        5 |           0.435387 |                             -2.02489  |                        -0.0284829   |          0.00470506  |              -0.126548   |
|        4 |           0.375695 |                              8.60495  |                        -0.0244551   |          0.00149726  |              -0.0657251  |
|        6 |           0.369022 |                             -0.929936 |                         0.0212522   |          0.0025597   |              -0.00919522 |
|        3 |           0.329943 |                             11.5127   |                        -0.000939059 |          0.00188068  |              -0.00295691 |
|        9 |           0.25     |                             -0.134139 |                        -0.00243554  |          0.00634492  |               0.00716459 |
|       12 |           0.131177 |                              0.173051 |                         0.0105646   |          1.74399e-05 |              -0.00124333 |

## Contiguous windows
| window   |   importance_score |   traditional_recon_delta_mse |   traditional_timing_delta_sigma68_ns |   ml_recon_delta_mse |
|:---------|-------------------:|------------------------------:|--------------------------------------:|---------------------:|
| 1-4      |           0.718944 |                  -0.000214674 |                              13.2044  |           0.00846108 |
| 0-3      |           0.709114 |                  -0.00205952  |                              11.895   |           0.00999719 |
| 2-4      |           0.67167  |                   0.000852481 |                              13.2044  |           0.00663419 |
| 3-4      |           0.63593  |                   0.000727986 |                              12.6851  |           0.00601286 |
| 3-6      |           0.597155 |                  -0.00156053  |                               3.84893 |           0.0174447  |
| 1-3      |           0.550417 |                   0.000733762 |                              11.9345  |           0.00380665 |
| 2-3      |           0.510238 |                   0.0015958   |                              11.9345  |           0.00225393 |
| 2-5      |           0.502551 |                   0.000533109 |                               4.45545 |           0.0129012  |

## Leakage checks
| check                         |    value | detail                                                                 |
|:------------------------------|---------:|:-----------------------------------------------------------------------|
| run_overlap                   | 0        | must be zero                                                           |
| topology_nuisance_only_bacc   | 0.502586 | uses only log amplitude, amplitude bin, and stave one-hot              |
| topology_label_shuffle_bacc   | 0.459951 | AE latent probe trained after shuffling train topology labels          |
| amplitude_nuisance_only_res68 | 0.10957  | odd-channel amplitude using only even amplitude and stave controls     |
| feature_audit                 | 0        | no run id, event id, event order, or held-out target columns in probes |

## Verdict
The dominant samples are 5, 4, 6, 3,
covering the rising edge and peak/early-fall region. The most stable traditional
timing damage comes from samples 3-4 and windows spanning 1-4. The ML
autoencoder/topology map instead emphasizes samples 5-6 and the early tail. The
ML timing result is better than plain CFD20, so the report treats it as a
calibrated residual-probe result rather than proof of a leak-free production
timing model; the run-overlap, nuisance-only, label-shuffle, and feature-audit
checks above are the leakage hunt for that unusually good number.
