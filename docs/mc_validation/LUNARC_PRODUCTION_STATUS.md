# LUNARC MC Validation Production Status

Generated: 2026-06-28

## Completed MC validation jobs

All six MC validation studies have been executed and completed on LUNARC.

| Study | SLURM job ID | Status | Partition | Account |
|-------|-------------|--------|-----------|---------|
| MV0 (digitizer gain) | 3328635 | COMPLETED | lu48 | lu2026-2-51 |
| MV1 (PID AUC) | 3328635 | COMPLETED | lu48 | lu2026-2-51 |
| MV2 (range–energy) | 3328635 | COMPLETED | lu48 | lu2026-2-51 |
| MV3 v3 (stopping depth) | 3328648 | COMPLETED | lu48 | lu2026-2-51 |
| MV4 (timing σ₆₈) | 3328641 | COMPLETED | lu48 | lu2026-2-51 |
| MV5 (pile-up R_max) | 3328643 | COMPLETED | lu48 | lu2026-2-51 |
| MV6 (anomaly species) | 3328644 | COMPLETED | lu48 | lu2026-2-51 |

Note: MV0, MV1, and MV2 ran in the same SLURM job (3328635) as a combined Tier-1 batch.
MV3 v3 is the corrected rerun (geometry diagnostics); earlier v1/v2 runs are superseded.

## Key inputs (verified by LUNARC preflight)

- MC ROOT: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root`
  - size: `677221620` bytes
  - sha256: `2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc`
- Pulse table: `reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz`
  - size: `9246625` bytes
  - sha256: `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f`

## Result locations

Results are stored under the canonical project root:

```
/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/
  reports/
    mc_validation/
      mv0_digitizer/study_result.json
      mv1_pid/study_result.json
      mv2_energy/study_result.json
      mv3_stopping_depth/study_result.json   ← v3 (supersedes v1/v2)
      mv4_timing/study_result.json
      mv5_pileup/study_result.json
      mv6_anomaly/study_result.json
```

## Study outcomes summary (2026-06-28)

| Study | Outcome | Action required |
|-------|---------|----------------|
| MV0 | PASS (v2 method: 92 ± 28 ADC/MeV) | None — CLOSED |
| MV1 | PASS (AUC = 0.986) | None — CLOSED |
| MV2 | PASS | None — CLOSED |
| MV3 | STRUCTURAL FAIL (χ²/ndf = 68,269) | New GEANT4 run with corrected upstream material budget |
| MV4 | PASS (raw σ₆₈ pull = −1.05); TENSION (corrected pull = +2.68; timewalk B unphysical) | New digitizer model needed for corrected path |
| MV5 | PASS (R_max 3.044 MHz vs data 3.05 MHz) | None — CLOSED |
| MV6 | DONE (C12 55% dominant, frac = 0.32%) | None — CLOSED |

## Next LUNARC production targets

1. **MV3 geometry fix**: update GEANT4 macro to include upstream material budget
   (CD₂ target, beam-pipe window, air gap, SciBar upstream layers), then resubmit.
2. **MV4 digitizer rewrite**: implement template-pulse convolution with CFD threshold;
   rerun timing study to resolve timewalk B-coefficient sign.

No further LUNARC jobs are scheduled until these geometry and digitizer fixes are merged.
