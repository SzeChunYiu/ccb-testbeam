# Claim evidence matrix

This table is the wiki-facing traceability bridge from each claim-ledger row to frozen artifact evidence and curated reference anchors.
External references explain terminology or standard methods; only project artifacts and QA gates support project-specific claims.
Blocked claims intentionally keep empty evidence as `BLOCKED: no production artifact yet` so missing MV4-MV8/final-release evidence cannot be hidden.

| Claim | Status | Evidence artifacts | Reference anchors | Statement | Limitation |
|---|---:|---|---|---|---|
| `CLAIM-ARTIFACT-VALIDATION` | SUPPORTED | `VALIDATION.json`, `VALIDATION_SUMMARY.md` | `REF-VALIDATION-ARTIFACTS`, `REF-GEANT4-2003`, `REF-GEANT4-2006` | The selected run has internally consistent frozen MV1-MV3/MV9 artifacts. | Does not by itself prove full release readiness or complete detector-physics validation. |
| `CLAIM-MV1-SUMMARY` | SUPPORTED | `reports/mc_validation/summary/metrics_table.csv` | `REF-VALIDATION-ARTIFACTS`, `REF-PDG-RPP-2024` | MV1 has a frozen artifact-summary metric (hgb_auc=0.99719995921) for run 20260627T175952Z_afe8992_mv4_timing_retry. | Summary metric only; uncertainty/systematic and publication-grade figure requirements remain separate gates. |
| `CLAIM-MV2-SUMMARY` | SUPPORTED | `reports/mc_validation/summary/metrics_table.csv` | `REF-VALIDATION-ARTIFACTS`, `REF-GEANT4-2003`, `REF-PDG-RPP-2024` | MV2 has a frozen artifact-summary metric (proton_ekin_recon_res68=0.0153808233017) for run 20260627T175952Z_afe8992_mv4_timing_retry. | Summary metric only; uncertainty/systematic and publication-grade figure requirements remain separate gates. |
| `CLAIM-MV3-SUMMARY` | SUPPORTED | `reports/mc_validation/summary/metrics_table.csv` | `REF-VALIDATION-ARTIFACTS`, `REF-GEANT4-2003`, `REF-PDG-RPP-2024` | MV3 has a frozen artifact-summary metric (n_sample_I=6450) for run 20260627T175952Z_afe8992_mv4_timing_retry. | Summary metric only; uncertainty/systematic and publication-grade figure requirements remain separate gates. |
| `CLAIM-MV4-RELEASE` | BLOCKED | `BLOCKED: no production artifact yet` | `REF-FINAL-BIBLIOGRAPHY-AUDIT` | MV4 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| `CLAIM-MV5-RELEASE` | BLOCKED | `BLOCKED: no production artifact yet` | `REF-FINAL-BIBLIOGRAPHY-AUDIT` | MV5 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| `CLAIM-MV6-RELEASE` | BLOCKED | `BLOCKED: no production artifact yet` | `REF-FINAL-BIBLIOGRAPHY-AUDIT` | MV6 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| `CLAIM-MV7-RELEASE` | BLOCKED | `BLOCKED: no production artifact yet` | `REF-FINAL-BIBLIOGRAPHY-AUDIT` | MV7 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| `CLAIM-MV8-RELEASE` | BLOCKED | `BLOCKED: no production artifact yet` | `REF-FINAL-BIBLIOGRAPHY-AUDIT` | MV8 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| `CLAIM-FINAL-RELEASE` | BLOCKED | `QA_RELEASE_AUDIT.json`, `publication/PUBLICATION_MANIFEST.json` | `REF-RUNBOOK`, `REF-FINAL-BIBLIOGRAPHY-AUDIT` | The MC validation package is final-release ready. | Release requires every QA audit gate to pass; current blocked gates must remain visible. |
