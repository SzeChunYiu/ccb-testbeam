# AUD-LEDGER-002 — MV3 tracked-summary provenance contradiction

## Session

- UTC stamp: `2026-07-24T200310Z`
- Owner: scheduled scientific-review session
- Initial remote main: `ad5a19a2dece0f0973573362004d558eb1a4cad5`
- Task status: `PARTIAL`
- Policy: `TRACKED_MV3_SUMMARY_OVERRIDES_ROUNDED_REPORT_PROSE`

## Start-of-run review

Authenticated GitHub reads inspected current `main`, recent commits, repository metadata,
PR #868, `chatgpt_todo/ACTIVE_TASK.md`, `HANDOFF.md`, root WIKI MV3/GAP-01 prose,
the canonical ledger, the legacy MV3 report and summary, and the existing MV3 ledger
validator/tests. A direct clone was attempted and failed because the runtime could not
resolve `github.com`; no repository access was fabricated.

PR #868 is closed, unmerged, and non-mergeable. It was not modified.

## Confirmed defect

Canonical rows `CL-019`, `CL-020`, and `CL-021`, plus
`validate_mv3_legacy_claim_rows.py` v1.0, assert that the legacy report omits exact
per-stave counts, exact B8 numerators, underlying chi-square components, and a
machine-readable result.

The tracked `mv3_summary.json` contradicts that narrative. It contains:

- MC counts B2/B4/B6/B8 = 117213/45507/31145/55619;
- data counts B2/B4/B6/B8 = 268576/19284/11834/7051;
- denominators 249484 and 306745;
- Pearson chi-square 204808.2179684494;
- ndf 3;
- chi-square/ndf 68269.40598948313.

Independent reconstruction using `expected_i = 306745 * mc_fraction_i` reproduces the
stored chi-square and ratio exactly in binary64 arithmetic.

The source supports exact provenance, but not accepted detector closure. Geometry,
trigger/selection transfer, gain response, covariance, and detector/model systematics
remain unresolved. `CL-021` should remain `FLAWED` for those reasons.

## Work delivered

Added:

- `tools/audit/audit_mv3_summary_provenance.py`;
- `tests/test_audit_mv3_summary_provenance.py`;
- `docs/validation/mv3_summary_provenance_audit.md`;
- `docs/validation/mv3_summary_provenance_validation.json`;
- `docs/validation/mv3_summary_provenance.svg`.

Updated `chatgpt_todo/ACTIVE_TASK.md`.

The auditor returns status 1 for the current ledger and status 0 for a corrected
fixture. It checks exact count sums, fraction/count identities, Pearson reconstruction,
ledger numerators/denominators, source-data binding, method/status fields, and required
scientific caveats. Invalid UTF-8 returns controlled status 2.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv3_summary_provenance.py \
  tests/test_audit_mv3_summary_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_mv3_summary_provenance.py -q

5 passed in 0.70s
```

Current-like audit: `FLAWED`, 32 explicit findings.
Corrected fixture: `VALIDATED`, zero findings.
Changed Python lines: maximum 100 characters.
Validation JSON and SVG XML parsed successfully.

## Direct-main commits before archive

- `4005bb56a495baf89ef3e6bc8432e439e82ba2fb` — auditor
- `c42ba214c8925ff3d5e37d473e2e8a0208a2a107` — focused tests
- `fab453452c724f6dcd505f5a61153ffa97e8d277` — validation JSON
- `01faaf199551ab1f5ea644122ebc6b101f21eda1` — audit report
- `e6f313f211fe005187e50d864ad05bd3719a1706` — visual evidence
- `f7035417386d74d742a9ba9e2a940ce495042e09` — active-task update

The contents API returned commit SHAs rather than conventional `git push` stdout.

## Required next correction

1. Replace the incorrect CL-019/020/021 rows with exact summary-bound values and
   counts while retaining non-authorizing states.
2. Replace the old validator contract that rejects exact numerators and denies the
   tracked summary.
3. Synchronize WIKI GAP-01 and related public prose to describe an exact but flawed
   Pearson diagnostic rather than a non-reconstructable geometry-only proof.
4. Run both old/new MV3 focused suites and the WIKI claim validators together.

## Scientific boundary and coordination limitation

No ROOT input, GEANT4 rerun, geometry correction, calibration, p-value, confidence
interval, or systematic covariance model was produced. Accepted stopping-depth closure
remains blocked under `BLK-MV3-LEGACY-001`.

`SESSION_LOG.md`, `BACKLOG.md`, and `BLOCKERS.md` were not replaced because the
connector provides whole-file replacement and current long-file reads are paged or
truncated; replacing a partial reconstruction could destroy unrelated append-only
provenance. This immutable archive and the latest handoff retain the full run.
