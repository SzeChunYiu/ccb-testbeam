# S03d: q_template-only clean-timing validation

- **Ticket:** 1781012848.2643.539f1f83
- **Worker:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT in `/home/billy/ccb-data/extracted/root/root`
- **Benchmark runs:** 58, 59, 60, 61, 62, 63, 65

## Question
Can `q_template`-only clean-timing cuts be validated against held-out downstream timing tails without using App.A weak labels?

## Raw Reproduction First
The script first scans raw `HRDv` ROOT using the shared S00 gate: B2/B4/B6/B8 even channels, baseline median samples 0-3, and amplitude `A>1000` ADC. It also reproduces the S07 downstream timing-tail parent gate using CFD20 downstream span `D_t`.

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
Templates are trained from calibration runs only. Each selected pulse is peak-normalized, CFD20-aligned, assigned to a fixed stave/amplitude bin, and scored by RMSE to the calibration median template. The validation target is external to App.A: clean if `D_t < 3.0 ns`, timing tail if `D_t > 51.0 ns`; intermediate events are excluded.

Template coverage:

| source         | n_bins |
| -------------- | ------ |
| bin            | 22     |
| stave_fallback | 10     |

Dataset:

| quantity                 | value     |
| ------------------------ | --------- |
| parent control events    | 10156     |
| clean events D_t<3 ns    | 2155      |
| tail events D_t>51 ns    | 72        |
| extreme benchmark events | 2227      |
| benchmark tail fraction  | 0.0323305 |

- **Traditional:** leave-one-run-out training chooses the best q-template aggregate among `q_max`, `q_mean`, downstream q summaries, q span, and B2-minus-downstream mean, with sign selected inside the training runs.
- **ML:** random forest using q-template aggregate features only. It excludes `D_t`, `C_t`, run id, event id, App.A labels, selected-stave flags, waveform samples, and amplitudes.
- **CIs:** all quoted intervals are held-out run bootstrap 95% CIs over the Sample-II analysis runs.

## Head-to-Head
| method                       | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | notes                                                                                                       |
| ---------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| traditional q_template score | 0.712233 | 0.617694       | 0.751726        | 0.157567          | 0.0758817 | 0.281014   | Train-run-selected q-template aggregate score.                                                              |
| q_template-only RF           | 0.898047 | 0.862737       | 0.921023        | 0.362884          | 0.205059  | 0.492788   | RF params={'n_estimators': 500, 'max_depth': 5, 'min_samples_leaf': 8}; q-template aggregate features only. |

At 95% clean acceptance, held-out tail rejection is:

| method                       | clean_efficiency | tail_rejection | n_tail |
| ---------------------------- | ---------------- | -------------- | ------ |
| q_template-only RF           | 0.940029         | 0.549184       | 72     |
| traditional q_template score | 0.952746         | 0.198164       | 72     |

## Leakage Hunt
| probe                                       | roc_auc  | average_precision | notes                                                                                                                                                                                    |
| ------------------------------------------- | -------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| q-template RF with shuffled training labels | 0.582979 | 0.0430265         | Run-held-out null check; labels shuffled only inside training runs.                                                                                                                      |
| B2-only q-template RF                       | 0.552578 | 0.0398001         | Upstream q_template only; away from downstream D_t source waveforms.                                                                                                                     |
| downstream-only q-template RF               | 0.898079 | 0.348771          | Downstream q_template only; shares waveform provenance with D_t labels.                                                                                                                  |
| absolute-amplitude-only RF                  | 0.825796 | 0.239639          | Amplitude nuisance probe; excluded from main RF.                                                                                                                                         |
| leaky D_t score                             | 1        | 1                 | Forbidden label-defining ceiling, reported only as a reference.                                                                                                                          |
| forbidden feature audit                     |          |                   | Forbidden main-feature columns: []; main features: ['q_b2', 'q_b4', 'q_b6', 'q_b8', 'q_mean', 'q_max', 'q_std', 'q_ds_mean', 'q_ds_max', 'q_ds_std', 'q_b2_minus_ds_mean', 'q_ds_span']. |

The q-template-only RF is not suspiciously perfect: AUC 0.898, while the shuffled-label control is AUC 0.583. The downstream-only q probe is stronger than the B2-only probe (0.898 vs 0.553), so the validation is best interpreted as a downstream waveform-quality validation of the timing-tail gate, not independent truth about upstream topology. No App.A label, timing span, run/event id, selected flag, waveform sample, or amplitude column enters the main ML matrix.

## Verdict
The raw reproduction gate passed exactly. `q_template` carries real held-out information about downstream timing tails: the traditional q score reaches AUC 0.712 [0.618, 0.752], and the q-template-only RF reaches AUC 0.898 [0.863, 0.921]. This supports replacing the retired App.A count with a run-held-out downstream timing-tail validation gate for q-template clean cuts, with the caveat that downstream q features and downstream `D_t` share waveform provenance.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python reports/1781012848.2643.539f1f83/s03d_1781012848_qtemplate_tail_validation.py --config reports/1781012848.2643.539f1f83/s03d_1781012848_config.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `run_counts.csv`, `template_bin_counts.csv`, `dataset_counts.csv`, `scoreboard.csv`, `fixed_clean_efficiency.csv`, `leakage_checks.csv`, `traditional_fold_choices.csv`, and `oof_predictions.csv`.
