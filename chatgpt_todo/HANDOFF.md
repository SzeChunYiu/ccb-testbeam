# Latest Scientific Review Handoff

## Session

- UTC stamp: `2026-07-24T050822Z`
- Task: `AUD-LEDGER-001`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `1c982d65a0b742c3b6d4f78201cfed37fa3094c4`
- Validated work/archive head: `089d02f622c86c8350ce9f7ab40df61e57c23aa3`
- Remote confirmation: recent-main search returned `089d02f622c86c8350ce9f7ab40df61e57c23aa3` as the current head before this handoff update.
- Destination: direct commits to `main`; no task branch, pull request, force-push, or history rewrite
- Acceptance: `AUD-LEDGER-001 = PARTIAL`; `CL-001` is validated, 23 malformed ledger rows remain

## Start-of-run and concurrency review

Reviewed repository permissions/default branch, recent main history, open PRs, commit
status, PR #868 state, all mandatory coordination records, the strict ledger-schema
gate, and the complete S00 evidence chain. A direct clone failed with `Could not
resolve host: github.com`; authenticated GitHub connector reads/writes were used.

Concurrent commit `a0e498852a3275f8bdfe2b5aeb50fb4860c24dd9` landed during the run. It was
preserved; no unrelated commit or working tree was overwritten. PR #868 remains closed,
unmerged, and non-mergeable and was not modified.

## Confirmed defects

1. `CL-001` contained 40 values under the canonical 43-column header, so ordinary
   positional parsing shifted late fields.
2. The row cited stale/nonexistent paths:
   - `reports/s00_pulse_table/REPORT.md`;
   - `data/pulse_table.parquet`.
3. `FIG-GL-001` cited stale/nonexistent paths:
   - `scripts/s00_selector.py`;
   - `data/s00_counts.csv`;
   - `docs/figures/s00_gate.png`.

## Source-backed correction

The row is now bound to:

- `configs/s00_reproduction.yaml`;
- `scripts/01_build_pulse_table_from_root.py`;
- `reports/S00_data_integrity_pipeline_reproduction/REPORT.md`;
- `reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv`;
- `reports/S00_data_integrity_pipeline_reproduction/manifest.json`;
- `reports/S00_data_integrity_pipeline_reproduction/fig_counts_by_group_stave.png`;
- source commit `dcde28d37b9adee4f56ee0348d090006c53d2fa1`.

The 43-field row records `640737 pulses`, 33 configured runs, `n_data=640737`,
`truth_type=data_count`, `status=VALIDATED`, exact source paths, full source commit,
`FIG-GL-001`, `TAB-GL-001`, and `ci_status=EXACT_COUNT_FIXED_INPUTS`.

The `0/0/0` uncertainty entries are scoped to exact deterministic count reproduction
for fixed repository-declared input files and algorithm. They are not a population
confidence interval. The generated selected-pulse CSV remains intentionally untracked.

## Validation delivered

Added:

- `tools/audit/validate_claim_ledger_cl001.py` v1.0.0;
- `tests/test_validate_claim_ledger_cl001.py`;
- `docs/validation/claim_ledger_cl001_audit.md`;
- `docs/validation/claim_ledger_cl001_validation.json`;
- `docs/validation/claim_ledger_cl001.svg`.

The validator checks the exact ledger/config/report/count-table/manifest/figure-registry
chain, count and run cardinality, count-table closure, report scope, commit linkage,
manifest contract, tracked source paths, and figure registry. It returns 0 for
`VALIDATED`, 1 for measured inconsistencies, and 2 for controlled input/schema errors.

Commands and results:

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_cl001.py \
  tests/test_validate_claim_ledger_cl001.py

PYTHONPATH=. python -m pytest tests/test_validate_claim_ledger_cl001.py -q

5 passed in 0.59s

PYTHONPATH=. python tools/audit/validate_claim_ledger_cl001.py \
  --output docs/validation/claim_ledger_cl001_validation.json \
  --svg docs/validation/claim_ledger_cl001.svg

status: VALIDATED
issues: 0
configured runs: 33
count: 640737
```

JSON and SVG parsing passed. Maximum changed Python line lengths were 96 and 95
characters. Ruff, full repository pytest, ROOT processing, simulation, and GitHub
Actions were not run; no broader CI success is claimed. No status checks were attached
to the initial head.

## Cumulative claim-ledger state

- canonical columns: 43
- data rows: 26
- exact rows: 3 (`CL-001`, `CL-007`, `CL-011`)
- width-mismatched rows: 23
- schema state: `FLAWED` by required fail-closed policy
- malformed-row late fields: `WITHHELD`

Cumulative schema Markdown/JSON/SVG evidence was refreshed to the 3/26 state.

## Direct-main commits

1. `b301216f014df325b3a211e21c1e8720206dd6b4` — `docs(ledger): reconstruct CL-001 from S00 evidence`
2. `561f40945c35583216dcd8c6d0c307a5da4ef5d3` — `docs(figures): repair FIG-GL-001 provenance`
3. `6aa5d3f80cf223127a32c2e6b6343808f307d7bb` — `feat(audit): validate CL-001 source chain`
4. `0493463a62e6a70ca3bf0bbd944467795cac3da7` — `test(audit): cover CL-001 source reconstruction`
5. `40191cb2b813fafbd02e01998b11a7e51a4a9b1d` — `fix(audit): normalize CL-001 evidence paths`
6. `be1803f4f42b77af3e4e4b7810496fbf96688e7d` — `docs(validation): add CL-001 reconstruction record`
7. `a51a9f9468ab32a4b8aa88600f8193f22bc7e8d1` — `docs(validation): visualize CL-001 source chain`
8. `1d97c0636cc004ea5d2bd4b38c1d2ba51ca978b7` — `docs(validation): record CL-001 reconstruction audit`
9. `47c22f4bd19ff581179958963f76e03b2fd9eceb` — `docs(validation): refresh claim-ledger schema record`
10. `97cfadf8ee9303821e48d66e7f35e99e0321805d` — `docs(validation): update cumulative ledger schema audit`
11. `5f90a64a29facf473fc1ba6c4e88c741a333ff0f` — `docs(validation): refresh ledger width visualization`
12. `c26239ad2074d1fa354515ec18b051c2149cbcfe` — `style(test): format CL-001 regression helpers`
13. `b96d89f459f6662796a31224c472e841c23e9d0c` — `docs(audit): advance ledger reconstruction to CL-001`
14. `3a2032a3fddebf81f7dff6347f5e5c16ca6f3f92` — `docs(audit): record CL-001 ledger progress`
15. `089d02f622c86c8350ce9f7ab40df61e57c23aa3` — `docs(audit): archive CL-001 ledger reconstruction`

Each write response reported a successful commit on `main`; the subsequent recent-main
search confirmed the archive commit at remote head before this handoff update.

## Files changed

- `docs/claim_ledger.csv`
- `docs/figure_registry.csv`
- `tools/audit/validate_claim_ledger_cl001.py`
- `tests/test_validate_claim_ledger_cl001.py`
- `docs/validation/claim_ledger_cl001_audit.md`
- `docs/validation/claim_ledger_cl001_validation.json`
- `docs/validation/claim_ledger_cl001.svg`
- `docs/validation/claim_ledger_schema_audit.md`
- `docs/validation/claim_ledger_schema_validation.json`
- `docs/validation/claim_ledger_schema.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/HANDOFF.md`
- `chatgpt_todo/archive/2026-07-24T050822Z_AUD-LEDGER-001_CL001_RECONSTRUCTION.md`

## Scientific boundary and next task

No raw ROOT file, generated pulse table, numerical count, uncertainty, figure,
calibration, simulation, or detector-performance result was regenerated. This run
corrected claim provenance and schema for one evidence-backed exact-count claim.

Next: reconstruct the highest-impact remaining malformed claim from exact source
reports/scripts/data/configuration/history. Do not infer field placement from current
positional CSV parsing. Completion requires 26/26 exact rows followed by WIKI, claim,
internal-link, figure, and table checks.

`SESSION_LOG.md` was not replaced because the connector provides whole-file replacement
rather than a byte-safe append and the long append-only file was only available through
paged/truncated reads. Replacing reconstructed partial bytes would risk destroying
prior provenance. The complete session is preserved in the immutable archive and this
handoff; this limitation remains explicit rather than fabricating a log append.
