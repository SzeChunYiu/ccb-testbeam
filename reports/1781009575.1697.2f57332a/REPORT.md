# P02d: early-peak topology versus timing tails

- **Ticket:** 1781009575.1697.2f57332a
- **Worker:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT in `data/root/root`
- **Runs:** P02 sample 58, 59, 60, 61, 62, 63, 65, 50; timing benchmark 58, 59, 60, 61, 62, 63, 65

## Question
Does the reproducible P02 early-peak/low-area pulse topology predict downstream S02/S07 timing-tail behavior when `D_t` is used only as the held-out evaluation label and never as a model feature?

## Raw Reproduction First
Selection follows the shared raw ROOT rule: B2/B4/B6/B8 from `HRDv`, baseline median samples 0-3, amplitude `A>1000` ADC, and CFD20 times for downstream timing.

| quantity                                   | report_value | reproduced | delta        | tolerance | pass | sample_size |
| ------------------------------------------ | ------------ | ---------- | ------------ | --------- | ---- | ----------- |
| P02 early-peak pulse rate, peak_sample<=3  | 0.044        | 0.0438833  | -0.000116667 | 0.002     | True | 60000       |
| S07 parent guarded gross events, D_t>51 ns | 72           | 72         | 0            | 0         | True | 10156       |

Run-level timing counts:

| run | raw_events | selected_pulses | parent_control_events | parent_clean_dt_lt3 | parent_gross_dt_gt50 | parent_gross_dt_gt51 |
| --- | ---------- | --------------- | --------------------- | ------------------- | -------------------- | -------------------- |
| 58  | 34141      | 16781           | 201                   | 37                  | 2                    | 2                    |
| 59  | 42303      | 21377           | 2161                  | 415                 | 14                   | 13                   |
| 60  | 36074      | 17029           | 2025                  | 428                 | 17                   | 16                   |
| 61  | 36535      | 18965           | 2319                  | 607                 | 25                   | 25                   |
| 62  | 37584      | 19089           | 2154                  | 420                 | 7                    | 7                    |
| 63  | 37030      | 18817           | 1045                  | 194                 | 9                    | 9                    |
| 65  | 38424      | 13038           | 251                   | 54                  | 0                    | 0                    |

The P02 early-peak rate is reproduced on the same 60,000-pulse recipe used by P02/P02b. The S07 guarded gross-tail count reproduces the documented 72-event count before any modeling.

## Methods
The benchmark uses App.I-style timing extremes: clean if `D_t<3 ns`, gross if `D_t>51 ns`; intermediate events are excluded. Predictions are leave-one-run-held-out across the seven Sample-II analysis runs, with run-block bootstrap CIs.

- **Traditional:** transparent P02 morphology scores. For each held-out run, the train folds choose among early-peak flags/counts, early-low-area count, and a hand-built P02 morphology score. No timing variables, run id, event id, or absolute amplitudes are used.
- **ML:** random forest over amplitude-normalized B2 shape plus selected-downstream mean/std shape summaries. It excludes `D_t`, `C_t`, run id, event id, absolute amplitudes, and selected-stave flags.
- **Leakage checks:** topology-only, absolute-amplitude-only, shuffled-label RF, forbidden-feature audit, and a leaky `D_t` ceiling.

## Early-Peak Association
| flag                   | n_flagged | gross_rate_flagged | gross_rate_unflagged | enrichment | auc_as_score |
| ---------------------- | --------- | ------------------ | -------------------- | ---------- | ------------ |
| any_early_peak         | 522       | 0.0191571          | 0.0363636            | 0.52682    | 0.450651     |
| b2_early_peak          | 270       | 0.0148148          | 0.0347471            | 0.426362   | 0.466061     |
| early_low_area_count>0 | 378       | 0.00793651         | 0.0373175            | 0.212675   | 0.433826     |

## Head-to-Head
| method                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | notes                                                                                                            |
| -------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| transparent P02 morphology | 0.692169 | 0.650121       | 0.736364        | 0.0629039         | 0.0396313 | 0.0933071  | Train-fold-selected transparent early-peak/low-area morphology score.                                            |
| shape-only RF morphology   | 0.999033 | 0.998328       | 0.99946         | 0.972779          | 0.940683  | 0.985778   | Fixed RF params={'n_estimators': 500, 'max_depth': 5, 'min_samples_leaf': 8}; 93 normalized morphology features. |

## Leakage Hunt
| probe                                  | roc_auc  | average_precision | notes                                                                                                                           |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| topology-only RF                       | 0.607183 | 0.106966          | Selected-stave flags and downstream count only; excluded from main RF.                                                          |
| absolute-amplitude-only RF             | 0.819535 | 0.275184          | Log amplitudes only; excluded from main RF.                                                                                     |
| B2-only shape RF                       | 0.889727 | 0.407565          | Upstream B2 normalized shape only; tests whether the result survives away from D_t source waveforms.                            |
| downstream-only shape RF               | 0.999156 | 0.976082          | Downstream normalized shape only; high values are label-source self-reference risk because D_t is derived from these waveforms. |
| shape RF with shuffled training labels | 0.484268 | 0.0373718         | Run-held-out null/leakage sanity check.                                                                                         |
| leaky D_t score                        | 1        | 1                 | Forbidden label-defining ceiling; reported only as a leakage reference.                                                         |
| forbidden feature audit                |          |                   | Forbidden columns in main RF: [].                                                                                               |

The RF is strong enough to require skepticism. The shuffled-label control is near chance, and the forbidden-feature audit found no `D_t`, `C_t`, run/event, amplitude, or selected-flag columns in the main RF matrix. However, the downstream-only waveform probe is also very high (AUC 0.999), while B2-only is much lower (AUC 0.890). Since `D_t` is computed from the same downstream waveforms, this is a label-source self-reference risk rather than an independent validation of pulse topology. The amplitude-only and topology-only probes are also non-trivial, so the morphology result should be read as a timing-tail proxy, not independent timing truth.

## Verdict
The original P02 early-peak flags do **not** validate as a positive timing-tail selector: `any_early_peak` is anti-enriched in gross events and has AUC 0.451. A broader transparent downstream morphology score is modestly predictive, AUC 0.692 [0.650, 0.736]. The shape-only RF reaches AUC 0.999 [0.998, 0.999], but the downstream-only leakage probe shows this is largely a morphology reconstruction of the timing-label source. Use P02d as a caution: early-peak topology itself is not the timing-tail driver, and high RF scores on `D_t` labels are not independent timing evidence.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python reports/1781009575.1697.2f57332a/p02d_early_peak_timing_tails.py --config reports/1781009575.1697.2f57332a/p02d_config.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `run_counts.csv`, `association_table.csv`, `scoreboard.csv`, `leakage_checks.csv`, `traditional_fold_choices.csv`, `fixed_efficiency.csv`, and `oof_predictions.csv`.
