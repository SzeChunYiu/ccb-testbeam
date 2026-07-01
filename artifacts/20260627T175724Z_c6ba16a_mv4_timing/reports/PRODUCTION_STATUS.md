# MC Validation Production Status

- **Run ID:** `20260627T175724Z_c6ba16a_mv4_timing`
- **Git SHA:** `c6ba16abc60bc32d763468c99f7f17e0604f5ada`
- **Profile:** `production`
- **Status:** **BLOCKED**
- **Reason:** validation gates not satisfied
- **Production claims allowed:** `False`

## Resume command

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260627T175724Z_c6ba16a_mv4_timing --profile production submit --studies all
```

## Heavy-compute policy

Production GEANT4, full ROOT scans, digitization, ML training, systematic/bootstrap arrays, and full-data notebooks must run only via LUNARC sbatch on compute nodes.

## Blockers

- None recorded.

## Smoke/fixture evidence

- No smoke gate recorded for this run.

## LUNARC job registry

- No production SLURM jobs submitted for this run.
