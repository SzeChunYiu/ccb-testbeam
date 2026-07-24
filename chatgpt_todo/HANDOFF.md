# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T200310Z`
- **Task:** `AUD-LEDGER-002`
- **Unit:** MV3 tracked-summary provenance contradiction and correction gate
- **Initial remote `main`:** `ad5a19a2dece0f0973573362004d558eb1a4cad5`
- **Validated delivery commit:** `0962878bdeb0568d4d62f11eccb9991b27b18750`
- **Remote `main` confirmation:** recent-history read showed `0962878bdeb0568d4d62f11eccb9991b27b18750` as the remote head containing the complete focused delivery
- **Destination:** direct sequential commits to `main`
- **Acceptance:** defect, independent reconstruction, fail-closed auditor, tests, and evidence are `VALIDATED`; canonical ledger/public-prose remediation remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected repository metadata, recent `main` history, root WIKI
MV3/GAP-01 prose, the canonical claim ledger, the legacy MV3 report and tracked summary,
the current MV3 ledger validator/tests, mandatory coordination files, and PR #868.
A direct clone was attempted and failed because this runtime could not resolve
`github.com`; repository access and commands were not fabricated.

The observed initial head remained stable while the focused files were added. Every
write used the current default branch through the authenticated contents API. No force
push, branch rewrite, task branch, PR transport, or unrelated deletion was used.
PR #868 is closed, unmerged, and non-mergeable and was not modified.

## Confirmed source contradiction

Canonical rows `CL-019`, `CL-020`, and `CL-021`, and
`tools/audit/validate_mv3_legacy_claim_rows.py` v1.0, assert that the legacy MV3 source
omits exact per-stave counts, exact B8 numerators, underlying chi-square components, and
a machine-readable result.

The tracked file
`reports/mv3_stopping_v3_1782679272/mv3_summary.json` contains:

- thresholded-MC B2/B4/B6/B8 counts `117213/45507/31145/55619`;
- selected-data B2/B4/B6/B8 counts `268576/19284/11834/7051`;
- denominators `249484` MC tracks and `306745` data events;
- Pearson chi-square `204808.2179684494`;
- ndf `3`;
- chi-square/ndf `68269.40598948313`.

The report itself prints only rounded fractions and rounded
`χ²/ndf = 68269.4`, but the tracked summary preserves the exact machine-readable
components. Therefore the current absence narrative is false.

## Independent calculation

The auditor reconstructs the profile statistic from exact tracked counts and fractions:

```text
expected_i = 306745 * mc_fraction_i
chi2 = sum((data_count_i - expected_i)^2 / expected_i)
ndf = 4 - 1 = 3
```

Result:

```text
chi2 = 204808.2179684494
chi2/ndf = 68269.40598948313
```

The reconstructed values exactly match the stored summary values in binary64
arithmetic.

This establishes reconstructability, not accepted detector closure. Geometry,
trigger/selection transfer, gain response, covariance, and detector/model systematics
remain unresolved. `CL-021` should remain `FLAWED`, but for those scientific reasons
rather than absent source data.

## Work delivered

Added:

- `tools/audit/audit_mv3_summary_provenance.py`;
- `tests/test_audit_mv3_summary_provenance.py`;
- `docs/validation/mv3_summary_provenance_audit.md`;
- `docs/validation/mv3_summary_provenance_validation.json`;
- `docs/validation/mv3_summary_provenance.svg`;
- `chatgpt_todo/archive/2026-07-24T200310Z_AUD-LEDGER-002_MV3_SUMMARY_PROVENANCE.md`.

Updated `chatgpt_todo/ACTIVE_TASK.md` and this handoff.

The SVG is explicitly labelled software/documentation validation, not detector data.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv3_summary_provenance.py \
  tests/test_audit_mv3_summary_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_mv3_summary_provenance.py -q

5 passed in 0.70s
```

The current-like exact row fixture returns `FLAWED` with 32 explicit findings. A
corrected fixture returns `VALIDATED` with zero findings. Mutated summary chi-square and
fraction values fail closed. Invalid UTF-8 returns controlled status 2. Validation JSON
and SVG XML parsing passed. Changed Python lines are no longer than 100 characters.

Validated file hashes:

- auditor: 10,658 bytes; SHA-256
  `2549a29913c6384c19addfb7cfe93ae4a0d2417499aa6f5cbf5fd9495c394753`;
- test: 5,955 bytes; SHA-256
  `6a9db439b6a7cc07bdc188646763fadcd8563a9878c61aa974fa10e2bc775b77`.

Remote source blobs recorded in the validation JSON:

- claim ledger: `bb552aa5ed70e7d81dcda888c5aa61402c01e03c`;
- legacy report: `b72eed4f7eb3237040a1346d7253080c098c8986`;
- tracked summary: `2bb4b34e499642dfdf8ceb13e2f6351ff6e5cc6d`;
- old validator: `aad4d1cb9fbbd81ec6e20cbca5250ef06c9f2d8a`.

## Direct-main commit sequence

- `4005bb56a495baf89ef3e6bc8432e439e82ba2fb` — auditor
- `c42ba214c8925ff3d5e37d473e2e8a0208a2a107` — focused tests
- `fab453452c724f6dcd505f5a61153ffa97e8d277` — validation JSON
- `01faaf199551ab1f5ea644122ebc6b101f21eda1` — audit report
- `e6f313f211fe005187e50d864ad05bd3719a1706` — visual evidence
- `f7035417386d74d742a9ba9e2a940ce495042e09` — active-task update
- `87be921069218f293e771539b84f5ba5be13b5e6` — immutable archive
- `0962878bdeb0568d4d62f11eccb9991b27b18750` — complete delivery handoff

The contents API returned successful commit SHAs instead of conventional textual
`git push` stdout. Post-write recent history confirmed the complete delivery on remote
`main`; this metadata update records that confirmation.

## Required next correction

1. Update `CL-019` with exact B8 `55619/249484`, exact fraction
   `0.22293614019335908`, and the tracked summary path.
2. Update `CL-020` with exact B8 `7051/306745`, exact fraction
   `0.02298651974767315`, and the tracked summary path.
3. Update `CL-021` with exact chi-square/ndf `68269.40598948313`, the Pearson
   construction, and the tracked summary path; retain `FLAWED` and the blocker.
4. Replace the old validator contract that rejects exact numerators and denies the
   tracked summary.
5. Synchronize WIKI GAP-01 and related public prose to describe an exact but flawed
   legacy Pearson diagnostic rather than a non-reconstructable geometry-only proof.
6. Run both MV3 focused suites and WIKI claim validators together before closing the
   task.

## Coordination limitation

`ACTIVE_TASK.md`, the immutable archive, validation artifacts, and this handoff contain
the complete session. `SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and the aggregate
matrices were not replaced because this connector offers whole-file replacement while
current long-file reads are paged or truncated. Replacing a partial reconstruction
could erase unrelated append-only provenance. No claim is made that those aggregate
files contain this run.

## Scientific boundary

No raw ROOT input, GEANT4 rerun, geometry correction, threshold-transfer validation,
gain calibration, p-value, confidence interval, covariance model, or detector/model
systematic propagation was produced. Accepted stopping-depth closure remains blocked
under `BLK-MV3-LEGACY-001`. Full repository pytest, ruff, ROOT processing, real-data/MC
regeneration, and broad GitHub Actions were not run; no such success is claimed.
