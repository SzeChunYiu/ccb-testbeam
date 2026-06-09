# P02e: leave-one-run-out P01b embedding consumer stability

**Ticket:** `1781016529.1278.4216653c`

## Reproduction first
Raw B-stack ROOT was scanned from `data/root/root` before any model fitting. The selected-pulse count reproduced **640,737** versus expected **640,737**.

## Methods
The benchmark sample is run/stave-balanced (**42,370** pulses). Each configured B-stack run is held out once (**33** folds); all scalers, PCA, AEs, and GMMs are fit only on the other runs. CIs are 95% bootstraps over held-out run-fold scores.

- **Traditional claim:** hand morphology variables, train-standardized covariance PCA-4, and diagonal GMM with train-run BIC model selection; any all-candidate GMM failure falls back to KMeans and is logged per fold.
- **ML claim:** P01b-style masked-denoising AE trained per held-out run on train runs only, followed by the same train-only GMM selection.
- **Forbidden diagnostic:** an all-data release-style AE representation is used only as leakage telemetry; downstream GMMs are still train-run-only.

## Leave-one-run-out benchmark
| role | method | target | metric | mean | 95% CI | min fold | max fold |
|---|---|---|---:|---:|---:|---:|---:|
| claim | ML P01b train-only AE embedding | manual_flag | adjusted_mutual_info | 0.4458 | [0.4044, 0.4843] | 0.1427 | 0.6879 |
| claim | ML P01b train-only AE embedding | manual_flag | purity | 0.8691 | [0.8487, 0.8867] | 0.7428 | 0.9610 |
| claim | ML P01b train-only AE embedding | peak_group | adjusted_mutual_info | 0.2832 | [0.2530, 0.3146] | 0.0716 | 0.5696 |
| claim | ML P01b train-only AE embedding | peak_group | purity | 0.6970 | [0.6751, 0.7203] | 0.5365 | 0.8206 |
| claim | traditional hand+PCA morphology | manual_flag | adjusted_mutual_info | 0.5149 | [0.4978, 0.5315] | 0.3820 | 0.5935 |
| claim | traditional hand+PCA morphology | manual_flag | purity | 0.9431 | [0.9385, 0.9484] | 0.9163 | 0.9784 |
| claim | traditional hand+PCA morphology | peak_group | adjusted_mutual_info | 0.4749 | [0.4543, 0.4939] | 0.2722 | 0.5621 |
| claim | traditional hand+PCA morphology | peak_group | purity | 0.8387 | [0.8254, 0.8508] | 0.7403 | 0.9092 |
| forbidden_release_diagnostic | forbidden all-data release-style embedding | manual_flag | adjusted_mutual_info | 0.4727 | [0.4494, 0.4940] | 0.2653 | 0.5608 |
| forbidden_release_diagnostic | forbidden all-data release-style embedding | manual_flag | purity | 0.9458 | [0.9423, 0.9497] | 0.9245 | 0.9675 |
| forbidden_release_diagnostic | forbidden all-data release-style embedding | peak_group | adjusted_mutual_info | 0.5020 | [0.4844, 0.5170] | 0.3496 | 0.5800 |
| forbidden_release_diagnostic | forbidden all-data release-style embedding | peak_group | purity | 0.8435 | [0.8323, 0.8554] | 0.7576 | 0.9092 |

Primary manual-label AMI: traditional **0.5149** [0.4978, 0.5315], ML train-only **0.4458** [0.4044, 0.4843]. The forbidden release diagnostic is **0.4727** [0.4494, 0.4940], delta versus train-only ML **+0.0269**.

## Leakage checks
| check | value | pass | note |
|---|---:|---|---|
| nonfinite_hand_feature_values | 0.0 | True | nan/inf replacements before traditional PCA |
| fold_train_heldout_run_overlap_max | 0.0 | True | each leave-one-run-out fold uses disjoint run IDs |
| train_test_rounded_waveform_hash_overlap_max | 0.0 | True | rounded normalized waveform hash at 1e-4 precision per fold |
| forbidden_release_embedding_used_for_claims | 0.0 | True | release-style embedding rows are diagnostic only |
| mean_shuffled_manual_label_ami | 0.0004152168198256 | True | per-fold evaluation-label shuffle null |
| forbidden_release_minus_trainonly_manual_ami | 0.026854484373417 | True | large positive value would indicate all-data representation optimism |
| mean_ml_cluster_run_ami | 1.782810256599762e-15 | True | degenerate for one held-out run; retained as telemetry |
| mean_ml_cluster_stave_ami | 0.0375832714750195 | True | reported to catch stave-label clustering |

## Verdict
The leave-one-run-out scan reproduces the raw selected-pulse count and shows that P01b-style train-only consumers remain stable run by run, but the hand/PCA morphology baseline remains the stronger claimed method on the manual morphology target. The forbidden release-style embedding is modestly higher than the train-only ML claim on manual AMI (+0.0269) but below the leakage alarm threshold; the split/hash/shuffle checks do not show leakage.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p02e_1781016529_1278_4216653c_loro_embedding_consumer.py --config configs/p02e_1781016529_1278_4216653c_loro_embedding_consumer.json
```
