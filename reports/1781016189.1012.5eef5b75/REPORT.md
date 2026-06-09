# P01e: downstream loader validation for P01b latents

**Ticket:** `1781016189.1012.5eef5b75`

## Reproduction first
Raw B-stack ROOT was scanned from `data/root/root` before loading the latent artifact. The P01b/S00 selection reproduced **640,737** selected B-stave pulses versus expected **640,737**.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

## Loader contract
The published NPZ was loaded from `artifacts/p01b_full_data_embedding_artifact/1781005204.1292.46e43fb0/p01b_embedding_latents.npz`. It contains `run`, `event_index`, `stave_index`, `amplitude_adc`, and `z`; `z` has shape `[640737, 4]`.

| check | value | pass |
|---|---:|---|
| artifact sha256 matches metadata/config | `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be` | True |
| key sha256 matches metadata/config | `605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193` | True |
| raw key sha256 matches artifact key sha256 | `605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193` | True |
| raw-key join rows | 640,737 | True |
| duplicate artifact keys | 0 | True |
| max raw/artifact amplitude delta ADC | 0 | True |

`row_counts_by_run_stave.csv` is the downstream smoke-test table for P02-P08 workers.

## Held-out consumer benchmark
The benchmark target is `stave_index`, using held-out runs `42, 57, 64, 65` only for evaluation. CIs are 95% run-block bootstrap intervals over held-out runs. The release model is not refit; the ML row consumes frozen `z` columns from the NPZ.

| method | metric | value | 95% CI |
|---|---:|---:|---:|
| traditional hand-shape logistic | balanced_accuracy | 0.4104 | [0.3899, 0.4227] |
| traditional hand-shape logistic | macro_f1 | 0.3410 | [0.3007, 0.3737] |
| ML P01b latent random forest | balanced_accuracy | 0.4790 | [0.4420, 0.4922] |
| ML P01b latent random forest | macro_f1 | 0.4683 | [0.4370, 0.4766] |

Primary balanced accuracy: traditional hand-shape logistic **0.4104** [0.3899, 0.4227], ML P01b latent random forest **0.4790** [0.4420, 0.4922].

## Leakage checks
| check | value | pass | note |
|---|---:|---|---|
| train_heldout_run_overlap | 0.0 | True | must be zero for by-run validation |
| raw_artifact_key_order_equal | 1.0 | True | raw recount key order matches NPZ key order |
| forbidden_feature_audit | 0.0 | True | claim feature matrices exclude run, event_index, stave_index, artifact_row, and raw_row |
| amplitude_only_balanced_accuracy | 0.34492 | True | amplitude can be a detector proxy but is weaker than the claim rows |
| event_index_only_balanced_accuracy | 0.257516 | True | event ordinal alone should not carry stave identity across held-out runs |
| shuffled_label_balanced_accuracy | 0.252356 | True | label-shuffle null should stay near four-class chance |

## Verdict
The published P01b latent NPZ is loader-safe for downstream P02-P08 use: raw selected keys reproduce first, artifact and key hashes verify, every raw selected key joins exactly once, and raw/artifact amplitudes match. The held-out consumer benchmark is a smoke test for usable feature alignment, not a new claim about the release representation because the release model was trained upstream on all selected pulses.

No Monte Carlo was used.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python scripts/p01e_1781016189_1012_5eef5b75_loader_validation.py --config configs/p01e_1781016189_1012_5eef5b75_loader_validation.json
```
