# Study report: P07c - boundary-control closure for natural B2 saturation transfer

- **Ticket:** `1781010522.1275.6b5664c7`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs 58, 59, 60, 61, 62, 63, 65
- **Command:** `/home/billy/anaconda3/bin/python scripts/p07c_boundary_control_closure.py --config configs/p07c_boundary_control_closure.json`

## Reproduction first
From raw ROOT, the upstream P07 `C=4000 ADC` ML res68 is reproduced as
`0.032431778078` versus archived
`0.032431778078`.

The P07b multi-ceiling natural-transfer numbers are also reproduced before the
new closure: artificial ratio-transfer res68 `0.0393`
and natural `A>=7000` q_template shift `-0.0897`.

## Held-out artificial closure
All rows below are leave-one-run-out with run-bootstrap 95% CIs.

| method | res68 | 95% CI | median bias |
|---|---:|---:|---:|
| traditional template family | 0.1480 | [0.1461, 0.1500] | 0.0165 |
| direct ML GBR | 0.0298 | [0.0279, 0.0323] | -0.0005 |
| primary ML ratio, shape only | 0.0442 | [0.0411, 0.0479] | 0.0062 |
| P07b ratio with explicit ceiling | 0.0393 | [0.0364, 0.0428] | 0.0034 |

## Boundary control: 6500-7500 ADC
The boundary control has 3714 B2 pulses. The primary question is
whether the correction preserves charge-shape and CFD20 timing before using it
above `7000 ADC`.

| method | q_template shift | 95% CI | CFD20 shift ns | tail delta |
|---|---:|---:|---:|---:|
| traditional template family | 0.0000 | [0.0000, 0.0000] | 0.000 | 0.0000 |
| primary ML ratio, shape only | -0.0832 | [-0.0847, -0.0810] | 0.426 | -0.0046 |
| P07b ratio with explicit ceiling | -0.0909 | [-0.0938, -0.0867] | 0.465 | -0.0057 |

## Application above 7000 ADC
For `A>=7000 ADC` (5266 pulses), the primary shape-only ML
correction gives q_template shift
`-0.0867` with CI
[-0.0913, -0.0839];
the P07b explicit-ceiling variant gives
`-0.0897`.

## Leakage checks
Leakage flags: **1**. The audit includes exact upstream reproduction, run
overlap, absence of explicit ceiling/observed-amplitude features in the primary
ML model, shuffled-target and ceiling-only controls, and observed-amplitude
dependency inside the 6500-7500 boundary. See `leakage_checks.csv`.

## Conclusion
The direct artificial-clip ML remains a strong closure, but the natural
multi-ceiling transfer is not automatically safe. The primary shape-only ratio
model reduces explicit ceiling leakage risk, yet the 6500-7500 boundary control
is the adoption gate: use the above-7000 correction only with the boundary
q_template and CFD20 shifts carried as systematic uncertainties.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `p07_reproduction_table.csv`,
`artificial_clip_by_run.csv`, `boundary_application_by_run.csv`,
`observed_amp_dependency.csv`, `boundary_application_predictions_sample.csv`,
`leakage_checks.csv`, and three PNG diagnostics
are in this folder.
