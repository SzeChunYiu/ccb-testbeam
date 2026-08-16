# Immutable session record — legacy MV4 timing claim source audit

## Identity

- UTC stamp: `2026-07-24T180301Z`
- Task: `AUD-LEDGER-001`
- Unit: source/provenance audit of timing claims `CL-002` through `CL-009`
- Owner: scheduled scientific-review session
- Initial remote `main`: `fca51ba5f932846c8ab57bf9d60b03cf5e32983c`
- Destination: direct sequential commits to `main`
- Acceptance: audit/tooling/evidence `VALIDATED`; ledger remediation `PARTIAL`

## Start-of-run review

Authenticated GitHub reads inspected current `main`, recent history, open pull requests,
commit status, PR #868, mandatory coordination records, the canonical 43-field claim ledger,
its cumulative schema evidence, the exact legacy MV4 report and summary, the historical producer
at commit `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`, and the current fail-closed MV4 contract.
No force push, history rewrite, task branch, stale PR merge, or unrelated deletion was used.
PR #868 remained closed, unmerged, and non-mergeable.

## Exact source evidence

- ledger: 18,183 bytes; blob `58d70cdd7b90c256b2aa268c425de0e1dadbb3f6`;
  SHA-256 `cfdfc8b38e53158fee5cb32a61165d2fc8c2e2370d81580e5f75fe369963fbcb`;
- report: 2,342 bytes; SHA-256
  `004e1269ede4f60d43eaf1ef3d0087e4ebc9168a4ff09df2a7ae5199fd081bec`;
- summary: 1,204 bytes; SHA-256
  `29ea729663a29288af686a59a63ddd2bd4f22a6001e2591cb7a4994066173ea9`;
- current contract: 4,441 bytes; SHA-256
  `55608d6a3f72bf65877a2be81acb66db20ca4df9517b12e20b22dec57e01f4e1`.

## Confirmed findings

Seven timing rows have 37–39 rather than 43 columns. The cited report and summary do not
contain B6 `0.68/0.75 ns`, combined B4+B6+B8 `0.54/0.56 ns`, or B4-B6 covariance
`-0.127 ns²`. `CL-007` overstates a toy-digitizer pull as `VALIDATED/PASS`, despite a
hard-coded data anchor and assumed `0.10 ns` uncertainty. `CL-009` calls an analytic CFD20
plus `A+B/sqrt(amplitude)` source an ML verdict although no ML model is present. The former
`results.json` and `configs/mv4_timing.yaml` paths are absent.

Exact fixed source outputs are 80,000 tracks from 241,487 scanned events, raw sigma68
`1.744319343085384 ns`, corrected held-out sigma68 `1.7696154242198858 ns`, raw pull
`-1.054403396247793`, corrected pull `2.680528799917713`, gain `110 ADC/MeV`, and assumed
data uncertainty `0.10 ns`.

## Delivered files

- `tools/audit/audit_mv4_legacy_claim_rows.py`
- `tests/test_audit_mv4_legacy_claim_rows.py`
- `docs/validation/mv4_legacy_claim_rows_source_audit.md`
- `docs/validation/mv4_legacy_claim_rows_audit_validation.json`
- `docs/validation/mv4_legacy_claim_rows_audit.svg`
- updated `chatgpt_todo/ACTIVE_TASK.md`

Policy: `LEGACY_MV4_TIMING_REQUIRES_STRICT_INPUTS_AND_SOURCE_BOUND_CLAIMS`.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv4_legacy_claim_rows.py \
  tests/test_audit_mv4_legacy_claim_rows.py

PYTHONPATH=. python -m pytest tests/test_audit_mv4_legacy_claim_rows.py -q
4 passed in 0.03s
```

The direct audit returned status `FLAWED`, exit 1, and 14 findings on exact starting bytes.
Its JSON parsed, the SVG parsed as XML, and changed Python lines were at most 97 characters.
The failure is the validated scientific result of this audit; the gate was not weakened.

## Direct-main commits before archive

- `a6bcd6b73f6afeabfd7dbed28f41f84dbd46de8e` — audit tool
- `27078a39776ebfe10c56dcb9adffbba1c7e9f0de` — focused tests
- `48cb05fe9cb984e47bd394321d000ce972e9e2df` — machine-readable evidence
- `f1a652d9ed8b7c179558042538b4dc91c35d54f7` — visual evidence
- `e0a83ebe689d4704ef65b7301ef9a70f46684e05` — audit report
- `a407daee106836c71c7fa67909a36c86950a8584` — active-task update

The connector returned successful direct-main commit SHAs rather than conventional textual
`git push` stdout.

## Blockers and next action

A local checkout could not resolve `github.com`. The connector can replace complete files but
cannot apply a line patch. Replacing the 18 kB ledger or long shared coordination files from a
partial response would risk lost updates, so this run did not claim the remediation as delivered.
The next unit must reconstruct `CL-002` through `CL-009` to exactly 43 fields from a complete
current ledger snapshot, withhold unsupported per-stave/combined/covariance values, retain the
two pulls only as gated toy diagnostics, rename the false ML verdict to analytic `REVIEW`, rerun
this audit plus the cumulative schema validator, and commit the exact corrected ledger to `main`.

No ROOT processing, detector timing measurement, covariance matrix, timing calibration,
uncertainty closure, or detector-performance result was produced.
