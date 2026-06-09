# P02e: all-three early-peak timing-tail validation

- **Ticket:** 1781015838.1380.00770dd4
- **Worker:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT in `data/root/root`
- **Runs:** P02 sample 58, 59, 60, 61, 62, 63, 65, 50; timing benchmark 58, 59, 60, 61, 62, 63, 65

## Question
Does the reproducible P02 early-peak/low-area pulse topology predict S02/S07 timing-tail behavior after restricting the target population to events with B2, B4, B6, and B8 all selected?

## Raw Reproduction First
Selection follows the shared raw ROOT rule: B2/B4/B6/B8 from `HRDv`, baseline median samples 0-3, amplitude `A>1000` ADC, and CFD20 times for downstream timing. The documented parent gate is reproduced before the all-three restriction, then the benchmark is limited to all-three downstream events.

| quantity                                             | report_value | reproduced | delta        | tolerance | pass | sample_size |
| ---------------------------------------------------- | ------------ | ---------- | ------------ | --------- | ---- | ----------- |
| P02 early-peak pulse rate, peak_sample<=3            | 0.044        | 0.0438833  | -0.000116667 | 0.002     | True | 60000       |
| S07 parent guarded gross events, D_t>51 ns           | 72           | 72         | 0            | 0         | True | 10156       |
| all-three downstream control events                  | 3774         | 3774       | 0            | 0         | True | 10156       |
| all-three downstream guarded gross events, D_t>51 ns | 22           | 22         | 0            | 0         | True | 3774        |

Run-level timing counts:

| run | raw_events | selected_pulses | parent_control_events | parent_clean_dt_lt3 | parent_gross_dt_gt50 | parent_gross_dt_gt51 | all_three_control_events | all_three_clean_dt_lt3 | all_three_gross_dt_gt51 |
| --- | ---------- | --------------- | --------------------- | ------------------- | -------------------- | -------------------- | ------------------------ | ---------------------- | ----------------------- |
| 58  | 34141      | 16781           | 201                   | 37                  | 2                    | 2                    | 72                       | 9                      | 0                       |
| 59  | 42303      | 21377           | 2161                  | 415                 | 14                   | 13                   | 749                      | 93                     | 5                       |
| 60  | 36074      | 17029           | 2025                  | 428                 | 17                   | 16                   | 802                      | 129                    | 6                       |
| 61  | 36535      | 18965           | 2319                  | 607                 | 25                   | 25                   | 925                      | 176                    | 8                       |
| 62  | 37584      | 19089           | 2154                  | 420                 | 7                    | 7                    | 798                      | 111                    | 1                       |
| 63  | 37030      | 18817           | 1045                  | 194                 | 9                    | 9                    | 365                      | 57                     | 2                       |
| 65  | 38424      | 13038           | 251                   | 54                  | 0                    | 0                    | 63                       | 4                      | 0                       |

The P02 early-peak rate is reproduced on the same 60,000-pulse recipe used by P02/P02b. The S07 guarded gross-tail count reproduces the documented 72-event parent count before any modeling; the all-three subset then reproduces the 3,774 control-event and 22 guarded-gross-event gates.

## Methods
The benchmark uses App.I-style timing extremes inside the all-three subset: clean if `D_t<3 ns`, gross if `D_t>51 ns`; intermediate events are excluded. Predictions are leave-one-run-held-out across the seven Sample-II analysis runs, with run-block bootstrap CIs. Missing-stave topology is constant by construction.

- **Traditional:** transparent P02 morphology scores. For each held-out run, the train folds choose among early-peak flags/counts, early-low-area count, and a hand-built P02 morphology score. No timing variables, run id, event id, or absolute amplitudes are used.
- **ML:** random forest over amplitude-normalized B2 shape plus selected-downstream mean/std shape summaries. It excludes `D_t`, `C_t`, run id, event id, absolute amplitudes, and selected-stave flags.
- **Leakage checks:** constant topology audit, absolute-amplitude-only, B2-only and downstream-only shape probes, shuffled-label RF, forbidden-feature audit, and a leaky `D_t` ceiling.

## Early-Peak Association
| flag                   | n_flagged | gross_rate_flagged | gross_rate_unflagged | enrichment | auc_as_score |
| ---------------------- | --------- | ------------------ | -------------------- | ---------- | ------------ |
| any_early_peak         | 141       | 0.0283688          | 0.0391304            | 0.72498    | 0.472602     |
| b2_early_peak          | 60        | 0.0333333          | 0.0369686            | 0.901667   | 0.495368     |
| early_low_area_count>0 | 83        | 0.0120482          | 0.0405405            | 0.297189   | 0.451916     |

## Head-to-Head
| method                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | notes                                                                                                            |
| -------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| transparent P02 morphology | 0.638562 | 0.610736       | 0.727285        | 0.0538732         | 0.0533393 | 0.190086   | Train-fold-selected transparent early-peak/low-area morphology score.                                            |
| shape-only RF morphology   | 0.994348 | 0.980468       | 0.999474        | 0.911199          | 0.65474   | 0.991318   | Fixed RF params={'n_estimators': 500, 'max_depth': 5, 'min_samples_leaf': 8}; 93 normalized morphology features. |

## Leakage Hunt
| probe                                  | roc_auc  | average_precision | notes                                                                                                                           |
| -------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| constant all-three topology RF         | 0.533522 | 0.0430573         | Selected-stave flags and downstream count only; all benchmark rows have downstream_count unique=[3].                            |
| absolute-amplitude-only RF             | 0.774925 | 0.270608          | Log amplitudes only; excluded from main RF.                                                                                     |
| B2-only shape RF                       | 0.881143 | 0.397163          | Upstream B2 normalized shape only; tests whether the result survives away from D_t source waveforms.                            |
| downstream-only shape RF               | 0.995368 | 0.911585          | Downstream normalized shape only; high values are label-source self-reference risk because D_t is derived from these waveforms. |
| shape RF with shuffled training labels | 0.578191 | 0.050365          | Run-held-out null/leakage sanity check.                                                                                         |
| leaky D_t score                        | 1        | 1                 | Forbidden label-defining ceiling; reported only as a leakage reference.                                                         |
| forbidden feature audit                |          |                   | Forbidden columns in main RF: [].                                                                                               |

The RF is strong enough to require skepticism. The shuffled-label control is near chance, and the forbidden-feature audit found no `D_t`, `C_t`, run/event, amplitude, or selected-flag columns in the main RF matrix. Missing-stave topology is removed because every benchmark row has all three downstream staves selected. However, the downstream-only waveform probe is also very high (AUC 0.995), while B2-only is lower (AUC 0.881). Since `D_t` is computed from the same downstream waveforms, this remains label-source self-reference risk rather than independent validation of pulse topology. The amplitude-only probe is also non-trivial, so the morphology result should be read as a timing-tail proxy, not independent timing truth.

## Verdict
After removing missing-stave topology, the original P02 early-peak flags still do **not** validate as a robust positive timing-tail selector: `any_early_peak` has AUC 0.473. A broader transparent morphology score reaches AUC 0.639 [0.611, 0.727]. The shape-only RF reaches AUC 0.994 [0.980, 0.999], but the downstream-only leakage probe shows this is still largely a morphology reconstruction of the timing-label source. P02e removes the missing-stave explanation for P02d's high RF score, but does not turn `D_t`-derived waveform scores into independent timing evidence.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python reports/1781015838.1380.00770dd4/p02e_all_three_early_peak_timing_tails.py --config reports/1781015838.1380.00770dd4/p02e_config.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `run_counts.csv`, `association_table.csv`, `scoreboard.csv`, `leakage_checks.csv`, `traditional_fold_choices.csv`, `fixed_efficiency.csv`, and `oof_predictions.csv`.
