# CCB testbeam MC validation thesis draft

- **Run ID:** `20260625T064500Z_full_input_artifacted`
- **Generated:** `2026-06-25T15:57:23.477135+00:00`
- **Validation status:** `PASS`
- **Release audit:** `BLOCKED`, release_ready=`False`
- **Report scope:** `artifact-summary` with full_report_suite_status=`BLOCKED`
- **Notebook scope:** `artifact-summary` with full_notebook_suite_status=`BLOCKED`

## Abstract draft

This draft records the current frozen-artifact MC validation state for MV1-MV3 and MV9. It is a writing scaffold and provenance index, not a final scientific thesis conclusion.

## Artifact-backed chapters

1. Inputs, provenance, and execution status: see `VALIDATION_SUMMARY.md` and `QA_RELEASE_AUDIT.md`.
2. MV1 particle identification: see `reports/mc_validation/artifact_reports/MV1_REPORT.md`.
3. MV2 energy/range response: see `reports/mc_validation/artifact_reports/MV2_REPORT.md`.
4. MV3 stopping profile: see `reports/mc_validation/artifact_reports/MV3_REPORT.md`.
5. MV9 synthesis and global status: see `reports/mc_validation/artifact_reports/GLOBAL_REPORT.md`.

## Release blockers to resolve before final thesis

- `MV4_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV5_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV6_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV7_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV8_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `systematic_arrays`: required systematic/bootstrap arrays are not complete
- `full_figure_catalog`: required 300-entry figure catalog/contact sheets are not complete
- `clean_kernel_notebooks`: full-data notebooks have not been executed via LUNARC sbatch
- `thesis_pdf_html`: thesis/static site PDF/HTML package is not built
- `release_bundle`: final release bundle/signoff is not complete

## Reproduction

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted thesis
```

## Guardrail

This draft must not be cited as the final thesis/static-site/PDF release. It intentionally preserves blocker visibility.
