# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T180301Z`
- **Task:** `AUD-LEDGER-001`
- **Unit:** exact-source audit of legacy MV4 timing claims `CL-002` through `CL-009`
- **Initial remote `main`:** `fca51ba5f932846c8ab57bf9d60b03cf5e32983c`
- **Validated audit/evidence head before this handoff:** `73e63f9cb7cf4537dbf9efa4c7d7ba7904624fed`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** audit, tests, and evidence are `VALIDATED`; claim-ledger remediation remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent history, open pull requests, commit
status, PR #868, the mandatory `chatgpt_todo/` records, the canonical claim ledger and cumulative
schema evidence, the exact legacy MV4 report and summary, the historical producer at commit
`3c5ff5cf587c8ca9cefda20cb220ba29effd2170`, and the current fail-closed MV4 contract.

The run based its writes on remote head `fca51ba5f932846c8ab57bf9d60b03cf5e32983c` and used
direct contents-API commits to `main`. No force push, history rewrite, task branch, stale PR merge,
or unrelated deletion was used. PR #868 remains closed, unmerged, and non-mergeable and was not
modified. No status checks were attached to the starting head.

## Confirmed defects

The canonical ledger header has 43 fields, but the remaining legacy timing rows have:

| Claim | Columns | Former claim |
|---|---:|---|
| CL-002 | 38 | B6 sigma68 0.68 ns |
| CL-003 | 39 | B6 upper bound 0.75 ns |
| CL-004 | 38 | B4+B6+B8 sigma68 0.54 ns |
| CL-005 | 38 | combined upper bound 0.56 ns |
| CL-006 | 39 | B4-B6 covariance -0.127 ns² |
| CL-008 | 37 | corrected pull +2.68 sigma |
| CL-009 | 37 | ML timing verdict |

The cited report and `mv4_summary.json` do not contain the five B6/combined/covariance values.
They contain only global toy-digitizer raw and corrected timing outputs. The former ledger paths
`results.json` and `configs/mv4_timing.yaml` are absent.

`CL-007` is already 43 fields but overclaims its raw pull as `VALIDATED/PASS`. The pull uses a
hard-coded data anchor and an assumed `0.10 ns` data uncertainty. `CL-009` calls the source an ML
verdict, but the historical producer tests CFD20 plus an analytic `A+B/sqrt(amplitude)`
correction and contains no ML model.

## Exact source evidence

Starting ledger:

- Git blob `58d70cdd7b90c256b2aa268c425de0e1dadbb3f6`;
- 18,183 bytes;
- SHA-256 `cfdfc8b38e53158fee5cb32a61165d2fc8c2e2370d81580e5f75fe369963fbcb`;
- cumulative width state `19/26` exact and `7/26` malformed.

Legacy report:

- path `reports/mv4_timing_1782678162/REPORT.md`;
- 2,342 bytes;
- SHA-256 `004e1269ede4f60d43eaf1ef3d0087e4ebc9168a4ff09df2a7ae5199fd081bec`.

Legacy summary:

- path `reports/mv4_timing_1782678162/mv4_summary.json`;
- 1,204 bytes;
- SHA-256 `29ea729663a29288af686a59a63ddd2bd4f22a6001e2591cb7a4994066173ea9`.

Exact fixed source outputs:

| Quantity | Value |
|---|---:|
| tracks | 80000 |
| scanned events | 241487 |
| gain | 110 ADC/MeV |
| raw sigma68 | 1.744319343085384 ns |
| raw i.i.d. track-bootstrap SE | 0.006755405549476786 ns |
| corrected held-out sigma68 | 1.7696154242198858 ns |
| corrected i.i.d. track-bootstrap SE | 0.010813166729502352 ns |
| raw pull | -1.054403396247793 |
| corrected pull | 2.680528799917713 |
| assumed data uncertainty | 0.10 ns |

The train/application split is row-index parity. The run does not bind calibration bytes,
data-anchor result bytes, configuration, manifest, run inventory, or detector-response
systematics. The current `scripts/MV4_TIMING_README.md` explicitly labels the path
`TOY_DIAGNOSTIC` and requires current calibration and measured anchors under `--strict`, with
run/block validation.

## Delivered audit and evidence

Added:

- `tools/audit/audit_mv4_legacy_claim_rows.py`;
- `tests/test_audit_mv4_legacy_claim_rows.py`;
- `docs/validation/mv4_legacy_claim_rows_source_audit.md`;
- `docs/validation/mv4_legacy_claim_rows_audit_validation.json`;
- `docs/validation/mv4_legacy_claim_rows_audit.svg`;
- `chatgpt_todo/archive/2026-07-24T180301Z_AUD-LEDGER-001_MV4_TIMING_SOURCE_AUDIT.md`.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

Policy:

`LEGACY_MV4_TIMING_REQUIRES_STRICT_INPUTS_AND_SOURCE_BOUND_CLAIMS`

The visual is explicitly labelled software/provenance evidence, not detector data.

## Validation

Executed locally against exact repository-byte reconstructions:

```text
python -m py_compile \
  tools/audit/audit_mv4_legacy_claim_rows.py \
  tests/test_audit_mv4_legacy_claim_rows.py

PYTHONPATH=. python -m pytest tests/test_audit_mv4_legacy_claim_rows.py -q
4 passed in 0.03s

PYTHONPATH=. python tools/audit/audit_mv4_legacy_claim_rows.py \
  --ledger docs/claim_ledger.csv \
  --report reports/mv4_timing_1782678162/REPORT.md \
  --summary reports/mv4_timing_1782678162/mv4_summary.json \
  --contract scripts/MV4_TIMING_README.md \
  --output-json docs/validation/mv4_legacy_claim_rows_audit_validation.json
exit status 1; status FLAWED; findings 14
```

The nonzero result is the validated outcome of the source audit. The gate was not weakened.
The JSON parsed, the SVG parsed as XML, and changed Python lines were at most 97 characters.
Full repository pytest, ruff, ROOT processing, and GitHub Actions were not run.

## Direct-main commit sequence

- `a6bcd6b73f6afeabfd7dbed28f41f84dbd46de8e` — `feat(audit): detect unsupported legacy MV4 timing claims`
- `27078a39776ebfe10c56dcb9adffbba1c7e9f0de` — `test(audit): cover legacy MV4 claim-source failures`
- `48cb05fe9cb984e47bd394321d000ce972e9e2df` — `docs(validation): record legacy MV4 timing claim flaws`
- `f1a652d9ed8b7c179558042538b4dc91c35d54f7` — `docs(validation): visualize legacy MV4 claim gaps`
- `e0a83ebe689d4704ef65b7301ef9a70f46684e05` — `docs(validation): audit legacy MV4 timing claim sources`
- `a407daee106836c71c7fa67909a36c86950a8584` — `docs(audit): activate legacy MV4 claim-source audit`
- `73e63f9cb7cf4537dbf9efa4c7d7ba7904624fed` — `docs(audit): archive legacy MV4 timing source audit`

The authenticated contents API returned successful direct-main commit SHAs rather than
conventional textual `git push` output. A post-write history read must confirm that remote `main`
contains the handoff commit and all listed progress commits.

## Blocker and exact next action

The ledger replacement is not claimed as delivered. A local checkout could not resolve
`github.com`; the connector exposes complete-file replacement rather than a line patch. Replacing
the 18 kB ledger or long shared coordination files from partial responses would risk erasing
concurrent provenance.

The next unit must use a complete current ledger snapshot to reconstruct `CL-002` through
`CL-009` to exactly 43 fields, withhold the five unsupported values under
`BLK-MV4-LEGACY-001`, retain the two pulls only as non-authorizing toy diagnostics, replace the
false ML label with analytic `REVIEW`, rerun this audit and the cumulative schema validator,
refresh the schema Markdown/JSON/SVG, and commit the exact corrected ledger directly to `main`.

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and other long shared matrices
were not replaced from partial/ranged reads. The complete session is preserved in the immutable
archive, this handoff, the active task, and the validation artifacts.

## Scientific boundary

No ROOT processing, detector timing measurement, B6 or combined-stave resolution, covariance
matrix, timing calibration, uncertainty closure, or detector-performance result was produced.
The five unsupported values remain unverified, and the recorded pulls remain legacy
toy-digitizer diagnostics rather than empirical timing validation.
