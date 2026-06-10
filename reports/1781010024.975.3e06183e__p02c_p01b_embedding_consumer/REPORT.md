# P02c: consume P01b embeddings with run-heldout guardrails

**Ticket:** `1781010024.975.3e06183e`

## Reproduction first
Raw B-stack ROOT was scanned from `data/root/root` before any embedding or downstream model fitting. The P01b/S00 selected-pulse count reproduced **640,737** versus expected **640,737**.

The tracked P01b metadata was found in `reports/1781005204.1292.46e43fb0__p01b_full_data_embedding_artifact`. The binary release `.npz` was `missing`, so this consumer `regenerated` a release-style all-data latent table locally and kept it out of git.

## Methods
Benchmark fitting is split by run: train runs exclude `42, 57, 64, 65` and held-out runs are `42, 57, 64, 65`. The benchmark uses a run/stave-balanced sample of **42,370** pulses and CIs are 95% run-block bootstraps over held-out runs.

- **Traditional:** hand morphology variables plus PCA-4, with diagonal GMM cluster count selected by train-run BIC.
- **ML claim:** P01b-style masked-denoising AE embeddings fit on train runs only, then diagonal GMM selected by train-run BIC.
- **Forbidden diagnostic:** the same downstream GMM procedure using all-data release embeddings. This row is leakage telemetry, not a benchmark claim.

## Held-out benchmark
| method | target | metric | value | 95% CI |
|---|---|---:|---:|---:|
| ML P01b train-only AE embedding | manual_flag | adjusted_mutual_info | 0.4787 | [0.4562, 0.5001] |
| ML P01b train-only AE embedding | manual_flag | purity | 0.9116 | [0.9063, 0.9278] |
| ML P01b train-only AE embedding | peak_group | adjusted_mutual_info | 0.3913 | [0.3706, 0.4142] |
| ML P01b train-only AE embedding | peak_group | purity | 0.8137 | [0.7908, 0.8347] |
| traditional hand+PCA morphology | manual_flag | adjusted_mutual_info | 0.4973 | [0.4644, 0.5189] |
| traditional hand+PCA morphology | manual_flag | purity | 0.9148 | [0.9031, 0.9284] |
| traditional hand+PCA morphology | peak_group | adjusted_mutual_info | 0.4661 | [0.4328, 0.4993] |
| traditional hand+PCA morphology | peak_group | purity | 0.8431 | [0.8257, 0.8586] |

On the primary manual morphology target, traditional AMI is **0.4973** [0.4644, 0.5189] and the train-only P01b embedding AMI is **0.4787** [0.4562, 0.5001].

The forbidden release-embedding diagnostic gives manual AMI **0.4734** [0.4552, 0.5006], delta versus train-only ML **-0.0053**. This is reported only to bound leakage risk from using an all-data representation.

## Leakage checks
| check | value | pass | note |
|---|---:|---|---|
| train_heldout_run_overlap | 0.0 | True | must be zero |
| benchmark_fit_uses_release_embedding | 0.0 | True | release embedding row is diagnostic only |
| train_test_rounded_waveform_hash_overlap | 0.0 | True | rounded normalized waveform hash at 1e-4 precision |
| ml_cluster_run_ami | 0.017655669088126033 | True | reported to catch run-label clustering |
| ml_cluster_stave_ami | 0.03212935366530853 | True | reported to catch stave-label clustering |
| shuffled_manual_label_ami | -0.000594415667442169 | True | evaluation-label shuffle null |
| forbidden_release_minus_trainonly_manual_ami | -0.005309277135171264 | True | large positive value would indicate all-data embedding optimism |

## Verdict
The P01b consumer path works with the release artifact missing: it regenerates an all-data latent table for feature export while keeping benchmark claims on a train-only embedding. The ML train-only embedding is competitive with, but not cleanly superior to, the strong traditional hand/PCA morphology clustering. Because the release diagnostic is tracked separately and the claimed model never fits on all-data embeddings, P02c supports using P01b latents for downstream feature production with run-heldout guardrails.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p02c_p01b_embedding_consumer.py --config configs/p02c_p01b_embedding_consumer.json
```
