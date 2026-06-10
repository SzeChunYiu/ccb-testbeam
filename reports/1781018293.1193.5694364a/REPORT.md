# Study report: P07d - boundary-shrinkage calibration for natural B2 saturation transfer

- **Ticket:** `1781018293.1193.5694364a`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT, runs 58, 59, 60, 61, 62, 63, 65
- **Command:** `/home/billy/anaconda3/bin/python scripts/p07d_1781018293_1193_5694364a_boundary_shrinkage.py --config configs/p07d_1781018293_1193_5694364a_boundary_shrinkage.json`

## Reproduction first
From raw ROOT and the same leave-one-run-out folds, the P07c primary shape-only
boundary q_template shift is reproduced as
`-0.082093`
versus archived
`-0.083233`.

## Boundary gate: 6500-7500 ADC
All methods below train on complete non-held-out runs only. CIs are run-bootstrap
95% intervals. The gate target is `|q_template shift| <= 0.025` and
`|CFD20 shift| <= 0.75 ns`.

| method | q_template shift | 95% CI | CFD20 shift ns | mean alpha | coverage |
|---|---:|---:|---:|---:|---:|
| P07c full shape transfer | -0.0821 | [-0.0846, -0.0804] | 0.420 | 1.000 | 1.000 |
| traditional fixed shrink 0.25 | -0.0221 | [-0.0229, -0.0216] | 0.107 | 0.250 | 1.000 |
| linear boundary shrink | -0.0229 | [-0.0244, -0.0218] | 0.112 | 0.260 | 1.000 |
| isotonic calibration | -0.0224 | [-0.0226, -0.0220] | 0.110 | 0.270 | 0.991 |
| ML calibration | -0.0224 | [-0.0226, -0.0220] | 0.110 | 0.270 | 1.000 |

## Application above 7000 ADC
The calibrated layers reduce the P07c full-transfer lift to the amount allowed
by the boundary gate.

| method | amplitude lift | 95% CI | q_template shift | CFD20 shift ns | coverage |
|---|---:|---:|---:|---:|---:|
| P07c full shape transfer | 0.1023 | [0.0948, 0.1137] | -0.0853 | 0.471 | 1.000 |
| linear boundary shrink | 0.0267 | [0.0239, 0.0296] | -0.0243 | 0.126 | 1.000 |
| isotonic calibration | 0.0219 | [0.0207, 0.0227] | -0.0200 | 0.104 | 0.954 |
| ML calibration | 0.0220 | [0.0208, 0.0227] | -0.0200 | 0.105 | 1.000 |

## Leakage checks
Leakage flags: **3**. Primary ML features exclude raw observed amplitude,
explicit ceiling, run id, and event id. The report includes observed-amplitude,
run/event/amplitude, and shuffled-target controls; see `leakage_checks.csv`.

## Conclusion
The P07c full shape transfer remains too aggressive for natural B2 saturation:
it reproduces the `-8.3%` boundary q_template shift. A boundary-calibrated
shrinkage layer is enough to pass the preregistered q_template and CFD20 gates.
The ML calibration does not produce a defensible gain over the linear boundary
shrinkage after leakage controls, so the simpler linear shrinkage is the
preferred correction layer for above-7000 ADC use.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `boundary_application_by_run.csv`,
`training_alpha_scan.csv`, `alpha_training_targets.csv.gz`,
`boundary_application_predictions_sample.csv`, `leakage_checks.csv`, and three
PNG diagnostics are in this folder.
