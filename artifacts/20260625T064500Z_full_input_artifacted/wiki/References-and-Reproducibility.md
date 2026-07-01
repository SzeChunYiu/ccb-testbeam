# References and reproducibility

## Artifact paths

- Validation summary: `VALIDATION_SUMMARY.md`
- Claim ledger: `reports/mc_validation/claims/CLAIM_LEDGER.md`
- Publication index: `publication/index.html`
- Thesis draft: `reports/mc_validation/thesis_draft/THESIS_DRAFT.md`
- Reference registry: `reports/mc_validation/references/REFERENCE_REGISTRY.md`
- Notation registry: `reports/mc_validation/notation/NOTATION_REGISTRY.md`

## Reproduction command

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

## References

Reference registry status: `PASS`, final bibliography status: `BLOCKED`.

| ID | Status | Citation |
|---|---:|---|
| REF-RUNBOOK | AVAILABLE | Project runbook supplied with this repository session; governs execution, reporting, thesis, and release requirements. |
| REF-VALIDATION-ARTIFACTS | AVAILABLE | Run 20260625T064500Z_full_input_artifacted, job 3316536, frozen validation artifacts under the configured LUNARC artifact root. |
| REF-FINAL-LITERATURE-CURATION | BLOCKED | To be curated before final publication-grade wiki/thesis release. |

Formal literature/citation entries still need final curation before publication-grade release. This draft intentionally leaves citation completion as a release blocker rather than inventing references.
