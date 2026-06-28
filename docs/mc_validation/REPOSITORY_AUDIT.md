# MC Validation Repository Audit

Generated: 2026-06-28

## Environment

- Repository path: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam`
- Git branch: `main`
- Python env: `/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3`

## Package layout

- MC validation package present: `True`
- Base config present: `True` (`configs/mc_validation/base.yaml`)

## Key inputs

- MC ROOT (`geant4/data/output_krakow_1M.root`): present (677 MB, sha256 verified)
- Data pulse table (`reports/*/s00_selected_b_pulses.csv.gz`): present (9.2 MB, sha256 verified)

## MC validation program status (as of 2026-06-28)

All seven MV study entry points are implemented and have completed LUNARC runs.

### Tier-1 studies (SLURM job 3328635)

| Study | Implementation | LUNARC run | Status |
|-------|---------------|------------|--------|
| MV0 (digitizer gain) | `mc_validation/mv0_digitizer.py` | 3328635 | PASS |
| MV1 (PID AUC) | `mc_validation/mv1_pid.py` | 3328635 | PASS |
| MV2 (range–energy) | `mc_validation/mv2_energy.py` | 3328635 | PASS |

### Tier-2 studies

| Study | Implementation | SLURM job | Status |
|-------|---------------|-----------|--------|
| MV3 v3 (stopping depth) | `mc_validation/mv3_stopping.py` | 3328648 | STRUCTURAL FAIL (known geometry defect) |
| MV4 (timing σ₆₈) | `mc_validation/mv4_timing.py` | 3328641 | PASS (raw) / TENSION (corrected) |
| MV5 (pile-up R_max) | `mc_validation/mv5_pileup.py` | 3328643 | PASS |
| MV6 (anomaly species) | `mc_validation/mv6_anomaly.py` | 3328644 | DONE — CLOSED |

### Summary

Four of seven studies pass outright (MV0, MV1, MV2, MV5). One is done and closed (MV6).
One has a structural simulation failure requiring a new GEANT4 production run (MV3).
One has a partial pass with a known toy-digitizer defect in the corrected path (MV4).

Tier-2 is no longer blocked — all studies have run. The two remaining action items
(MV3 geometry fix, MV4 digitizer rewrite) are GEANT4/simulation tasks, not validation
infrastructure tasks.

## Outstanding repository gaps

- No unit/regression tests on the reconstruction pipeline.
- Raw data not mirrored to LUNARC with checksums (pulse tables present, ROOT file present
  but not independently checksummed via a mirroring workflow).
- MV3 geometry fix PR not yet opened.
- MV4 template-pulse digitizer not yet implemented.
