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
python scripts/mc_validation/run_pipeline.py --run-id 20260627T180424Z_2516606_mv4_timing_final release
python scripts/mc_validation/run_pipeline.py --run-id 20260627T180424Z_2516606_mv4_timing_final qa
```

## References

Reference registry status: `PASS`, final bibliography status: `BLOCKED`.

| ID | Status | Citation |
|---|---:|---|
| REF-RUNBOOK | AVAILABLE | Project runbook supplied in repository session; governs execution, reporting, thesis, release requirements. |
| REF-VALIDATION-ARTIFACTS | AVAILABLE | Run 20260625T064500Z_full_input_artifacted, SLURM job 3316536, frozen validation artifacts under configured LUNARC artifact root. |
| REF-GEANT4-2003 | AVAILABLE | S. Agostinelli et al., Nuclear Instruments and Methods in Physics Research A 506 (2003) 250-303, doi:10.1016/S0168-9002(03)01368-8. |
| REF-GEANT4-2006 | AVAILABLE | J. Allison et al., IEEE Transactions on Nuclear Science 53 (2006) 270-278, doi:10.1109/TNS.2006.869826. |
| REF-PDG-RPP-2024 | AVAILABLE | S. Navas et al. (Particle Data Group), Physical Review D 110 (2024) 030001, doi:10.1103/PhysRevD.110.030001. |
| REF-BIRKS-1964 | AVAILABLE | J. B. Birks, The Theory and Practice of Scintillation Counting, Pergamon/Macmillan, 1964. |
| REF-KNOLL-2010 | AVAILABLE | G. F. Knoll, Radiation Detection and Measurement, 4th ed., Wiley, 2010, ISBN 978-0-470-13148-0. |
| REF-ROOT-1997 | AVAILABLE | R. Brun and F. Rademakers, Nuclear Instruments and Methods in Physics Research A 389 (1997) 81-86, doi:10.1016/S0168-9002(97)00048-X. |
| REF-FINAL-BIBLIOGRAPHY-AUDIT | BLOCKED | Blocked until every thesis/wiki claim maps to either a frozen project artifact, a curated internal note, or an external literature reference. |

Formal literature/citation entries still need final curation before publication-grade release. This draft intentionally leaves citation completion as a release blocker rather than inventing references.
