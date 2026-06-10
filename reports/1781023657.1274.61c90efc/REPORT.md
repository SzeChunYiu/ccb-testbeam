# S07h: independent high-amplitude all-three App.I target

- **Ticket:** `1781023657.1274.61c90efc`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack `HRDv` ROOT from `data/root/root`
- **Selection:** Sample-II runs, B2+B4+B6+B8 all selected, S07g high `event_max_log_amp` tertile, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.

## Question

Does the S07g high-amplitude all-three shape RF survive when the App.I `D_t` extreme label is replaced by an independent duplicate-readout timing-tail target?

## Raw-ROOT Reproduction First

| quantity                                 | report_value | reproduced | delta | tolerance | pass |
| ---------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| parent guarded gross D_t>51 ns           | 72           | 72         | 0     | 0         | True |
| parent documented gross D_t>50 ns        |              | 74         |       |           | True |
| all-three control events                 | 3774         | 3774       | 0     | 0         | True |
| all-three guarded gross D_t>51 ns        | 22           | 22         | 0     | 0         | True |
| S07g high-amplitude D_t-extreme events   | 169          | 169        | 0     | 0         | True |
| S07g high-amplitude clean events         | 159          | 159        | 0     | 0         | True |
| S07g high-amplitude guarded gross events | 10           | 10         | 0     | 0         | True |
| S07g high-amplitude shape RF ROC AUC     | 1            | 1          | 0     | 0         | True |

The reproduced S07g number is the high-amplitude all-three D_t-extreme stratum: 169 rows, 159 clean, 10 guarded gross, and shape-only RF ROC AUC 1.000. The independent target below starts from the same high-amplitude clean source events but labels injected duplicate-readout truth, not a `D_t` threshold.

| method                            | roc_auc | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier       | notes                                                                                                                          |
| --------------------------------- | ------- | -------------- | --------------- | ----------------- | --------- | ---------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------ |
| S07g high-amplitude shape-only RF | 1       | 1              | 1               | 1                 | 1         | 1          | 0.000271847 | Recomputed from raw ROOT using the S07g all-three OOF RF; params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}. |

High-amplitude source counts before injection:

| run | clean | gross |
| --- | ----- | ----- |
| 58  | 4     | 0     |
| 59  | 20    | 1     |
| 60  | 39    | 3     |
| 61  | 45    | 4     |
| 62  | 27    | 0     |
| 63  | 23    | 2     |
| 65  | 1     | 0     |

## Independent Target

Each high-amplitude clean all-three event (`D_t < 3.0 ns`) is paired with one raw-clean row and one copy where a selected downstream waveform receives a delayed scaled duplicate of itself. Delays are 2-6 samples; scales are 0.12-0.38. Pair members are held out together because the split is by run.

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 4         | 4        | 8     |
| 59  | 20        | 20       | 40    |
| 60  | 39        | 39       | 78    |
| 61  | 45        | 45       | 90    |
| 62  | 27        | 27       | 54    |
| 63  | 23        | 23       | 46    |
| 65  | 1         | 1        | 2     |

## Head-to-Head

| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                            |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ---------------------------------------------------------------------------------------------------------------- |
| curvature-only traditional                | 0.493256 | 0.465431       | 0.522471        | 0.547471          | 0.509895  | 0.593491   | 0.247404 | 0.242474     | 0.251315      | Post-injection \|C_t\| comparator; target is injected truth.                                                     |
| fold-selected traditional timing/template | 0.641153 | 0.607808       | 0.660997        | 0.697505          | 0.661042  | 0.727981   | 0.229769 | 0.217701     | 0.2404        | S07d conventional score selected inside each training fold.                                                      |
| direct D_t/curvature cross-check          | 0.516554 | 0.490583       | 0.542143        | 0.562008          | 0.533557  | 0.600965   | 0.248593 | 0.24396      | 0.252592      | Diagnostic only; not the label definition.                                                                       |
| high-amplitude all-three shape-only RF    | 0.795756 | 0.76037        | 0.840816        | 0.809299          | 0.774636  | 0.856259   | 0.192597 | 0.169924     | 0.209249      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; strict normalized shape features only. |

The strong traditional method is selected inside each training fold from timing, curvature, downstream shape summaries, and a train-fold matched-template residual. The ML method is a random forest over strict normalized B2/downstream aggregate shape features only; timing, run/event IDs, pair IDs, injection parameters, absolute amplitudes, and topology flags are excluded.

By-run held-out metrics:

| method                                    | heldout_run | roc_auc  | average_precision | n_clean | n_injected |
| ----------------------------------------- | ----------- | -------- | ----------------- | ------- | ---------- |
| fold-selected traditional timing/template | 58          | 0.53125  | 0.517857          | 4       | 4          |
| fold-selected traditional timing/template | 59          | 0.61625  | 0.68562           | 20      | 20         |
| fold-selected traditional timing/template | 60          | 0.674885 | 0.679865          | 39      | 39         |
| fold-selected traditional timing/template | 61          | 0.673086 | 0.739767          | 45      | 45         |
| fold-selected traditional timing/template | 62          | 0.65775  | 0.735586          | 27      | 27         |
| fold-selected traditional timing/template | 63          | 0.598299 | 0.662055          | 23      | 23         |
| fold-selected traditional timing/template | 65          | 0.5      | 0.5               | 1       | 1          |
| high-amplitude all-three shape-only RF    | 58          | 0.625    | 0.622024          | 4       | 4          |
| high-amplitude all-three shape-only RF    | 59          | 0.82     | 0.828014          | 20      | 20         |
| high-amplitude all-three shape-only RF    | 60          | 0.77712  | 0.815329          | 39      | 39         |
| high-amplitude all-three shape-only RF    | 61          | 0.779012 | 0.79094           | 45      | 45         |
| high-amplitude all-three shape-only RF    | 62          | 0.894376 | 0.911711          | 27      | 27         |
| high-amplitude all-three shape-only RF    | 63          | 0.771267 | 0.791589          | 23      | 23         |
| high-amplitude all-three shape-only RF    | 65          | 1        | 1                 | 1       | 1          |

Fixed 95% clean-acceptance operating points:

| method                                    | heldout_run | threshold | clean_acceptance | injected_rejection | n_clean_test | n_injected_test |
| ----------------------------------------- | ----------- | --------- | ---------------- | ------------------ | ------------ | --------------- |
| fold-selected traditional timing/template | 58          | 0.771062  | 1                | 0                  | 4            | 4               |
| fold-selected traditional timing/template | 59          | 0.800137  | 1                | 0.2                | 20           | 20              |
| fold-selected traditional timing/template | 60          | 0.799935  | 0.974359         | 0.0769231          | 39           | 39              |
| fold-selected traditional timing/template | 61          | 0.563297  | 0.777778         | 0.488889           | 45           | 45              |
| fold-selected traditional timing/template | 62          | 0.80155   | 1                | 0.37037            | 27           | 27              |
| fold-selected traditional timing/template | 63          | 0.769014  | 0.956522         | 0.217391           | 23           | 23              |
| fold-selected traditional timing/template | 65          | 0.764918  | 1                | 0                  | 1            | 1               |
| high-amplitude all-three shape-only RF    | 58          | 0.639428  | 1                | 0                  | 4            | 4               |
| high-amplitude all-three shape-only RF    | 59          | 0.627931  | 0.9              | 0.4                | 20           | 20              |
| high-amplitude all-three shape-only RF    | 60          | 0.654069  | 1                | 0.25641            | 39           | 39              |
| high-amplitude all-three shape-only RF    | 61          | 0.618028  | 0.822222         | 0.577778           | 45           | 45              |
| high-amplitude all-three shape-only RF    | 62          | 0.651992  | 1                | 0.333333           | 27           | 27              |
| high-amplitude all-three shape-only RF    | 63          | 0.638598  | 0.956522         | 0.391304           | 23           | 23              |
| high-amplitude all-three shape-only RF    | 65          | 0.636938  | 1                | 0                  | 1            | 1               |

## Leakage Hunt

| probe                                  | roc_auc  | average_precision | notes                                                          |
| -------------------------------------- | -------- | ----------------- | -------------------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same source event before injection; should be chance.          |
| topology-only RF                       | 0.5      | 0.5               | All rows are all-three by construction; excluded from main RF. |
| absolute-amplitude-only RF             | 0.553795 | 0.544653          | Injection can change peak height; excluded from main RF.       |
| B2-only shape RF                       | 0.5      | 0.5               | Upstream waveform is not injected; should be near chance.      |
| downstream-only aggregate shape RF     | 0.796824 | 0.798178          | Expected to be informative because injection is downstream.    |
| shape RF with shuffled training labels | 0.548178 | 0.527473          | Run-held-out null sanity check.                                |
| pair split violations                  | 0        |                   | Must be 0.                                                     |
| forbidden main RF columns              | 0        |                   | None.                                                          |

The independent-label RF result is strong but no longer perfect. Shuffled labels, topology-only, B2-only, and pre-injection `D_t` probes stay near chance, pair overlap across run splits is zero, and no forbidden columns enter the main RF. The downstream-only probe is high for the expected reason: the synthetic duplicate-readout corruption is injected downstream.

## Finding

Replacing the App.I `D_t` extremes with injected duplicate-readout truth reduces the high-amplitude all-three RF from the reproduced S07g AUC 1.000 to ROC AUC 0.796 [0.760, 0.841]. The fold-selected traditional comparator reaches 0.641 [0.608, 0.661], while curvature-only is 0.493. The S07g shape signal therefore survives as waveform-corruption sensitivity, but not as a perfect independent timing-tail discriminator.

## Reproducibility

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s07h_1781023657_1274_61c90efc_high_amp_independent_target.py --config configs/s07h_1781023657_1274_61c90efc.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07g_high_amp_scoreboard.csv`, `injected_counts_by_run.csv`, `scoreboard.csv`, `by_run_metrics.csv`, `leakage_checks.csv`, `fixed_efficiency.csv`, and `oof_predictions.csv`.
