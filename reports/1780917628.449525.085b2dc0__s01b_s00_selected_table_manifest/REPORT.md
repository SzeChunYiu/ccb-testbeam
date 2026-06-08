# Study report: S01b - S00 selected-pulse table manifest and regeneration hook

- **Study ID:** S01b
- **Author (worker label):** testbeam-laptop-3
- **Date:** 2026-06-08
- **Depends on:** S00
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `e96dcd095081b209d4018a07fc8a2c07b0ad362d`
- **Config:** `s01b_s00_reproduction_local.yaml`

## 0. Question

Can downstream workers reliably locate or regenerate the S00 selected B-stave pulse table, with a pinned row count, checksum, and command that does not write into read-only `data/`?

Atomic steps:
- Check whether `data/processed/s00_selected_b_pulses.csv.gz` exists in the current read-only data mirror.
- Re-run the S00 raw-ROOT reproduction with paths corrected for this sandbox layout.
- Write the regenerated table, manifest, and hook under this owned report directory.
- Benchmark the deterministic selection rule against the S00 run-split ML sanity check.

## 1. Reproduction

The processed data artifact expected by the S00 config is **not present** at `data/processed/s00_selected_b_pulses.csv.gz` in this clone. Reproduction therefore used the raw ROOT files directly and redirected the selected table to this report directory:

`reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz`

Match table:

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_i_calib events with selected pulse | 239559 | 239559 | 0 | 0 | yes |
| sample_i_calib selected pulses | 248745 | 248745 | 0 | 0 | yes |
| sample_i_analysis events with selected pulse | 243133 | 243133 | 0 | 0 | yes |
| sample_i_analysis selected pulses | 252266 | 252266 | 0 | 0 | yes |
| sample_i_analysis B2 selected pulses | 241422 | 241422 | 0 | 0 | yes |
| sample_i_analysis B4 selected pulses | 6451 | 6451 | 0 | 0 | yes |
| sample_i_analysis B6 selected pulses | 3094 | 3094 | 0 | 0 | yes |
| sample_i_analysis B8 selected pulses | 1299 | 1299 | 0 | 0 | yes |
| sample_ii_calib events with selected pulse | 12103 | 12103 | 0 | 0 | yes |
| sample_ii_calib selected pulses | 14630 | 14630 | 0 | 0 | yes |
| sample_ii_analysis events with selected pulse | 89807 | 89807 | 0 | 0 | yes |
| sample_ii_analysis selected pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 selected pulses | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 selected pulses | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 selected pulses | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 selected pulses | 4506 | 4506 | 0 | 0 | yes |

The regenerated gzip has 640,737 data rows plus one header row. Its sha256 is `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f`.

## 2. Traditional method

The production method is the S00 deterministic gate:
- read `h101/HRDv` from `data/root/root/hrdb_run_NNNN.root`;
- reshape to eight channels with 18 samples each;
- use physical B-stave even channels `{0,2,4,6}` for `{B2,B4,B6,B8}`;
- subtract the median of samples 0-3;
- select pulses with `max(waveform - baseline) > 1000 ADC`.

No fit is involved, so chi2/ndf is not applicable. The exact-count uncertainty is zero for fixed inputs and fixed code; provenance risk is handled by `input_sha256.csv`, `manifest.json`, and the selected-table checksum.

## 3. ML method

The ML check is inherited from S00 and rerun with the report-local config. It is a calibrated logistic regression using `amplitude_adc`, `area_adc_samples`, `peak_sample`, and `baseline_adc`, split by run with held-out runs 57 and 65. The hyperparameter scan covered `C in {0.01, 0.1, 1.0, 10.0}` with 3-fold stratified CV; best CV ROC AUC was at `C=10.0`. Isotonic calibration and a reliability plot are recorded in `fig_ml_reliability.png`.

This model is a sanity check only. The label is the deterministic threshold rule, so it must not replace the rule used to build the table.

## 4. Head-to-head benchmark

| Method | Metric | Value +/- CI | Notes |
|---|---|---:|---|
| Traditional threshold | held-out selection accuracy | 1.000000 [1.000000, 1.000000] | Exact table definition. |
| Calibrated logistic regression | held-out selection accuracy | 0.999796 [0.999491, 1.000000] | Run-split sanity check; not used for production. |

Verdict: ML does not beat the deterministic baseline. Downstream workers should consume or regenerate the deterministic table and validate its sha256 before analysis.

## 5. Falsification

- **Pre-registration:** before looking at regenerated outputs, the pass condition was exact reproduction of the S00 selected-row count and zero deltas in the match table, with the regenerated table checksum recorded.
- **Falsification test:** any nonzero delta in `count_match_table.csv`, a row count other than 640,737, or a missing ROOT input would falsify the claim that the table can be regenerated from the current raw mirror.
- **Result:** passed with zero count deltas in one configured reproduction attempt. No multiple-comparison correction is needed because no cuts or model families were selected post hoc.

## 6. Threats to validity

- **Benchmark/selection:** the traditional baseline is the exact production rule, not a strawman; the ML model is only a sanity check.
- **Data leakage:** the ML check splits by run. The selected table itself is deterministic and does not train on labels.
- **Metric misuse:** table validity is measured by exact row count and checksum, not by ML accuracy.
- **Post-hoc selection:** the amplitude cut, channel mapping, run list, and held-out runs are inherited from S00 and fixed in `s01b_s00_reproduction_local.yaml`.

## 7. Provenance manifest

`manifest.json` records the command, config, git commit, input checksum table, selected table sha256, and output hashes. `regenerate_s00_selected_table.sh` is the report-local regeneration hook:

```bash
bash reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/regenerate_s00_selected_table.sh
```

## 8. Findings & next steps

The current read-only data mirror does not contain `data/processed/s00_selected_b_pulses.csv.gz`, but the table can be regenerated from raw ROOT in this sandbox with exact S00 count reproduction. The working table for this ticket is committed under this report directory so downstream workers have a pinned checksum to compare against.

Hypothesis: recent downstream blocks were caused by an absent processed-data artifact and path-layout drift (`data/extracted/...` in config versus `data/root/root` in the current mirror), not by a physics or S00 reproduction discrepancy. This is confirmed by exact raw-ROOT reproduction with the corrected local paths and would be falsified if another clone with the same raw hashes failed to reproduce the table checksum.

Recommended next tickets:
- S01c: publish or document the canonical non-git processed-data location for `s00_selected_b_pulses.csv.gz`. Expected information gain: separates infrastructure setup from S01 analysis and prevents every worker from regenerating the same 640,737-row table.
- S01d: add downstream consumers that validate the selected-table sha256 before S01/S02 analysis. Expected information gain: catches stale or layout-mismatched processed artifacts before timing/template code uses them.

## 9. Reproducibility

Commands:

```bash
python scripts/01_build_pulse_table_from_root.py --config reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s01b_s00_reproduction_local.yaml
gzip -cd reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz | wc -l
sha256sum reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
```

Output artifacts are all files in this directory. The generated table is intentionally report-local in this PR because `data/` is read-only.
