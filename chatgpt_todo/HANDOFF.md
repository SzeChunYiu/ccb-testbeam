# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T173757Z`
- **Task:** `AUD-LEDGER-001`
- **Unit:** source-backed reconstruction of legacy MV3 claims `CL-019`, `CL-020`, and `CL-021`
- **Initial remote `main`:** `1e44fd19a02c33377e727bd5d85be7a8aa96b587`
- **Validated implementation/evidence head before coordination:** `e2e99cf2981df30dfa25cd87d794f9d81149204f`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** this three-row reconstruction is `VALIDATED`; ledger-wide `AUD-LEDGER-001` remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent history, repository permissions, PR #868, the canonical ledger, cumulative schema evidence, mandatory coordination files, the exact legacy MV3 report, the current fail-closed MV3 implementation, and source history. The run incorporated the immediately preceding MV1 handoff at `1e44fd19...` and based all writes on current remote `main`. No force push, history rewrite, task branch, stale PR merge, or unrelated-file deletion was used.

PR #868 remains closed, unmerged, and non-mergeable and was not modified.

## Confirmed defects

The 43-column ledger contained:

- `CL-019`: 38 columns;
- `CL-020`: 38 columns;
- `CL-021`: 36 columns.

Their late truth, status, source, CI, blocker, supersession, and note fields were therefore withheld. The former rows also cited absent paths `scripts/mv3_stopping.py` and `reports/mv3_stopping_v3_1782679272/results.json`.

The tracked report contains only rounded three-decimal fractions and the combined label `chi2/ndf = 68269.4`. It does not contain exact per-stave counts, separate chi-square and ndf, a p-value, bin variances, covariance, or a machine-readable result.

## Exact source evidence

Legacy report:

- path `reports/mv3_stopping_v3_1782679272/REPORT.md`;
- Git blob `b72eed4f7eb3237040a1346d7253080c098c8986`;
- 2232 bytes;
- SHA-256 `a1027e168d1f0321a334c44f1a1d59176a17869b5239991709b861db7962fa0f`;
- introducing commit `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`.

Fixed report outputs:

| Quantity | Value |
|---|---:|
| MC tracks above threshold | 249484 |
| Data events | 306745 |
| MC B8 fraction | 0.223, rounded to 3 decimals |
| Data B8 fraction | 0.023, rounded to 3 decimals |
| Reported profile label | `chi2/ndf = 68269.4` |

The reported MC fraction is compatible with 249 distinct integer numerators, 55511–55759. The reported data fraction is compatible with 307 numerators, 6902–7208. Exact counts and exact binomial intervals cannot be recovered from the rounded table.

Current remediation:

- path `src/ccb_mc_validation/studies/mv3_stopping_depth.py`;
- Git blob `9b0dfeaa6e74401345bc78c7ab82b33d7868b665`;
- SHA-256 `6f5d206caed1b54d0b6e2d0a9ef558e8f0e298bcb2683ccedd6fe33ff8e7bc43`;
- requires explicit `sample_label` and per-layer hit/energy masks;
- blocks rather than synthesizing Sample I/II from parity or occupancy from `stop_layer >= layer`.

## Delivered correction

`CL-019` and `CL-020` now have exactly 43 fields, retain only the rounded fixed outputs, leave unsupported count/uncertainty fields empty, use `allowed_status_validated=NO`, and remain `GATED` under `BLK-MV3-LEGACY-001`.

`CL-021` now records the exact literal source label `68269.4` but is `FLAWED`, not a calibrated goodness-of-fit result. It explicitly states that chi-square, ndf, p-value, bin errors, and covariance are unavailable.

Corrected ledger:

- Git blob `58d70cdd7b90c256b2aa268c425de0e1dadbb3f6`;
- 18183 bytes;
- SHA-256 `cfdfc8b38e53158fee5cb32a61165d2fc8c2e2370d81580e5f75fe369963fbcb`.

Cumulative state:

- exact-width rows `19/26`;
- malformed and withheld rows `7/26`;
- width histogram `37:2, 38:3, 39:2, 43:19`;
- remaining malformed rows `CL-002`–`CL-006`, `CL-008`, and `CL-009`;
- global schema status remains intentionally `FLAWED` until all rows are reconstructed.

## Files and evidence

Added:

- `tools/audit/validate_mv3_legacy_claim_rows.py`;
- `tools/audit/render_mv3_legacy_claim_evidence.py`;
- `tests/test_validate_mv3_legacy_claim_rows.py`;
- `docs/validation/mv3_legacy_claim_rows_audit.md`;
- `docs/validation/mv3_legacy_claim_rows_validation.json`;
- `docs/validation/mv3_legacy_claim_rows.svg`;
- `chatgpt_todo/archive/2026-07-24T173757Z_AUD-LEDGER-001_MV3_CLAIMS.md`.

Updated:

- `docs/claim_ledger.csv`;
- `docs/validation/claim_ledger_schema_audit.md`;
- `docs/validation/claim_ledger_schema_validation.json`;
- `docs/validation/claim_ledger_schema.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

Policies:

- `LEGACY_MV3_PROFILE_REQUIRES_EXACT_COUNTS_AND_FAIL_CLOSED_RERUN`;
- `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

## Validation

```text
python -m py_compile \
  tools/audit/validate_mv3_legacy_claim_rows.py \
  tools/audit/render_mv3_legacy_claim_evidence.py \
  tests/test_validate_mv3_legacy_claim_rows.py

PYTHONPATH=. python -m pytest tests/test_validate_mv3_legacy_claim_rows.py -q
7 passed in 1.05s
```

The direct validator returned `VALIDATED` with zero issues. The regression suite covers the former width mismatch, fabricated exact numerator, modified profile value, modified report, controlled invalid UTF-8, and SVG parsing. Both validation JSON files parse; both SVGs parse as XML; no changed Python line exceeds 100 characters. Remote committed validator/renderer/test blobs equal the local validated Git blobs.

## Direct-main commit sequence

- `7f22ba7157dfa9272eed39e2048149121fffc99b` — `fix(ledger): reconstruct legacy MV3 profile claims`
- `d45f6c338998123b0f4efb5771d471eb3e9521b1` — `feat(audit): validate legacy MV3 claim rows`
- `4a80586ffdf437a9e602cf68913b73fdf4fabf4e` — `feat(audit): render legacy MV3 claim evidence`
- `982d436d6478880382f02b85ea78a792429b3ed2` — `test(audit): cover legacy MV3 claim governance`
- `a5595f428860dcd872bc5dc8f0f840394f48330f` — `docs(validation): audit legacy MV3 claim rows`
- `e02b4ffe441058a1b33c777f941fcfe17286dbfc` — `docs(validation): record legacy MV3 claim validation`
- `a88e427dfc6031c361f2c237fe131a2e3dc2261e` — `docs(validation): visualize legacy MV3 claim limits`
- `3e8058bff3417ff3d23b986003932a062a055832` — `docs(validation): update cumulative ledger schema record`
- `a822e5a7aa242677028cba9b8005f5504b9dd1a3` — `docs(validation): audit nineteen exact ledger rows`
- `e2e99cf2981df30dfa25cd87d794f9d81149204f` — `docs(validation): visualize nineteen exact ledger rows`
- `b3f9f576aeec607267d0bb576a6cfb98bdd2dc13` — `docs(audit): complete legacy MV3 claim-row unit`
- `3336d028bfa6b00ea1f20b7495f19a240ec3a324` — `docs(audit): archive legacy MV3 claim reconstruction`

The authenticated contents API returned successful direct-main commit SHAs rather than conventional textual `git push` output. A post-write history read is required after this handoff to confirm final remote head containment.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and the other large shared matrices were not replaced from partial/ranged reads. This connector exposes whole-file replacement rather than a byte-safe append/patch action; reconstructing a long concurrently edited file from incomplete output could erase unrelated provenance. The complete run is retained in the immutable archive, latest handoff, active task, canonical ledger, and validation artifacts. `BLK-MV3-LEGACY-001` is present in all three reconstructed canonical rows and its resolution contract is stated below.

## Blocker and next scientific action

`BLK-MV3-LEGACY-001` remains open. Resolution requires a clean current-code rerun with immutable input files and hashes, explicit Sample I/II labels, real per-layer masks, exact per-stave counts, documented threshold/gain/pulse-model transfer, a preregistered profile statistic with valid uncertainty/covariance treatment, and retained machine-readable results and plots. Do not infer an exact B8 count, binomial interval, p-value, material-budget error, or detector performance from the legacy rounded report.

## Scientific boundary

No ROOT, Geant4, beam-data, calibration, threshold scan, or stopping-depth analysis was rerun. No exact B8 counts, confidence intervals, valid chi-square statistic, p-value, data/MC closure, or detector-performance result is claimed. Full repository pytest, ruff, ROOT processing, and GitHub Actions were not run. PR #868 remains closed and unmerged.
