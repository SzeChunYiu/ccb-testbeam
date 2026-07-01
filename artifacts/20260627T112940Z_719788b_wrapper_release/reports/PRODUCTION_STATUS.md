# MC Validation Production Status

- **Run ID:** `20260627T112940Z_719788b_wrapper_release`
- **Git SHA:** `719788b2974ba414410c2aaecd19777c4441dd08`
- **Profile:** `production`
- **Status:** **BLOCKED**
- **Reason:** missing required release audit: /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260627T112940Z_719788b_wrapper_release/QA_RELEASE_AUDIT.json
- **Production claims allowed:** `False`

## Resume command

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260627T112940Z_719788b_wrapper_release --profile production submit --studies all
```

## Heavy-compute policy

Production GEANT4, full ROOT scans, digitization, ML training, systematic/bootstrap arrays, and full-data notebooks must run only via LUNARC sbatch on compute nodes.

## Blockers

- None recorded.

## Smoke/fixture evidence

- No smoke gate recorded for this run.

## LUNARC job registry

- No production SLURM jobs submitted for this run.
