# P01c: lightweight P01b artifact loader checks

**Ticket:** `1781016530.1346.4e7f7ee0`

## Reproduction first
Raw B-stack ROOT was scanned from `data/root/root` before any artifact loading. The P01b/S00 selection reproduced **640,737** selected B-stave pulses versus expected **640,737**.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

## Loader contract
Configured NPZ path: `artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0/p01b_embedding_latents.npz`.
The ignored NPZ was absent in this checkout, so binary artifact checks were marked not-run rather than faked.

| check | value | pass |
|---|---:|---|
| artifact present | false | True |
| regenerate command recorded | `/home/billy/anaconda3/bin/python scripts/p01b_full_data_embedding_artifact.py --config configs/p01b_full_data_embedding_artifact.json` | True |
| upstream raw input manifest matches current raw files | True | True |

`loader_contract_checks.csv` and `input_sha256.csv` are the lightweight downstream smoke-test outputs.

## Held-out consumer benchmark
The benchmark target is `stave_index`, using held-out runs `42, 57, 64, 65` only for evaluation. CIs are 95% run-block bootstrap intervals over held-out runs. Release embeddings are excluded from these benchmark feature matrices, so downstream reports cannot silently benchmark on the all-data P01b release latents.

| method | metric | value | 95% CI |
|---|---:|---:|---:|
| traditional hand-shape logistic | balanced_accuracy | 0.4113 | [0.3875, 0.4269] |
| traditional hand-shape logistic | macro_f1 | 0.3493 | [0.3120, 0.3782] |
| ML raw-waveform random forest | balanced_accuracy | 0.6259 | [0.5957, 0.6401] |
| ML raw-waveform random forest | macro_f1 | 0.6240 | [0.5991, 0.6394] |

Primary balanced accuracy: traditional hand-shape logistic **0.4113** [0.3875, 0.4269], ML raw-waveform random forest **0.6259** [0.5957, 0.6401].

## Leakage checks
| check | value | pass | note |
|---|---:|---|---|
| train_heldout_run_overlap | 0.0 | True | must be zero for by-run validation |
| forbidden_feature_audit | 0.0 | True | benchmark features exclude run, event_index, stave_index, artifact row ids, raw row ids, and z latents |
| release_embedding_benchmark_guard | 1.0 | True | all-data release embeddings are loader-validated only, not used as benchmark features |
| artifact_absent_regenerate_path | 1.0 | True | absent ignored NPZ has exact regenerate command |
| amplitude_only_balanced_accuracy | 0.345163489677185 | True | amplitude is a detector proxy but weaker than waveform ML |
| event_index_only_balanced_accuracy | 0.2613528986854876 | True | event ordinal alone should not carry stave identity across held-out runs |
| shuffled_label_balanced_accuracy | 0.24103618228432505 | True | label-shuffle null should stay near four-class chance |

## Verdict
The loader path is safe to consume as a checked artifact gate. In this checkout the ignored NPZ is absent, so the report records the exact regenerate command and does not pretend to validate the binary. The raw-selected count and upstream raw manifest still reproduce, and the held-out benchmark demonstrates the raw loader/feature alignment without using release embeddings as benchmark features.

No Monte Carlo was used.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p01c_1781016530_1346_4e7f7ee0_loader_checks.py --config configs/p01c_1781016530_1346_4e7f7ee0_loader_checks.json
```
