# S07h: non-D_t target for P02 morphology

- **Ticket:** 1781015838.1407.0539203d
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT under `data/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65

## Question
Can P02 morphology be benchmarked against an independent timing-corruption label, rather than the downstream `D_t` tail that is derived from the same waveforms?

## Raw Reproduction First
The script first rescans raw ROOT with the P02d recipe: B2/B4/B6/B8, median baseline samples 0-3, `A>1000` ADC, CFD20 downstream times, and leave-one-run-held-out transparent P02 morphology on the original `D_t` extreme label.

| quantity                                   | report_value | reproduced | delta        | tolerance | pass | sample_size |
| ------------------------------------------ | ------------ | ---------- | ------------ | --------- | ---- | ----------- |
| P02 early-peak pulse rate, peak_sample<=3  | 0.044        | 0.0438833  | -0.000116667 | 0.002     | True | 60000       |
| S07 parent guarded gross events, D_t>51 ns | 72           | 72         | 0            | 0         | True | 10156       |
| P02d transparent morphology ROC AUC        | 0.692169     | 0.692169   | 0            | 1e-12     | True | 2227        |

This reproduces the prior transparent P02 morphology AUC before the injected-label study is run.

## Injected Non-D_t Target
The label is known injected truth. Starting from clean events with `D_t<3 ns`, each event is paired with one raw-clean row and one copy where a selected downstream waveform receives a delayed, scaled copy of itself. The label is not a threshold on any post-injection timing value.

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 37        | 37       | 74    |
| 59  | 415       | 415      | 830   |
| 60  | 428       | 428      | 856   |
| 61  | 607       | 607      | 1214  |
| 62  | 420       | 420      | 840   |
| 63  | 194       | 194      | 388   |
| 65  | 54        | 54       | 108   |

## Methods
Splits are leave-one-run-held-out. Intervals are 95% run-block bootstrap CIs over the held-out predictions.

- **Transparent P02 morphology:** train-fold-selected signed cut/score among early-peak flags, early-low-area count, and hand-built P02 morphology scores.
- **Strong traditional reference:** S07d fold-selected one-dimensional timing/template score, including a train-fold matched secondary-pulse residual.
- **ML:** random forest on normalized B2 shape plus downstream aggregate normalized-shape summaries only.

## Head-to-Head
| method                                | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                        |
| ------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ------------------------------------------------------------------------------------------------------------ |
| transparent P02 morphology            | 0.527618 | 0.520063       | 0.536721        | 0.510367          | 0.506405  | 0.515888   | 0.248646 | 0.247917     | 0.249469      | Train-fold-selected transparent P02 morphology cuts/scores only.                                             |
| traditional timing/template reference | 0.612406 | 0.603459       | 0.626072        | 0.577832          | 0.5715    | 0.586977   | 0.240167 | 0.237645     | 0.242416      | Fold-selected one-dimensional timing/template comparator from S07d.                                          |
| shape-only RF P02 morphology          | 0.859788 | 0.837892       | 0.882154        | 0.874114          | 0.851705  | 0.896756   | 0.155966 | 0.141924     | 0.170339      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; 72 normalized morphology features. |

By-run held-out metrics:

| method                                | heldout_run | roc_auc  | average_precision | n_clean | n_injected |
| ------------------------------------- | ----------- | -------- | ----------------- | ------- | ---------- |
| transparent P02 morphology            | 58          | 0.541271 | 0.524187          | 37      | 37         |
| transparent P02 morphology            | 59          | 0.519805 | 0.507737          | 415     | 415        |
| transparent P02 morphology            | 60          | 0.519172 | 0.506746          | 428     | 428        |
| transparent P02 morphology            | 61          | 0.543744 | 0.520416          | 607     | 607        |
| transparent P02 morphology            | 62          | 0.527149 | 0.510649          | 420     | 420        |
| transparent P02 morphology            | 63          | 0.522385 | 0.506692          | 194     | 194        |
| transparent P02 morphology            | 65          | 0.533265 | 0.512806          | 54      | 54         |
| traditional timing/template reference | 58          | 0.65851  | 0.591326          | 37      | 37         |
| traditional timing/template reference | 59          | 0.621884 | 0.587528          | 415     | 415        |
| traditional timing/template reference | 60          | 0.63538  | 0.59423           | 428     | 428        |
| traditional timing/template reference | 61          | 0.606642 | 0.576486          | 607     | 607        |
| traditional timing/template reference | 62          | 0.619459 | 0.588261          | 420     | 420        |
| traditional timing/template reference | 63          | 0.599147 | 0.567095          | 194     | 194        |
| traditional timing/template reference | 65          | 0.581276 | 0.549537          | 54      | 54         |
| shape-only RF P02 morphology          | 58          | 0.871804 | 0.887945          | 37      | 37         |
| shape-only RF P02 morphology          | 59          | 0.866918 | 0.880524          | 415     | 415        |
| shape-only RF P02 morphology          | 60          | 0.8951   | 0.91048           | 428     | 428        |
| shape-only RF P02 morphology          | 61          | 0.840997 | 0.863434          | 607     | 607        |
| shape-only RF P02 morphology          | 62          | 0.88398  | 0.898579          | 420     | 420        |
| shape-only RF P02 morphology          | 63          | 0.844843 | 0.835473          | 194     | 194        |
| shape-only RF P02 morphology          | 65          | 0.775892 | 0.791815          | 54      | 54         |

## Leakage Hunt
| probe                                  | roc_auc  | average_precision | notes                                                                     |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same source event before corruption; should be chance.                    |
| post-injection D_t/curvature           | 0.519963 | 0.560667          | Allowed diagnostic only; label is injected truth, not a timing threshold. |
| topology-only RF                       | 0.501391 | 0.501996          | Present flags and downstream count only; excluded from main RF.           |
| absolute-amplitude-only RF             | 0.588159 | 0.609989          | Injection can change peak height; excluded from main RF.                  |
| B2-only shape RF                       | 0.5      | 0.5               | Upstream waveform is not injected; should be near chance.                 |
| downstream-only aggregate shape RF     | 0.858463 | 0.872113          | Expected to be informative because corruption is injected downstream.     |
| shape RF with shuffled training labels | 0.491364 | 0.502366          | Run-heldout null sanity check.                                            |
| pair split violations                  | 0        |                   | Must be 0.                                                                |
| forbidden main RF columns              | 0        |                   | None.                                                                     |

The RF is high enough to warrant skepticism. The shuffled-label, B2-only, topology-only, and pre-injection `D_t` probes stay near chance, and pair overlap across train/test runs is zero. The amplitude-only probe is non-trivial because injection changes peak height, so amplitudes are excluded from the main RF. Downstream-only shape is expected to be informative because the injected corruption is placed downstream; that is valid for this injected target but should not be read as a measured beam pile-up rate.

## Verdict
Transparent P02 morphology is weak on the independent injected label: ROC AUC 0.528 [0.520, 0.537]. The strong traditional timing/template reference reaches 0.612 [0.603, 0.626], while the shape-only RF reaches 0.860 [0.838, 0.882]. The result supports RF morphology as an injected-corruption detector, but does not rescue early-peak P02 cuts as a standalone timing-tail target.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s07h_1781015838_1407_0539203d_non_dt_p02_morphology.py --config configs/s07h_1781015838_1407_0539203d.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `injected_counts_by_run.csv`, `scoreboard.csv`, `by_run_metrics.csv`, `leakage_checks.csv`, `transparent_p02_fold_choices.csv`, `traditional_reference_fold_choices.csv`, `fixed_efficiency.csv`, and `oof_predictions.csv`.
