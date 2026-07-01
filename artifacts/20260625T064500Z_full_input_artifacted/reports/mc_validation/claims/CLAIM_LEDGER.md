# MC validation claim ledger

- **Run ID:** `20260625T064500Z_full_input_artifacted`
- **Release claims allowed:** `False`
- **Blocked claim count:** `6`

| Claim | Status | Statement | Limitations |
|---|---:|---|---|
| CLAIM-ARTIFACT-VALIDATION | SUPPORTED | The selected run has internally consistent frozen MV1-MV3/MV9 artifacts. | Does not by itself prove full release readiness or complete detector-physics validation. |
| CLAIM-MV1-SUMMARY | SUPPORTED | MV1 has a frozen artifact-summary metric (hgb_auc=0.997641986278) for run 20260625T064500Z_full_input_artifacted. | Summary metric only; uncertainty/systematic and publication-grade figure requirements remain separate gates. |
| CLAIM-MV2-SUMMARY | SUPPORTED | MV2 has a frozen artifact-summary metric (proton_ekin_recon_res68=0.0365311094732) for run 20260625T064500Z_full_input_artifacted. | Summary metric only; uncertainty/systematic and publication-grade figure requirements remain separate gates. |
| CLAIM-MV3-SUMMARY | SUPPORTED | MV3 has a frozen artifact-summary metric (n_sample_I=64762) for run 20260625T064500Z_full_input_artifacted. | Summary metric only; uncertainty/systematic and publication-grade figure requirements remain separate gates. |
| CLAIM-MV4-RELEASE | BLOCKED | MV4 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| CLAIM-MV5-RELEASE | BLOCKED | MV5 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| CLAIM-MV6-RELEASE | BLOCKED | MV6 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| CLAIM-MV7-RELEASE | BLOCKED | MV7 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| CLAIM-MV8-RELEASE | BLOCKED | MV8 production validation is complete. | Blocked pending calibrated digitized MC/systematic production artifacts. |
| CLAIM-FINAL-RELEASE | BLOCKED | The MC validation package is final-release ready. | Release requires every QA audit gate to pass; current blocked gates must remain visible. |
