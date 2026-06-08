# Study report: S00 - Data integrity and pipeline reproduction

- **Study ID:** S00
- **Author (worker label):** testbeam-gate-1
- **Date:** 2026-06-08
- **Depends on:** none
- **Input checksum(s):** `reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv`
- **Git commit:** `dcde28d` for the code/config that produced this report's artifacts
- **Config:** `configs/s00_reproduction.yaml`

## 0. Question

Can the selected B-stack pulse table be rebuilt from reduced raw ROOT files by applying the documented `A > 1000 ADC` cut to physical B-stave channels, and does it reproduce the report's 640,737 selected pulses and key per-run/per-stave counts exactly?

Atomic steps:
- Read `h101/HRDv` from `data/extracted/root/root/hrdb_run_NNNN.root`.
- Reshape each event into eight 18-sample channel blocks.
- Use even channel blocks `{0,2,4,6}` as physical staves `{B2,B4,B6,B8}`; odd blocks are duplicate readout-side channels and are not part of the selected B-stave pulse table.
- Compute pedestal as the median of samples 0-3 and amplitude as `max(waveform - pedestal)`.
- Select pulses with `A > 1000 ADC`.

## 1. Reproduction (mandatory - gate)

Gate result: **PASSED**. The raw ROOT reproduction matches every checked report count with zero tolerance.

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

The reproduced group table is:

| Group | Events total | Events with selected pulse | Selected pulses | B2 | B4 | B6 | B8 |
|---|---:|---:|---:|---:|---:|---:|---:|
| sample_i_calib | 409815 | 239559 | 248745 | 237882 | 6747 | 2940 | 1176 |
| sample_i_analysis | 388879 | 243133 | 252266 | 241422 | 6451 | 3094 | 1299 |
| sample_ii_calib | 35943 | 12103 | 14630 | 11907 | 1689 | 763 | 271 |
| sample_ii_analysis | 262091 | 89807 | 125096 | 88213 | 21229 | 11148 | 4506 |

The exact machine-readable table is `count_match_table.csv`.

## 2. Traditional (non-ML) method

The production reproduction method is deterministic waveform thresholding:

1. For every configured B run, read `HRDv`.
2. For each physical stave channel, subtract the median of the first four samples.
3. Count a selected pulse if `max(corrected waveform) > 1000 ADC`.

No fit is involved, so chi2/ndf is not applicable. The statistical uncertainty on an exact data-integrity count is zero for a fixed input file and fixed algorithm; the relevant uncertainty is systematic/provenance risk. The dominant systematic checked here is channel mapping: counting all eight channels gives duplicate-readout overcounts, while the even-channel physical-stave mapping gives the documented totals exactly.

Validation artifacts:
- `fig_counts_by_run.png`
- `fig_counts_by_group_stave.png`
- `fig_amplitude_distributions.png`
- `sorted_even_channel_crosscheck.csv`

The sorted-file `hrdMax` values are **not** used for the gate. Counting even sorted `hrdMax` channels gives larger counts than raw `HRDv` because that branch is a derived representation with different pulse extraction semantics. This confirms the S00 gate must be pinned to the raw waveform rule above.

## 3. ML method

An ML sanity check was run only to satisfy the study template's head-to-head discipline; it is not used to define the gate count.

Model:
- Calibrated logistic regression with features `amplitude_adc`, `area_adc_samples`, `peak_sample`, `baseline_adc`.
- Split by run: held-out runs 57 and 65.
- Hyperparameter CV: `C in {0.01, 0.1, 1.0, 10.0}`, 3-fold stratified CV on the non-held-out sample.
- Calibration: isotonic calibration; reliability diagram in `fig_ml_reliability.png`.
- Bootstrap: 300 resamples for held-out selection accuracy CI.

Best CV setting was `C=10.0`. Held-out performance is near-perfect but still inferior to the deterministic threshold for this task. This is expected: the label is the threshold rule itself, not physics truth.

## 4. Head-to-head benchmark (mandatory)

Held-out data: sampled pulses from runs 57 and 65. Metric: selection accuracy against the deterministic `A > 1000 ADC` label.

| Method | Metric | Value +/- CI | Notes |
|---|---|---:|---|
| Traditional threshold | selection accuracy | 1.000000 [1.000000, 1.000000] | The exact gate definition. |
| Calibrated logistic regression | selection accuracy | 0.999796 [0.999491, 1.000000] | Sanity check only; ROC AUC 1.000, Brier 0.000126. |

Verdict: ML does not beat the deterministic baseline and should not be used for S00 selection. The threshold method wins by about 0.020 percentage points on the sampled held-out benchmark and, more importantly, is exactly reproducible.

## 5. Systematics & caveats

- Physical B-stave selection requires even raw channels `{0,2,4,6}`. Including odd channels double-counts duplicate readout-side blocks.
- Run 38 is absent locally and is not part of the configured B split. The exact gate count uses Sample I calibration runs 31-37 and 39-42, Sample I analysis runs 44-57, Sample II calibration run 64, and Sample II analysis runs 58-63 and 65.
- The count gate resolves the run-split basis for the selected pulse table: the newer report split with Sample II calibration run 64 matches exactly. It does not test the older timing-calibration choice of run 61.
- The 2 cm vs 4 cm stave-spacing discrepancy is not exercised by pulse counting. It remains a timing-geometry issue for S02-S06/S18, not a blocker for the S00 count gate.
- The selected pulse table is written to `data/processed/s00_selected_b_pulses.csv.gz`, which is intentionally ignored by git.

## 6. Findings & next steps

- S00 count reproduction passed exactly from raw ROOT: 640,737 selected B-stave pulses.
- The B2-dominated Sample I analysis topology is reproduced: 241,422 B2 pulses versus 10,844 downstream pulses.
- Sample II analysis is more penetrating: 88,213 B2, 21,229 B4, 11,148 B6, 4,506 B8.
- The deterministic threshold is the correct production method for S00. ML adds no value and is slightly worse on the sampled held-out benchmark.

Recommended next tickets:
- S00a: reconcile sorted `hrdMax` semantics against raw `HRDv` amplitudes, to prevent future workers from using sorted counts as a gate proxy.
- S01: build the amplitude-adaptive template and evaluate `q_template` on the full selected-pulse table.
- S02: scan timing pickoff methods on the reproduced selected-pulse table, with the 2 cm vs 4 cm geometry assumption explicitly parameterized.

## 7. Reproducibility

Commands:

```bash
python scripts/01_build_pulse_table_from_root.py --config configs/s00_reproduction.yaml
```

Generated committed artifacts:
- `reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv`
- `reports/S00_data_integrity_pipeline_reproduction/counts_by_group.csv`
- `reports/S00_data_integrity_pipeline_reproduction/counts_by_run.csv`
- `reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv`
- `reports/S00_data_integrity_pipeline_reproduction/ml_benchmark.csv`
- `reports/S00_data_integrity_pipeline_reproduction/ml_cv_scan.csv`
- `reports/S00_data_integrity_pipeline_reproduction/sorted_even_channel_crosscheck.csv`
- `reports/S00_data_integrity_pipeline_reproduction/fig_counts_by_run.png`
- `reports/S00_data_integrity_pipeline_reproduction/fig_counts_by_group_stave.png`
- `reports/S00_data_integrity_pipeline_reproduction/fig_amplitude_distributions.png`
- `reports/S00_data_integrity_pipeline_reproduction/fig_ml_reliability.png`
- `reports/S00_data_integrity_pipeline_reproduction/manifest.json`

Generated non-committed data artifact:
- `data/processed/s00_selected_b_pulses.csv.gz`
