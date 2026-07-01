# Study implementation gap audit

- **All study implementations ready:** `False`
- **Blocked count:** `5`

| Study | Status | Module | Current state | Required next artifact |
|---|---:|---|---|---|
| MV4 | BLOCKED | `ccb_mc_validation.studies.mv4_timing` | timing study placeholder / requires MV0 digitizer readiness and production timing artifacts | `reports/mc_validation/systematics/MV4_TIMING_UNCERTAINTIES.json` |
| MV5 | BLOCKED | `ccb_mc_validation.studies.mv5_pileup` | pile-up overlay skeleton / requires controlled mixture lineage and recovery diagnostics | `reports/mc_validation/pileup/MV5_RECOVERY_DIAGNOSTICS.json` |
| MV6 | BLOCKED | `ccb_mc_validation.studies.mv6_representation` | representation comparison skeleton / requires nuisance-leakage-safe waveform comparison | `reports/mc_validation/representations/MV6_REPRESENTATION_COMPARISON.json` |
| MV7 | BLOCKED | `ccb_mc_validation.studies.mv7_pedestal` | pedestal/noise closure skeleton / requires held-out channel diagnostics | `reports/mc_validation/noise/MV7_PEDESTAL_NOISE_CLOSURE.json` |
| MV8 | BLOCKED | `ccb_mc_validation.studies.mv8_saturation` | saturation/dynamic-range skeleton / requires failure accounting and dynamic-range scan | `reports/mc_validation/saturation/MV8_DYNAMIC_RANGE_SCAN.json` |

## Guardrail

This audit is a readiness map, not physics evidence. A study can move from `BLOCKED` to `READY` only when its production implementation writes the required artifacts and release QA/claim-ledger gates are updated.
