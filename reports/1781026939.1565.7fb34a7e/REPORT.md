# P02d: run-heldout latent-distance artifact keyed by event id

**Ticket:** `1781026939.1565.7fb34a7e`

## Reproduction first
Raw B-stack ROOT was scanned from `data/root/root` before model fitting. The selected-pulse count reproduced **640,737** versus expected **640,737**.

## Published artifact
The artifact `reports/1781026939.1565.7fb34a7e/p02d_run_heldout_latent_distance_artifact.parquet` has **640,737** rows, one per selected pulse, keyed by `run`, `event_index`, ROOT `EVENTNO` as `event_id`, `stave`, and `stave_index`. Each row carries train-run-only PCA and AE latent coordinates, KMeans distance-cluster ids, and nearest-centroid distances computed by a model that excluded that row's run.

## Methods
All **33** configured runs are held out once. Fit samples are run/stave-balanced with at most **300** pulses per train run/stave; encodings and distances are then produced for every pulse in the held-out run. CIs are 95% bootstraps over held-out run-fold scores.

- **Traditional:** hand morphology variables, train-run-only standardization, PCA-4, and KMeans-8 nearest-centroid distances.
- **ML:** P01b-style masked-denoising AE-4 trained only on non-held-out runs, then KMeans-8 nearest-centroid distances.
- **Guard:** a forbidden all-data AE latent benchmark is evaluated only to detect optimism from representation leakage; it is not present in the published artifact.

## Held-out benchmark
| role | method | target | metric | mean | 95% CI | min fold | max fold |
|---|---|---|---:|---:|---:|---:|---:|
| claim | ML train-run-only AE latent distance | manual_flag | adjusted_mutual_info | 0.3028 | [0.2738, 0.3296] | 0.1065 | 0.4419 |
| claim | ML train-run-only AE latent distance | manual_flag | purity | 0.9462 | [0.9393, 0.9542] | 0.9118 | 0.9857 |
| claim | ML train-run-only AE latent distance | peak_group | adjusted_mutual_info | 0.2488 | [0.2269, 0.2739] | 0.1227 | 0.4236 |
| claim | ML train-run-only AE latent distance | peak_group | purity | 0.7956 | [0.7775, 0.8165] | 0.6931 | 0.9634 |
| claim | traditional train-run-only hand/PCA distance | manual_flag | adjusted_mutual_info | 0.4760 | [0.4493, 0.5052] | 0.3135 | 0.7606 |
| claim | traditional train-run-only hand/PCA distance | manual_flag | purity | 0.9760 | [0.9722, 0.9801] | 0.9558 | 0.9942 |
| claim | traditional train-run-only hand/PCA distance | peak_group | adjusted_mutual_info | 0.2502 | [0.2313, 0.2687] | 0.1416 | 0.3519 |
| claim | traditional train-run-only hand/PCA distance | peak_group | purity | 0.7919 | [0.7749, 0.8112] | 0.7020 | 0.9589 |
| forbidden_all_data_guard | forbidden all-data AE latent distance | manual_flag | adjusted_mutual_info | 0.3827 | [0.3638, 0.4005] | 0.1945 | 0.4288 |
| forbidden_all_data_guard | forbidden all-data AE latent distance | manual_flag | purity | 0.9592 | [0.9527, 0.9651] | 0.9372 | 0.9909 |
| forbidden_all_data_guard | forbidden all-data AE latent distance | peak_group | adjusted_mutual_info | 0.2359 | [0.2151, 0.2557] | 0.1228 | 0.3246 |
| forbidden_all_data_guard | forbidden all-data AE latent distance | peak_group | purity | 0.7934 | [0.7744, 0.8128] | 0.6987 | 0.9622 |

Primary manual-label AMI: traditional **0.4760** [0.4493, 0.5052], ML **0.3028** [0.2738, 0.3296]. The forbidden all-data guard gives **0.3827** [0.3638, 0.4005], delta versus ML **+0.0799**.

## Leakage checks
| check | value | pass | note |
|---|---:|---|---|
| artifact_key_duplicate_rows | 0.0 | True | key is run/event_index/event_id/stave_index |
| artifact_missing_distance_or_latent_values | 0.0 | True | every selected pulse should be filled by exactly one heldout fold |
| fold_train_heldout_run_overlap_max | 0.0 | True | each fold excludes the heldout run before fitting PCA/AE/KMeans |
| train_test_rounded_waveform_hash_overlap_max | 0.0 | True | rounded normalized waveform hash at 1e-4 precision per fold |
| forbidden_all_data_minus_trainonly_manual_ami | 0.079884761888182 | False | large positive value would indicate representation leakage optimism |
| shuffled_manual_label_ami_abs_max | 0.006186053566196762 | True | heldout-label shuffle null using ML clusters |
| all_data_latent_used_in_published_artifact | 0.0 | True | forbidden latent appears only in guard metrics, not artifact columns |

## Verdict
P02d publishes the requested keyed latent-distance artifact without using all-data latents for claimed rows. The traditional hand/PCA distance remains the stronger morphology benchmark, while the AE distance provides an independent ML representation for downstream consumers. The leakage hunt found a real all-data optimism warning: the forbidden all-data AE guard is 0.0799 AMI above the train-run-only ML claim, so downstream consumers should use the published train-run-only columns and not regenerate all-data latents for benchmark claims.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p02d_1781026939_1565_7fb34a7e_run_heldout_latent_distance_artifact.py --config configs/p02d_1781026939_1565_7fb34a7e_run_heldout_latent_distance_artifact.json
```
