# S03e: all-three q_template clean-cut validation with curvature C_t

- **Ticket:** 1781027860.926.103338b4
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT in `data/root/root`
- **Benchmark runs:** 58, 59, 60, 61, 62, 63, 65

## Question
Can `q_template`-only clean-timing cuts be validated on the all-three-downstream population when the held-out tail label is curvature `C_t = t_B8 - 2t_B6 + t_B4`, without using App.A weak labels?

## Raw Reproduction First
The script first scans raw `HRDv` ROOT using the shared S00 gate: B2/B4/B6/B8 even channels, baseline median samples 0-3, and amplitude `A>1000` ADC. It also reproduces the S07 all-three downstream count gate before any q-template scoring.

| quantity                                             | report_value | reproduced | delta | tolerance | pass |
| ---------------------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses                        | 640737       | 640737     | 0     | 0         | True |
| sample_i_calib selected pulses                       | 248745       | 248745     | 0     | 0         | True |
| sample_i_analysis selected pulses                    | 252266       | 252266     | 0     | 0         | True |
| sample_ii_calib selected pulses                      | 14630        | 14630      | 0     | 0         | True |
| sample_ii_analysis selected pulses                   | 125096       | 125096     | 0     | 0         | True |
| S07 parent guarded gross events, D_t>51 ns           | 72           | 72         | 0     | 0         | True |
| all-three downstream control events                  | 3774         | 3774       | 0     | 0         | True |
| all-three downstream guarded gross events, D_t>51 ns | 22           | 22         | 0     | 0         | True |

Run counts for the timing benchmark:

| run | selected_pulses | parent_control_events | parent_clean_dt_lt3 | parent_gross_dt_gt51 | all_three_control_events | all_three_gross_dt_gt51 |
| --- | --------------- | --------------------- | ------------------- | -------------------- | ------------------------ | ----------------------- |
| 58  | 16781           | 201                   | 37                  | 2                    | 72                       | 0                       |
| 59  | 21377           | 2161                  | 415                 | 13                   | 749                      | 5                       |
| 60  | 17029           | 2025                  | 428                 | 16                   | 802                      | 6                       |
| 61  | 18965           | 2319                  | 607                 | 25                   | 925                      | 8                       |
| 62  | 19089           | 2154                  | 420                 | 7                    | 798                      | 1                       |
| 63  | 18817           | 1045                  | 194                 | 9                    | 365                      | 2                       |
| 65  | 13038           | 251                   | 54                  | 0                    | 63                       | 0                       |

## Methods
Templates are trained from calibration runs only. Each selected pulse is peak-normalized, CFD20-aligned, assigned to a fixed stave/amplitude bin, and scored by RMSE to the calibration median template. The validation target is external to App.A and uses all-three events only: clean if `|C_t| < 3.0 ns`, timing tail if `|C_t| > 51.0 ns`; intermediate events are excluded.

Template coverage:

| source         | n_bins |
| -------------- | ------ |
| bin            | 22     |
| stave_fallback | 10     |

Dataset:

| quantity                  | value     |
| ------------------------- | --------- |
| all-three control events  | 3774      |
| clean events \|C_t\|<3 ns | 728       |
| tail events \|C_t\|>51 ns | 23        |
| extreme benchmark events  | 751       |
| benchmark tail fraction   | 0.0306258 |

- **Traditional:** leave-one-run-out training chooses the best q-template aggregate among `q_max`, `q_mean`, downstream q summaries, q span, and B2-minus-downstream mean, with sign selected inside the training runs.
- **ML:** random forest using q-template aggregate features only. It excludes `D_t`, `C_t`, run id, event id, App.A labels, selected-stave flags, waveform samples, and amplitudes.
- **CIs:** all quoted intervals are held-out run bootstrap 95% CIs over the Sample-II analysis runs.

## Head-to-Head
| method                       | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | notes                                                                                                       |
| ---------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| traditional q_template score | 0.793956 | 0.767367       | 0.83812         | 0.16357           | 0.110245  | 0.227248   | Train-run-selected q-template aggregate score.                                                              |
| q_template-only RF           | 0.865833 | 0.814006       | 0.928173        | 0.331524          | 0.209331  | 0.516514   | RF params={'n_estimators': 500, 'max_depth': 5, 'min_samples_leaf': 8}; q-template aggregate features only. |

At 95% clean acceptance, held-out tail rejection is:

| method                       | clean_efficiency | tail_rejection | n_tail |
| ---------------------------- | ---------------- | -------------- | ------ |
| q_template-only RF           | 0.91921          | 0.837778       | 23     |
| traditional q_template score | 0.960063         | 0.346667       | 23     |

## Leakage Hunt
| probe                                       | roc_auc  | average_precision | notes                                                                                                                                                                                    |
| ------------------------------------------- | -------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| q-template RF with shuffled training labels | 0.497551 | 0.0310932         | Run-held-out null check; labels shuffled only inside training runs.                                                                                                                      |
| B2-only q-template RF                       | 0.606844 | 0.062267          | Upstream q_template only; away from downstream D_t source waveforms.                                                                                                                     |
| downstream-only q-template RF               | 0.836449 | 0.355522          | Downstream q_template only; shares waveform provenance with D_t labels.                                                                                                                  |
| absolute-amplitude-only RF                  | 0.718884 | 0.148033          | Amplitude nuisance probe; excluded from main RF.                                                                                                                                         |
| leaky \|C_t\| score                         | 1        | 1                 | Forbidden label-defining ceiling, reported only as a reference.                                                                                                                          |
| D_t cross-check score                       | 1        | 1                 | Not used as the primary target; reports how close span is to the curvature label.                                                                                                        |
| forbidden feature audit                     |          |                   | Forbidden main-feature columns: []; main features: ['q_b2', 'q_b4', 'q_b6', 'q_b8', 'q_mean', 'q_max', 'q_std', 'q_ds_mean', 'q_ds_max', 'q_ds_std', 'q_b2_minus_ds_mean', 'q_ds_span']. |

The q-template-only RF is not treated as independent timing truth: the forbidden `|C_t|` ceiling is label-defining, and downstream q features share waveform provenance with the curvature label. The shuffled-label control is AUC 0.498; downstream-only q is stronger than B2-only q (0.836 vs 0.607), so the validation is best interpreted as a downstream waveform-quality validation of a curvature-tail gate. No App.A label, timing span, curvature, run/event id, selected flag, waveform sample, or amplitude column enters the main ML matrix.

## Verdict
The raw reproduction gate passed exactly. On the all-three curvature-tail label, the traditional q score reaches AUC 0.794 [0.767, 0.838], and the q-template-only RF reaches AUC 0.866 [0.814, 0.928]. This supports using q_template as a conservative all-three clean-cut diagnostic, not as a replacement truth label for pile-up or App.A.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/s03e_1781027860_926_103338b4_all_three_curvature_qtemplate.py --config configs/s03e_1781027860_926_103338b4_all_three_curvature_qtemplate.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `run_counts.csv`, `template_bin_counts.csv`, `dataset_counts.csv`, `scoreboard.csv`, `fixed_clean_efficiency.csv`, `leakage_checks.csv`, `traditional_fold_choices.csv`, and `oof_predictions.csv`.
