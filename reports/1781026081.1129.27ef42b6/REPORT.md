# P05b: two-pulse abstention calibration for S07d injections

- **Ticket:** `1781026081.1129.27ef42b6`
- **Worker:** `testbeam-laptop-2`
- **Inputs:** raw HRD ROOT files only; no Monte Carlo.
- **Split:** train runs `[58, 59, 60, 61, 62]`, held-out runs `[63, 65]`; CIs bootstrap held-out source runs.

## Reproduction first

Before calibration, the raw `HRDv` selected-pulse gate reproduced `640737` B-stave pulses versus `640737` reported, with zero tolerance. The S10 injection AP reproduction values are `[0.982, 0.9719]`.

## Methods

Traditional method: bounded two-pulse template recovery with train-only cuts on fit failure, fractional SSE improvement, chi2/ndf proxy, fitted separation, and predicted secondary/primary amplitude ratio.

ML method: the S11a MLP recovery output is converted into an isotonic failure-probability gate using leave-one-run-out training folds. The gate uses normalized waveform features plus fit diagnostics, and the threshold is selected only on train runs to target bad-recovery rate <= `0.15`.

Bad recovery means base failure, event constituent-time RMS > `12.0` ns, or absolute charge bias > `0.20`.

## Held-out result

| method                         | coverage | abstention_rate | accepted_time_rms_ns | accepted_time_rms_ns_ci_low | accepted_time_rms_ns_ci_high | bad_recovery_rate | risk_coverage_auc |
| ------------------------------ | -------- | --------------- | -------------------- | --------------------------- | ---------------------------- | ----------------- | ----------------- |
| traditional_train_quality_cuts | 0.355    | 0.645           | 9.90322              | 8.65745                     | 11.1012                      | 0.150235          | 0.193549          |
| ml_isotonic_failure_gate       | 0.698333 | 0.301667        | 9.68225              | 9.42046                     | 9.94569                      | 0.188544          | 0.179032          |

The ML isotonic gate accepts many more held-out two-pulse corrections and has slightly lower accepted timing RMS, but it does not meet the 0.15 held-out bad-recovery target. The traditional gate is stricter and lands closest to the target, so the result is a coverage-versus-risk tradeoff rather than a clean ML operating-point win.

## Secondary-Amplitude Sidebands

| method                         | secondary_amplitude_sideband | coverage | abstention_rate | accepted_time_rms_ns | bad_recovery_rate |
| ------------------------------ | ---------------------------- | -------- | --------------- | -------------------- | ----------------- |
| ml_isotonic_failure_gate       | equal_secondary_ratio_1.00   | 0.78     | 0.22            | 7.88688              | 0.119658          |
| traditional_train_quality_cuts | equal_secondary_ratio_1.00   | 0.326667 | 0.673333        | 8.09845              | 0.0612245         |
| ml_isotonic_failure_gate       | high_secondary_ratio_0.75    | 0.75974  | 0.24026         | 7.49028              | 0.0769231         |
| traditional_train_quality_cuts | high_secondary_ratio_0.75    | 0.467532 | 0.532468        | 6.04791              | 0.0277778         |
| ml_isotonic_failure_gate       | low_secondary_ratio_0.25     | 0.492424 | 0.507576        | 13.561               | 0.4               |
| traditional_train_quality_cuts | low_secondary_ratio_0.25     | 0.19697  | 0.80303         | 17.6494              | 0.576923          |
| ml_isotonic_failure_gate       | mid_secondary_ratio_0.50     | 0.731707 | 0.268293        | 10.6004              | 0.25              |
| traditional_train_quality_cuts | mid_secondary_ratio_0.50     | 0.402439 | 0.597561        | 10.2569              | 0.181818          |

The sideband table is written to `secondary_amplitude_sidebands.csv`. Low secondary-amplitude overlays are the hardest operational region; both methods abstain most there.

## Leakage Review

All leakage checks pass: `True`. The checks cover train/held-out run disjointness, event-id overlap, train-only threshold selection, ML leave-one-run-out calibration folds, and a shuffled-label MLP sentinel.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p05b_1781026081_1129_27ef42b6_abstention_calibration.py --config configs/p05b_1781026081_1129_27ef42b6.json
```

Runtime in this run was `31.33` s.
