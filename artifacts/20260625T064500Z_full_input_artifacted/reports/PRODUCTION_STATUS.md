# MC Validation Production Status

- **Run ID:** `20260625T064500Z_full_input_artifacted`
- **Git SHA:** `7bd0a16c3a34adf9a6f9d0d6440cf7f4c66df1ca`
- **Profile:** `production`
- **Status:** **BLOCKED**
- **Reason:** validation gates not satisfied
- **Production claims allowed:** `False`

## Resume command

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted --profile production submit --studies all
```

## Heavy-compute policy

Production GEANT4, full ROOT scans, digitization, ML training, systematic/bootstrap arrays, and full-data notebooks must run only via LUNARC sbatch on compute nodes.

## Blockers

- None recorded.

## Smoke/fixture evidence

- No smoke gate recorded for this run.

## LUNARC job registry

- No production SLURM jobs submitted for this run.
