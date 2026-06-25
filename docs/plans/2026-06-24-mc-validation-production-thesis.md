# MC Validation Production Thesis Completion Implementation Plan

**For Codex:** REQUIRED SUB-SKILL: Use executing-plans implement plan task-by-task.
**Goal:** Make the existing `ccb_mc_validation` implementation fail closed for production and prepare a resumable LUNARC-only production path.
**Architecture:** Keep one canonical orchestrator at `scripts/mc_validation/run_pipeline.py` backed by `src/ccb_mc_validation/execution/pipeline.py`. Local execution is restricted to audit, unit tests, explicit fixture/smoke checks, and blocker recording; production work is submitted through SLURM and never inferred from fixture artifacts.
**Tech Stack:** Python, pytest, existing `ccb_mc_validation` package, SLURM via `sbatch --parsable`, JSON/Markdown run registries.

---

## Completed local-safe tasks

1. Wrote read-only preflight evidence under `artifacts/preflight/20260624T202239Z/`.
2. Repaired MV0 digitizer waveform semantics so pedestal/noise/quantization are applied once per channel waveform after analog summing.
3. Replaced incomplete orchestrator surface with canonical commands: `init`, `inventory`, `preflight`, `plan`, `test`, `fixture`, `smoke`, `submit`, `watch`, `status`, `collect`, `validate`, `qa`, `plot`, `notebooks`, `docs`, `thesis`, `release`, `resume`, and `all`.
4. Added fail-closed production behavior: missing MC inputs or missing active LUNARC socket create structured blockers, not production results.
5. Added CLI guard: MV1/MV2/MV3 synthetic execution requires explicit `--fixture`; production commands require real inputs and `SLURM_JOB_ID`.
6. Added regression tests for digitizer pedestal-once behavior and orchestration blockers.

## Blocked production tasks

Production execution remains blocked until both are true:

- Active `ssh lunarc` control socket is available.
- Required production inputs are present at the resolved configured paths or the config is updated to real LUNARC/shared paths.

Resume command after those blockers are cleared:

```bash
python scripts/mc_validation/run_pipeline.py --run-id <RUN_ID> --profile production submit --studies all
```
