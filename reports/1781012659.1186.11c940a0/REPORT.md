# S07e: all-three-downstream injected timing-corruption benchmark

- **Ticket:** `1781012659.1186.11c940a0`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT `HRDv` from `data/root/root`
- **Selection:** Sample-II runs, B2+B4+B6+B8 all selected, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.

## Question

Rerun the S07d injected two-pulse timing-corruption target after removing missing-downstream-stave topology. The pre-registered conventional comparator is curvature-only, `|C_t| = |t_B8 - 2t_B6 + t_B4|`.

## Raw-ROOT Reproduction First

| quantity                            | report_value | reproduced | delta | tolerance | pass |
| ----------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| parent S07d guarded gross D_t>51 ns | 72           | 72         | 0     | 0         | True |
| parent documented gross D_t>50 ns   |              | 74         |       |           | True |
| all-three control events            | 3774         | 3774       | 0     | 0         | True |
| all-three clean events D_t<3 ns     |              | 579        |       |           | True |
| all-three guarded gross D_t>51 ns   | 22           | 22         | 0     | 0         | True |

The raw scan reproduces the parent S07d App.I gross-tail gate (`72`) and the all-three control population (`3774`) before any injection is made. The old all-three D_t-label RF is also regenerated as a guardrail; the injected target below uses known injection truth, not the D_t tail label.

| method                                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier       | brier_ci_low | brier_ci_high | notes                                                                                                                       |
| ------------------------------------------ | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ----------- | ------------ | ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| reproduced all-three curvature-only        | 1        | 1              | 1               | 1                 | 1         | 1          | 2.69041e-07 | 0            | 8.62127e-07   | S07e pre-registered all-three traditional comparator.                                                                       |
| reproduced all-three D_t/curvature ceiling | 1        | 1              | 1               | 1                 | 1         | 1          | 1.88359e-06 | 0            | 4.46498e-06   | Forbidden self-referential timing ceiling.                                                                                  |
| reproduced all-three shape-only RF         | 0.994426 | 0.981701       | 0.999521        | 0.913019          | 0.655174  | 0.984266   | 0.0123271   | 0.00503737   | 0.0211324     | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; raw-ROOT reproduction of S07e all-three App.I RF. |

## Injected Target

Each raw clean all-three event (`D_t < 3.0 ns`) is paired with one copy where a selected downstream waveform receives a delayed scaled copy of itself. Delays are 2-6 samples and scales are 0.12-0.38. Pair members are held out together because the split is by run.

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 9         | 9        | 18    |
| 59  | 93        | 93       | 186   |
| 60  | 129       | 129      | 258   |
| 61  | 176       | 176      | 352   |
| 62  | 111       | 111      | 222   |
| 63  | 57        | 57       | 114   |
| 65  | 4         | 4        | 8     |

## Methods

- **Traditional, pre-registered:** post-injection curvature-only `|C_t|`.
- **Traditional, strong check:** S07d fold-selected conventional score from timing, curvature, downstream shape summaries, and a train-only matched-template residual.
- **ML:** random forest on amplitude-normalized B2 and downstream aggregate waveform-shape features only. Timing values, run/event IDs, pair IDs, injection parameters, absolute amplitudes, and topology flags are excluded.

| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                                 |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| curvature-only traditional                | 0.498607 | 0.485751       | 0.505766        | 0.561028          | 0.542393  | 0.578168   | 0.244267 | 0.24034      | 0.247978      | Pre-registered |C_t| comparator on all-three downstream injected target.                                                                                              |
| fold-selected traditional timing/template | 0.605954 | 0.59861        | 0.617426        | 0.570681          | 0.561944  | 0.582091   | 0.239508 | 0.237104     | 0.241645      | S07d conventional comparator selected inside each training fold.                                                                                                      |
| direct D_t/curvature cross-check          | 0.530522 | 0.51749        | 0.53761         | 0.581449          | 0.564646  | 0.598474   | 0.24422  | 0.240831     | 0.247644      | Diagnostic only; target is injected two-pulse truth, not a D_t threshold.                                                                                             |
| all-three shape-only RF                   | 0.822118 | 0.798937       | 0.845495        | 0.83589           | 0.815097  | 0.860548   | 0.177242 | 0.164962     | 0.190645      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, run/event ids, pair ids, injection params, amplitudes, and topology flags. |

Traditional fold choices:

| heldout_run | candidate                  | sign | train_auc | train_median | train_iqr | n_train | n_test |
| ----------- | -------------------------- | ---- | --------- | ------------ | --------- | ------- | ------ |
| 58          | max_downstream_peak_sample | 1    | 0.60715   | 6            | 3         | 1140    | 18     |
| 59          | max_downstream_peak_sample | 1    | 0.602     | 6            | 3         | 972     | 186    |
| 60          | max_downstream_peak_sample | 1    | 0.607481  | 6            | 3         | 900     | 258    |
| 61          | max_downstream_peak_sample | 1    | 0.609791  | 6            | 3         | 806     | 352    |
| 62          | max_downstream_peak_sample | 1    | 0.606548  | 6            | 3         | 936     | 222    |
| 63          | max_downstream_peak_sample | 1    | 0.604246  | 6            | 3         | 1044    | 114    |
| 65          | max_downstream_peak_sample | 1    | 0.605872  | 6            | 3         | 1150    | 8      |

## Fixed 95% Clean Acceptance

| method                     | heldout_run | threshold | clean_acceptance | injected_rejection | n_clean_test | n_injected_test |
| -------------------------- | ----------- | --------- | ---------------- | ------------------ | ------------ | --------------- |
| curvature-only traditional | 58          | 4.43967   | 1                | 0.111111           | 9            | 9               |
| curvature-only traditional | 59          | 4.44238   | 0.956989         | 0.129032           | 93           | 93              |
| curvature-only traditional | 60          | 4.44943   | 0.96124          | 0.0930233          | 129          | 129             |
| curvature-only traditional | 61          | 4.43024   | 0.948864         | 0.153409           | 176          | 176             |
| curvature-only traditional | 62          | 4.32559   | 0.900901         | 0.135135           | 111          | 111             |
| curvature-only traditional | 63          | 4.44509   | 0.964912         | 0.122807           | 57           | 57              |
| curvature-only traditional | 65          | 4.43628   | 1                | 0                  | 4            | 4               |
| all-three shape-only RF    | 58          | 0.613838  | 1                | 0.444444           | 9            | 9               |
| all-three shape-only RF    | 59          | 0.612915  | 0.946237         | 0.430108           | 93           | 93              |
| all-three shape-only RF    | 60          | 0.617216  | 0.96124          | 0.465116           | 129          | 129             |
| all-three shape-only RF    | 61          | 0.603822  | 0.926136         | 0.488636           | 176          | 176             |
| all-three shape-only RF    | 62          | 0.617067  | 0.963964         | 0.396396           | 111          | 111             |
| all-three shape-only RF    | 63          | 0.610749  | 0.929825         | 0.350877           | 57           | 57              |
| all-three shape-only RF    | 65          | 0.614452  | 1                | 0.5                | 4            | 4               |

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

The RF result is good but not perfect. Shuffled-label and topology-only probes are near chance, pair split violations are zero, and the main RF feature list has no forbidden timing, ID, amplitude, topology, or injection-parameter columns. The amplitude-only probe is non-trivial because injection can alter peak height; that information is excluded from the main RF. Direct post-injection `D_t`/curvature is near chance, confirming this target is not a disguised timing-tail threshold.

## Finding

On the all-three injected truth target, curvature-only reaches ROC AUC 0.499 [0.486, 0.506], the fold-selected traditional comparator reaches 0.606 [0.599, 0.617], and the shape-only RF reaches 0.822 [0.799, 0.845]. The RF advantage over curvature-only is 0.324 AUC, and over the S07d fold-selected traditional score is 0.216. This supports waveform-shape sensitivity after the all-three topology restriction, but it remains an injected-corruption recovery benchmark rather than a measured beam pile-up rate.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07e_all_three_injected_curvature_benchmark.py --config configs/s07e_1781012659_1186_11c940a0.json
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `injection_scoreboard.csv`, `leakage_checks.csv`, `fixed_efficiency.csv`, and `injection_oof_predictions.csv`.
