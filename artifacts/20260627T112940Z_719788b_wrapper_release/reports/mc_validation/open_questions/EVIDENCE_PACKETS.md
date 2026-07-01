# Open-question evidence packets

- **All packets closed:** `False`
- **Packet count:** `7`
- **Open packet count:** `7`

| Question | Packet status | Closure action | Required artifacts | Execution hint | Implementation blocker |
|---|---:|---|---|---|---|
| OQ-MV4 | BLOCKED | produce_mv4_timing_artifact | `reports/mc_validation/artifact_reports/MV4_REPORT.html`<br>`reports/mc_validation/systematics/MV4_TIMING_UNCERTAINTIES.json`<br>`reports/mc_validation/leakage/MV4_TRUTH_BOUNDARY_AUDIT.json` | `CCB_RUN_ID=<run_id> sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch` | current SLURM wrapper runs MV0-MV3/MV9; MV4 packet cannot close until calibrated timing implementation writes MV4 production artifacts |
| OQ-MV5 | BLOCKED | produce_mv5_pileup_artifact | `reports/mc_validation/artifact_reports/MV5_REPORT.html`<br>`reports/mc_validation/pileup/MV5_MIXTURE_LINEAGE.json`<br>`reports/mc_validation/pileup/MV5_RECOVERY_DIAGNOSTICS.json` | `CCB_RUN_ID=<run_id> sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch` | current SLURM wrapper runs MV0-MV3/MV9; MV5 packet cannot close until pile-up overlay/recovery implementation writes MV5 production artifacts |
| OQ-MV6 | BLOCKED | produce_mv6_representation_artifact | `reports/mc_validation/artifact_reports/MV6_REPORT.html`<br>`reports/mc_validation/representations/MV6_REPRESENTATION_COMPARISON.json`<br>`reports/mc_validation/leakage/MV6_NUISANCE_LEAKAGE_AUDIT.json` | `CCB_RUN_ID=<run_id> sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch` | current SLURM wrapper runs MV0-MV3/MV9; MV6 packet cannot close until representation-comparison implementation writes MV6 production artifacts |
| OQ-MV7 | BLOCKED | produce_mv7_pedestal_noise_artifact | `reports/mc_validation/artifact_reports/MV7_REPORT.html`<br>`reports/mc_validation/noise/MV7_PEDESTAL_NOISE_CLOSURE.json`<br>`reports/mc_validation/noise/MV7_CHANNEL_DIAGNOSTICS.json` | `CCB_RUN_ID=<run_id> sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch` | current SLURM wrapper runs MV0-MV3/MV9; MV7 packet cannot close until pedestal/noise closure implementation writes MV7 production artifacts |
| OQ-MV8 | BLOCKED | produce_mv8_saturation_artifact | `reports/mc_validation/artifact_reports/MV8_REPORT.html`<br>`reports/mc_validation/saturation/MV8_DYNAMIC_RANGE_SCAN.json`<br>`reports/mc_validation/saturation/MV8_FAILURE_ACCOUNTING.json` | `CCB_RUN_ID=<run_id> sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch` | current SLURM wrapper runs MV0-MV3/MV9; MV8 packet cannot close until saturation/dynamic-range implementation writes MV8 production artifacts |
| OQ-SYS | BLOCKED | submit_systematic_arrays | `reports/mc_validation/systematics/SYSTEMATIC_ARRAY_MANIFEST.json`<br>`reports/mc_validation/systematics/BOOTSTRAP_INTERVALS.json`<br>`reports/mc_validation/systematics/UNCERTAINTY_DECOMPOSITION.json` | `CCB_RUN_ID=<run_id> sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch` | systematic packet cannot close until MV4-MV8 production artifacts exist and paired systematic arrays are submitted through SLURM |
| OQ-WIKI | BLOCKED | publish_final_wiki | `wiki/WIKI_MANIFEST.json`<br>`reports/mc_validation/references/REFERENCE_REGISTRY.json`<br>`publication/PUBLICATION_MANIFEST.json`<br>`QA_RELEASE_AUDIT.json` | `python scripts/mc_validation/run_pipeline.py --run-id <run_id> release && python scripts/mc_validation/run_pipeline.py --run-id <run_id> qa` | wiki packet cannot close until QA release audit is PASS and bibliography/figures are publication-ready |

## Closure rule

These packets are templates for recursive study closure. A packet remaining `BLOCKED` is not a failure of generation; it means the production evidence has not yet been produced and checked.
