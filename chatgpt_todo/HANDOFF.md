# Latest Scientific Review Handoff

## Session

- UTC stamp: `2026-07-24T061758Z`
- Task: `AUD-LEDGER-001`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `72fccaa8f4d6c00665c60fd0a94884c87cdd544b`
- Main after validated work/archive: `5113230b9d065f3a672f0b72e85fadcf311124e2`
- Remote confirmation before this handoff update: recent-main search returned `292f5ad6e55438e155dec756b9bf257a723a3524` at head; the subsequent archive write succeeded as `5113230b9d065f3a672f0b72e85fadcf311124e2`.
- Destination: direct sequential commits to `main`; no task branch, pull request, force-push, or history rewrite
- Acceptance: `AUD-LEDGER-001 = PARTIAL`; `CL-010` is blocked, `CL-012` is superseded, and 21 malformed ledger rows remain

## Start-of-run and concurrency review

Reviewed repository permissions/default branch, recent main history, open PRs, PR #868, commit status/workflow state, mandatory `chatgpt_todo/` records, claim and figure registries, WIKI, MV5 report/summary/script, academic pile-up chapter, source commit, and tracked MV5 figure. The initial head was the concurrent SiPM campaign merge `72fccaa8f4d6c00665c60fd0a94884c87cdd544b`; it was preserved. A direct clone failed because the runtime could not resolve `github.com`, so authenticated GitHub connector reads/writes were used. PR #868 remains closed, unmerged, and non-mergeable and was not modified.

No status checks or pull-request workflow runs were attached to the initial head. No CI success is inferred.

## Confirmed source conflict

1. `CL-010` had 37 fields and `CL-012` had 36 fields under the canonical 43-column header, so their late fields were not safely interpretable.
2. The tracked MV5 summary records `tau_eff_new_ns=124.8` and `duty=0.38`. Its headline is exactly:

```text
(1 / 124.8 ns) × 0.38 = 3.0448717948717947 MHz
```

`0.38` is named as the beam duty factor in source and summary; the reviewed repository evidence does not establish it as an occupancy-quality threshold.
3. The academic chapter instead uses `mu_max=0.1`, derives `0.801 MHz` per stave and `3.20 MHz` for four staves, then calls `3.05 MHz` a rounding. `3.05` is not a rounding of `3.20`.
4. The MV5 JSON records `rmax_from_failure_ceiling_mhz=null`. The maximum simulated recovery failure fraction is `0.03475`, below the recorded ceiling `0.17`; no recovery crossing or lower bound at `3.044 MHz` was demonstrated.
5. `FIG-PU-003` cited nonexistent `results.json` and `docs/figures/rmax_comparison.png` paths instead of the tracked `mv5_pileup_summary.json` and `mv5_pileup.png` artifacts.

## Source-backed correction

- `CL-010` is now exactly 43 fields, `status=BLOCKED`, `truth_type=derived_model_conflicted`, `allowed_status_validated=NO`, current value blank, `ci_status=NOT_APPLICABLE_WITH_REASON`, and `blocked_by=S-STAT-003`.
- `CL-012` is now exactly 43 fields, `status=SUPERSEDED`, current value blank, `ci_status=SUPERSEDED_DO_NOT_USE`, and retained only as correction history.
- Both rows cite the tracked MV5 report, script, summary JSON, source commit `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`, and `FIG-PU-003`.
- `FIG-PU-003` now points to `reports/mv5_pileup_1782678353/mv5_pileup_summary.json` and `reports/mv5_pileup_1782678353/mv5_pileup.png`, with explicit non-acceptance language.

No accepted Rmax value or uncertainty remains in the canonical claim ledger.

## Validation delivered

Added:

- `tools/audit/validate_claim_ledger_cl010.py` v1.0.0;
- `tests/test_validate_claim_ledger_cl010.py`;
- `docs/validation/claim_ledger_cl010_audit.md`;
- `docs/validation/claim_ledger_cl010_validation.json`;
- `docs/validation/claim_ledger_cl010.svg`.

The validator requires exact 43-field quarantine rows, checks source paths and producing commit, independently recomputes the duty-scaled reciprocal, verifies the null recovery crossing and failure ceiling, identifies the chapter's incompatible derivation, and validates repaired figure provenance. It returns 0 for `VALIDATED`, 1 for measured inconsistencies, and 2 for controlled input/schema/UTF-8 errors.

Commands and results:

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_cl010.py \
  tests/test_validate_claim_ledger_cl010.py

PYTHONPATH=. python -m pytest tests/test_validate_claim_ledger_cl010.py -q

6 passed in 0.04s
```

The source-faithful fixture validator returned `VALIDATED` with zero issues. JSON and SVG parsing passed. Maximum changed Python line length was 92 characters. The tests cover corrected quarantine, attempted re-promotion to `VALIDATED`, attempted insertion of a canonical value, a future recovery-crossing change, stale figure paths, and controlled invalid UTF-8.

The exact proposed ledger bytes were parsed independently:

- file size: `10097` bytes;
- SHA-256: `809e03162f04f94235fe36612c0ec8a3ccf4ae054a5d87341bdd5e26ad3c57d6`;
- data rows: 26;
- exact-width rows: 5 (`CL-001`, `CL-007`, `CL-010`, `CL-011`, `CL-012`);
- width-mismatched rows: 21;
- schema status: `FLAWED` by required fail-closed policy.

Ruff, full repository pytest, ROOT processing, simulation execution, the WIKI validator, broken-link checker, and GitHub Actions were not run. Repository facts were inspected through authenticated GitHub blob reads; no real data or simulation output was regenerated.

## Direct-main commits

1. `d9aeff21544f84fc01485510d5ac2476c251966a` — `fix(ledger): quarantine conflicted Rmax claims`
2. `6b45cfd2b6fcf8ac4c60bd401549bab7d1ea6008` — `fix(ledger): repair Rmax figure provenance`
3. `44e4d7fcf9cb65c2e20e142c4b2eaad3a2bcc84f` — `feat(audit): validate conflicted Rmax claim quarantine`
4. `be637cbca0a3d879eab12b7f7c808bf2aeac6e45` — `test(audit): cover conflicted Rmax ledger gate`
5. `21c4fdd483d8484453c7b72c159f7166d81e2c2c` — `docs(validation): record Rmax claim quarantine`
6. `97168267bd7f4319f1912dd5d882b819230407d1` — `docs(validation): add Rmax quarantine record`
7. `509df1f3d02356e755d4d7c8fc7e6a1a98498891` — `docs(validation): visualize Rmax claim conflict`
8. `6e965555933720717e8ee1223fd21260a2809989` — `docs(validation): advance ledger width audit to five rows`
9. `0bc21206270cd25d7947ffbd41b9636f0ba02904` — `docs(validation): refresh five-row ledger schema record`
10. `f9ce6c9eb3a02e90e1f1826b7ffe9304a93303cb` — `docs(validation): refresh ledger width visualization`
11. `292f5ad6e55438e155dec756b9bf257a723a3524` — `docs(audit): advance ledger reconstruction through Rmax claims`
12. `5113230b9d065f3a672f0b72e85fadcf311124e2` — `docs(audit): archive Rmax ledger quarantine`

Every connector write returned a successful direct-main commit. A final recent-main search must confirm this handoff commit and its ancestors on remote `main`; the user-facing completion reports that final SHA.

## Files changed

- `docs/claim_ledger.csv`
- `docs/figure_registry.csv`
- `tools/audit/validate_claim_ledger_cl010.py`
- `tests/test_validate_claim_ledger_cl010.py`
- `docs/validation/claim_ledger_cl010_audit.md`
- `docs/validation/claim_ledger_cl010_validation.json`
- `docs/validation/claim_ledger_cl010.svg`
- `docs/validation/claim_ledger_schema_audit.md`
- `docs/validation/claim_ledger_schema_validation.json`
- `docs/validation/claim_ledger_schema.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`
- `chatgpt_todo/archive/2026-07-24T061758Z_AUD-LEDGER-001_RMAX_QUARANTINE.md`

## Scientific boundary and next task

No beam-rate measurement, tau_eff result, pile-up recovery result, confidence interval, simulation result, calibration, or detector-performance result was recalculated. This run corrects claim status, provenance, and schema and prevents an internally conflicted rate definition from remaining canonically accepted.

`AUD-LEDGER-001` remains `PARTIAL`. Resolve `S-STAT-003` by preregistering the rate measurand, per-stave/total normalization, occupancy criterion, beam-duty treatment, uncertainty budget, falsifiers, and independent validation strategy. Then synchronize the complete WIKI and academic chapter and continue source-backed reconstruction of the remaining 21 malformed ledger rows. Do not restore `3.044`, `3.05`, or `3.20 MHz` as an accepted Rmax without that evidence.

`SESSION_LOG.md` was not replaced because the connector provides whole-file replacement rather than a byte-safe append and the long append-only file was only available through paged/truncated reads. Replacing reconstructed partial bytes would risk destroying prior provenance. The complete run is preserved in the immutable archive and this handoff; this limitation is explicit rather than fabricating a log append.
