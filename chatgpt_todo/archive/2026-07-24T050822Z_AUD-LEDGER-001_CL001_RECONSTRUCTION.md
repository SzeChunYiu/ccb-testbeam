# Immutable handoff — AUD-LEDGER-001 CL-001 reconstruction

## Session

- UTC stamp: `2026-07-24T050822Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `1c982d65a0b742c3b6d4f78201cfed37fa3094c4`
- Task: `AUD-LEDGER-001`
- Owner: scheduled scientific-review session
- Destination: direct commits to `main`; no branch, pull request, force-push, or history rewrite
- Acceptance: `PARTIAL`; CL-001 is validated, 23 malformed rows remain

## Start-of-run review

Reviewed current main, recent history, repository permissions, open pull requests,
commit status, PR #868 state, mandatory `chatgpt_todo/` records, the strict claim-ledger
schema gate, the S00 configuration/report/script/count table/manifest/figure, source
commit history, and the global figure registry. A direct clone was attempted and failed
with `Could not resolve host: github.com`; authenticated GitHub reads and writes were
used. PR #868 remained closed and unmerged and was not modified.

## Confirmed defects

1. `CL-001` had 40 fields under a 43-column header, so late values were shifted.
2. The row cited nonexistent/stale paths `reports/s00_pulse_table/REPORT.md` and
   `data/pulse_table.parquet`.
3. `FIG-GL-001` cited nonexistent/stale `scripts/s00_selector.py`,
   `data/s00_counts.csv`, and `docs/figures/s00_gate.png`.
4. The canonical evidence chain instead uses:
   - `configs/s00_reproduction.yaml`;
   - `scripts/01_build_pulse_table_from_root.py`;
   - `reports/S00_data_integrity_pipeline_reproduction/REPORT.md`;
   - `reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv`;
   - `reports/S00_data_integrity_pipeline_reproduction/manifest.json`;
   - `reports/S00_data_integrity_pipeline_reproduction/fig_counts_by_group_stave.png`;
   - source commit `dcde28d37b9adee4f56ee0348d090006c53d2fa1`.

## Source-backed reconstruction

The corrected CL-001 row records:

- `current_value=640737 pulses`;
- `n_runs=33`;
- `n_data=640737 pulses`;
- exact fixed-input count uncertainties `0/0/0`, explicitly scoped in notes;
- `truth_type=data_count`;
- `status=VALIDATED`;
- canonical report/script/generated-data/config/manifest paths;
- `FIG-GL-001`, `TAB-GL-001`;
- full producing commit SHA;
- `ci_status=EXACT_COUNT_FIXED_INPUTS`.

The generated selected-pulse table remains intentionally untracked. This row does not
claim a population confidence interval or a new beam-data analysis.

## Measured validation

The S00 configuration, report, count table, manifest, and figure registry were
reconstructed from authenticated repository bytes. The validator checked:

- configured count `640737`;
- claim count and `n_data` `640737`;
- 33 unique configured runs;
- count-table report/reproduced values `640737/640737`;
- delta `0`, tolerance `0`, pass `True`;
- manifest `count_match_passed=true`;
- report source-commit prefix `dcde28d`;
- tracked source and figure paths.

Commands:

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
```

JSON and SVG parsing passed. Maximum changed Python line lengths were 96 and 95
characters. Ruff, full repository pytest, ROOT processing, simulation, and GitHub
Actions were not run; no broad CI success is claimed.

## Cumulative ledger state

- header fields: 43
- data rows: 26
- exact rows: 3 (`CL-001`, `CL-007`, `CL-011`)
- malformed rows: 23
- cumulative schema status: `FLAWED` (required fail-closed state)

Late-field interpretation remains withheld for every malformed row.

## Direct-main commit sequence before archive

1. `b301216f014df325b3a211e21c1e8720206dd6b4` — reconstruct CL-001
2. `561f40945c35583216dcd8c6d0c307a5da4ef5d3` — repair FIG-GL-001 provenance
3. `6aa5d3f80cf223127a32c2e6b6343808f307d7bb` — add source-chain validator
4. `0493463a62e6a70ca3bf0bbd944467795cac3da7` — add focused tests
5. `40191cb2b813fafbd02e01998b11a7e51a4a9b1d` — normalize evidence paths
6. `be1803f4f42b77af3e4e4b7810496fbf96688e7d` — add validation JSON
7. `a51a9f9468ab32a4b8aa88600f8193f22bc7e8d1` — add accessible SVG
8. `1d97c0636cc004ea5d2bd4b38c1d2ba51ca978b7` — add audit report
9. `47c22f4bd19ff581179958963f76e03b2fd9eceb` — refresh schema JSON
10. `97cfadf8ee9303821e48d66e7f35e99e0321805d` — update schema audit
11. `5f90a64a29facf473fc1ba6c4e88c741a333ff0f` — update width visualization
12. `c26239ad2074d1fa354515ec18b051c2149cbcfe` — style regression helpers
13. `b96d89f459f6662796a31224c472e841c23e9d0c` — update active task
14. `3a2032a3fddebf81f7dff6347f5e5c16ca6f3f92` — update backlog

## Remaining risks and next action

Reconstruct the next highest-impact malformed claim from its exact reports, scripts,
data/configuration, figures/tables, and history. Preserve unresolved fields explicitly.
Do not interpret current positional late fields. Completion requires 26/26 exact rows,
then WIKI, claim, internal-link, figure, and table checks.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file replacement
rather than a byte-safe append and the long append-only file was available only through
paged/truncated reads. Replacing reconstructed partial content would risk provenance
loss. This immutable record and the latest `HANDOFF.md` preserve the complete run.
