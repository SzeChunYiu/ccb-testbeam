# S07f: independent all-three App.I RF validation

- **Ticket:** `1781012109.1290.18206042`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Selection:** Sample-II analysis runs, B2+B4+B6+B8 all selected, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.

## Raw-ROOT Reproduction First

| quantity                                | report_value | reproduced | delta      | tolerance | pass |
| --------------------------------------- | ------------ | ---------- | ---------- | --------- | ---- |
| parent App.I guarded gross D_t>51 ns    | 72           | 72         | 0          | 0         | True |
| parent App.I documented gross D_t>50 ns |              | 74         |            |           | True |
| all-three control events                | 3774         | 3774       | 0          | 0         | True |
| all-three clean events D_t<3 ns         |              | 579        |            |           | True |
| all-three guarded gross D_t>51 ns       | 22           | 22         | 0          | 0         | True |
| all-three S07e shape RF ROC AUC         | 0.992778     | 0.994426   | 0.00164861 | 0.002     | True |

The all-three App.I raw count gate reproduces the S07e control population (`3774`) and guarded gross tail (`22`) exactly. The D_t-label benchmark then reproduces the S07e shape RF AUC as 0.994426, within the configured tolerance of the prior 0.992778.

| method                                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier       | brier_ci_low | brier_ci_high | notes                                                                                                                       |
| ------------------------------------------ | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ----------- | ------------ | ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| reproduced all-three curvature-only        | 1        | 1              | 1               | 1                 | 1         | 1          | 2.69041e-07 | 0            | 8.62127e-07   | S07e pre-registered all-three traditional comparator.                                                                       |
| reproduced all-three D_t/curvature ceiling | 1        | 1              | 1               | 1                 | 1         | 1          | 1.88359e-06 | 0            | 4.46498e-06   | Forbidden self-referential timing ceiling.                                                                                  |
| reproduced all-three shape-only RF         | 0.994426 | 0.981701       | 0.999521        | 0.913019          | 0.655174  | 0.984266   | 0.0123271   | 0.00503737   | 0.0211324     | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; raw-ROOT reproduction of S07e all-three App.I RF. |

## Independent Target

The validation target is not `D_t`: each raw clean all-three event (`D_t<3 ns`) is paired with one injected copy where a selected downstream waveform receives a delayed scaled copy of itself. Delays are 2-6 samples and scales are 0.12-0.38. Raw and injected pair members are held out together by run.

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 9         | 9        | 18    |
| 59  | 93        | 93       | 186   |
| 60  | 129       | 129      | 258   |
| 61  | 176       | 176      | 352   |
| 62  | 111       | 111      | 222   |
| 63  | 57        | 57       | 114   |
| 65  | 4         | 4        | 8     |

## Head-to-Head

| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                       |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| traditional fold-selected timing/template | 0.605954 | 0.598605       | 0.618069        | 0.570681          | 0.561867  | 0.583083   | 0.239508 | 0.237077     | 0.241699      | Fold-local best signed timing, curvature, shape-summary, or matched-template score.                                                                         |
| direct D_t/curvature cross-check          | 0.530522 | 0.51749        | 0.537119        | 0.581449          | 0.566058  | 0.597987   | 0.24422  | 0.240807     | 0.247804      | Not label-defining here; target is injected two-pulse truth.                                                                                                |
| all-three shape-only RF                   | 0.822118 | 0.80083        | 0.844361        | 0.83589           | 0.81471   | 0.860373   | 0.177242 | 0.164769     | 0.190468      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, run/event ids, injection params, amplitudes, and topology flags. |

The strong traditional score is selected inside each training fold from timing, curvature, downstream shape summaries, and a train-only matched-template residual. The ML method is a shape-only RF using B2 and downstream aggregate normalized waveform features; timing values, run/event IDs, pair IDs, injection parameters, amplitudes, and topology flags are excluded.

## Leakage Hunt

| probe                                  | roc_auc  | average_precision | notes                                                 |
| -------------------------------------- | -------- | ----------------- | ----------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same for clean/injected pairs; should be chance.      |
| topology-only RF                       | 0.5      | 0.5               | Constant all-three topology; should be chance.        |
| absolute-amplitude-only RF             | 0.560319 | 0.567646          | Excluded from main RF; injection changes peak height. |
| shape RF with shuffled training labels | 0.479804 | 0.482593          | Null/leakage sanity check.                            |
| per-stave slot shape RF                | 0.853256 | 0.858264          | Permissive shape representation; not main claim.      |
| pair split violations                  | 0        |                   | Must be 0.                                            |
| forbidden main RF columns              | 0        |                   | None.                                                 |

The result is good but not suspiciously perfect: shuffled labels are near chance, pair split violations are zero, and no forbidden columns enter the main RF. The direct post-injection `D_t` cross-check is near chance, confirming that the injected label is not a disguised `D_t` tail threshold. The amplitude-only probe is strong because the injection changes peak height, so it is kept out of the main RF and reported as a nuisance.

## Finding

The all-three App.I RF survives an independent non-`D_t` validation. On injected two-pulse truth, the traditional timing/template score reaches ROC AUC 0.606 [0.599, 0.618], while the all-three shape-only RF reaches 0.822 [0.801, 0.844]. This validates the all-three RF as a waveform-corruption detector, not as direct evidence for a measured beam pile-up rate.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07f_independent_all_three_appi_validation.py --config configs/s07f_1781012109_1290_18206042.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07e_reproduction_scoreboard.csv`, `injection_scoreboard.csv`, `leakage_checks.csv`, and out-of-fold prediction CSVs.
