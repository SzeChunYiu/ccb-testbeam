# Active Task

- **Task ID:** AUD-LEDGER-001 / CL-002 through CL-009 legacy MV4 timing source-audit unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T180301Z
- **Initial remote main SHA:** `fca51ba5f932846c8ab57bf9d60b03cf5e32983c`
- **Scope completed in this unit:** audited the seven remaining malformed timing rows plus the already exact-width raw-pull row against the exact tracked MV4 report, machine-readable summary, historical producer, and current fail-closed execution contract; added an executable auditor, focused tests, machine-readable evidence, and an accessible SVG.
- **Confirmed defects:** `CL-002`, `CL-003`, `CL-004`, `CL-005`, `CL-006`, `CL-008`, and `CL-009` have 37–39 columns rather than 43; the cited sources do not contain the B6 0.68/0.75 ns, combined-stave 0.54/0.56 ns, or covariance -0.127 ns² claims; `CL-007` overstates a toy pull as `VALIDATED/PASS`; `CL-009` calls an analytic CFD/timewalk source an ML verdict.
- **Source-backed fixed outputs:** 80000 tracks from 241487 scanned events; raw sigma68 `1.744319343085384 ns`, corrected held-out sigma68 `1.7696154242198858 ns`, raw pull `-1.054403396247793`, corrected pull `2.680528799917713`, gain `110 ADC/MeV`, and assumed data uncertainty `0.10 ns`.
- **Implemented files:** `tools/audit/audit_mv4_legacy_claim_rows.py`; `tests/test_audit_mv4_legacy_claim_rows.py`; `docs/validation/mv4_legacy_claim_rows_source_audit.md`; `docs/validation/mv4_legacy_claim_rows_audit_validation.json`; `docs/validation/mv4_legacy_claim_rows_audit.svg`.
- **Validation:** changed Python files compiled; focused suite returned `4 passed in 0.03s`; direct audit returned status `FLAWED` and exit 1 with 14 source/schema findings; JSON and SVG parsed; changed Python lines are at most 97 characters.
- **Evidence policy:** `LEGACY_MV4_TIMING_REQUIRES_STRICT_INPUTS_AND_SOURCE_BOUND_CLAIMS`.
- **Scientific boundary:** no ROOT processing, detector timing measurement, B6/combined-stave estimate, covariance reconstruction, calibration, or detector-performance closure was produced. This unit validates the audit and exact remediation contract, not the legacy numerical claims.
- **Remaining work:** reconstruct `CL-002` through `CL-009` to exactly 43 fields; withhold unsupported per-stave/combined/covariance values; retain pulls only as gated toy diagnostics; replace the false ML label with analytic `REVIEW`; refresh cumulative schema evidence and aggregate coordination records.
- **Status:** PARTIAL. The audit/evidence unit is VALIDATED; `docs/claim_ledger.csv` remains FLAWED until the source-backed row replacement is committed.
