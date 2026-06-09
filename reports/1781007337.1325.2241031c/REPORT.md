# Study report: S10d - two-pulse template resolvability live-time

- **Study ID:** S10d
- **Ticket:** `1781007337.1325.2241031c`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s10d_two_pulse_resolvability_livetime.json`

## 0. Question

Using only raw-pulse-derived B-stack templates and real residuals, what two-pulse delay is needed before the recovered constituent timing bias is below 1 ns and the total-area bias is below 20%? The benchmark compares a constrained traditional two-pulse template fit with a compact ML classifier/regressor under a run-held-out split.

## 1. Reproduction gate

The raw `HRDv` S00 selected-pulse count gate was rerun first. It passed exactly: `640737` selected B-stave pulses versus `640737` reported. Sample-II per-stave counts also have zero delta in `reproduction_match_table.csv`.

The S10 injection-trained ML AP handle was also rerun from raw ROOT before the new benchmark. Reproduced AP values are `[0.982, 0.9719]` for `['S10 low_2nA injection ML AP', 'S10 high_20nA injection ML AP']` with the documented 0.006 absolute tolerance.

The S10b live-time gate was then rerun from raw ROOT before S10d. It reproduced `124.79 ns` for the measured live10 window and `3.05 MHz` for the measured-tau rescaled combined Rmax. See `s10b_reproduction.csv`.

## 2. Methods

Templates are median S01-style empirical pulse shapes built from run-held-out training pulses only. Injected events use the same template library plus real single-pulse residuals from the source run/stave. Training runs are `[58, 59, 60, 61, 62]`; held-out runs are `[63, 65]`.

The traditional method is a bounded two-pulse template fit. It uses the S02 CFD20 timing initialization, scans first-pulse timing offsets and fixed separation hypotheses, solves amplitudes plus baseline by least squares, and counts constrained-fit failures. Its overlap score is the fractional SSE improvement over a one-pulse fit.

The ML method is a compact MLP classifier plus MLP regressor trained on the same injected mixtures. It sees only waveform-shape features and predicts overlap probability, two times, and two amplitudes.

## 3. Resolvability delay

The delay live-time is the first held-out separation where all larger tested separations satisfy `abs(median timing bias) < 1 ns` and `abs(median total-area bias) < 0.20`.

| Method | delay ns | bootstrap 95% CI ns | AP | time RMS ns | area bias | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| constrained template fit | 60.0 | [40.0, 60.0] | 0.757 | 13.83 | -0.030 | 0.172 |
| compact ML | 20.0 | [15.0, 60.0] | 0.834 | 9.41 | -0.008 | 0.323 |

The compact ML method reaches the bias criteria at a shorter held-out delay than the constrained template fit in this closure. That win is treated cautiously because both methods are trained/evaluated on template-like injections and the leakage probes are required for interpretation. Bootstrap CIs are run-held-out resamples from the held-out source runs and are in `resolvability_bootstrap_ci.csv`.

## 4. Separation and ratio dependence

Performance degrades sharply at the closest tested delays. The detailed held-out bias table is in `resolvability_by_delay.csv`; per-run held-out delay estimates are in `run_heldout_resolvability.csv`. Traditional and ML aggregate recovery tables remain in `head_to_head_overall.csv`, `metrics_by_separation.csv`, and `metrics_by_ratio.csv`.

## 5. Leakage checks

Run splitting is strict: no source run appears in both train and held-out sets. Event ids are generated per split and have no overlap. A shuffled-label classifier gives held-out AP `0.466`, recorded in `leakage_checks.csv`; this is consistent with no obvious label leakage.

## 6. Threats to validity

The injections are data-driven but still synthetic: both methods are evaluated on pulses generated from the same empirical template family. Real beam pile-up can include pathology, saturation, and topology effects not represented by this closure test. The strongest claim supported here is therefore method ranking for template-like overlapping pulses, not a final beam pile-up decomposition.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s10d_two_pulse_resolvability_livetime.py --config configs/s10d_two_pulse_resolvability_livetime.json
```

Runtime in this run was `91.77` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, delay tables, metrics tables, leakage checks, and figures.
