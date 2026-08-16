# AUD-LEDGER-001 — Claim-ledger schema gate

## Session identity

- UTC stamp: `2026-07-24T042917Z`
- Owner: scheduled scientific-review session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial observed remote `main`: `6a0268b46cc7c848096019ea466b73901df1605b`
- Latest concurrent base before this session's first write: `ef5a2167934f414e7cf064c210ddd22bb401ce20`
- Direct destination: `main`
- Task: `AUD-LEDGER-001`
- Acceptance after this unit: `PARTIAL`; the fail-closed validator and evidence are validated, but 24 malformed rows remain unreconstructed.

## Start-of-run review and concurrency

- Confirmed repository admin/push permission and default branch `main`.
- Inspected recent history, open pull requests, PR #868, `docs/claim_ledger.csv`, the completed WIKI front-door work, and mandatory `chatgpt_todo/` records.
- PR #868 remains closed, unmerged, and non-mergeable. It was not modified.
- Did not duplicate `AUD-REPO-001`, which remains owned by another active session.
- Concurrent WIKI-remediation commits advanced `main` during this session. They were preserved; this session's later commits were based on the then-current remote head.
- A direct clone was attempted but failed with `Could not resolve host: github.com`. Exact content was reconstructed from authenticated GitHub reads; direct-main connector commits were used.
- No force-push, branch rewrite, unrelated rollback, raw-data change, or destructive source edit was used.

## Exact repository evidence

### Canonical ledger snapshot

- Path: `docs/claim_ledger.csv`
- Git blob SHA-1: `0c7ea56d00ed44bd976e4ba8e05a84cb4c6eb63e`
- Bytes: `8971`
- SHA-256: `3ef63ee3836ce67c8b9f4538f754737cdcf53bc67d9a746210a0ea9e81e41d2d`
- Header width: `43`
- Data rows: `26`
- Exact local Git-blob reconstruction matched the authenticated GitHub blob before validation.

### Measured row-width state

- Exact-width rows: `2/26` — `CL-007`, `CL-011`
- Width-mismatched rows: `24/26`
- Width histogram:
  - 35 columns: 1 row
  - 36 columns: 4 rows
  - 37 columns: 7 rows
  - 38 columns: 8 rows
  - 39 columns: 3 rows
  - 40 columns: 1 row
  - 43 columns: 2 rows

### Demonstrated field-shift risk

On the exact bytes, ordinary positional `csv.DictReader` interpretation produces repository-unsupported mappings, including:

- `CL-001`: `status = data/pulse_table.parquet`; `ci_status = Exact reproduction count`.
- `CL-002`: `truth_type` becomes the results JSON path, `status` becomes the config path, and `source_report = FIG-TIM-001`.
- `CL-026`: `source_report = NOT_APPLICABLE_WITH_REASON`.

These are parser artifacts caused by missing fields/commas, not valid claim semantics. A short row is not assumed to contain only trailing empty fields. Status, truth type, sources, figures, CI state, blockers, supersession, commit, and notes are withheld for all malformed rows pending source-backed reconstruction.

## Added implementation

### `tools/audit/validate_claim_ledger_schema.py` v1.0.0

Policy:

`NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`

The validator:

- reads exact bytes once and records byte count and SHA-256;
- requires the exact canonical 43-field header;
- parses strict UTF-8 and strict CSV syntax;
- checks row width before mapping fields;
- checks missing and duplicate claim IDs;
- records row number, claim ID, width, missing/excess fields, schema state, and field-interpretation state;
- sets `field_interpretation=WITHHELD` for every malformed row;
- writes deterministic JSON and accessible SVG evidence;
- returns 0 for `VALIDATED`, 1 for measured flaws, and 2 for controlled input/schema/UTF-8 failure.

Remote Git blob SHA-1 after publication: `1961e63756b734db30a4a9a8037a756c291afe25`.

### Regression coverage

Added `tests/test_validate_claim_ledger_schema.py` with coverage for:

- exact 43-column rows;
- short rows;
- an explicit missing-middle-field positional shift;
- duplicate claim IDs;
- noncanonical headers;
- malformed CSV;
- machine-readable CLI flaw output;
- accessible SVG output;
- invalid UTF-8 and status 2.

Remote Git blob SHA-1: `74e19fa9842f89a81910acf7121e587e727398df`.

## Validation commands and results

Executed on exact local copies of the committed implementation/test:

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_schema.py \
  tests/test_validate_claim_ledger_schema.py

python -m pytest tests/test_validate_claim_ledger_schema.py -q

9 passed in 0.04s
```

Exact repository audit:

```text
python tools/audit/validate_claim_ledger_schema.py \
  docs/claim_ledger.csv \
  --output docs/validation/claim_ledger_schema_validation.json \
  --svg docs/validation/claim_ledger_schema.svg
```

Measured result:

```text
process status: 1
status: FLAWED
data rows: 26
exact-width rows: 2
width-mismatched rows: 24
```

The nonzero status is the required fail-closed outcome for the current malformed ledger, not a failed validator implementation.

Additional passed checks:

- validation JSON parsed successfully;
- SVG parsed as XML;
- source and test `py_compile` passed;
- maximum validator line length: 91 characters;
- maximum test line length: 90 characters;
- remote validator, test, and SVG Git blobs match the locally validated files.

Not run:

- full repository pytest;
- ruff;
- broken-link checker;
- ROOT/data processing;
- simulation;
- GitHub Actions.

No broader CI success is claimed.

## Evidence artifacts

Added:

- `docs/validation/claim_ledger_schema_audit.md`
- `docs/validation/claim_ledger_schema_validation.json`
- `docs/validation/claim_ledger_schema.svg`

The SVG shows all 26 claim IDs, actual widths, expected width 43, text/hatching distinctions, and the non-physics boundary. Remote SVG Git blob SHA-1: `7df5d9cef2b43601c498148970ddf87acdc29193`.

## Direct-to-main commit sequence before archive

- `dc2941513d643f2fe91828106e3f65a72dfff366` — `docs(audit): activate claim-ledger schema gate`
- `4ca689f788f76d51a768ea2272f8a1c36367f442` — `feat(audit): validate claim-ledger row alignment`
- `dd45b4274773d5d6f4c03e2d50202aa413a42cbe` — `test(audit): cover claim-ledger schema gate`
- `5138378935d651fa435523684a2d199c1f8c65db` — `docs(validation): record claim-ledger schema audit`
- `c798351d5d75a737621d705e1ea39acc3f244b55` — `docs(validation): add claim-ledger schema record`
- `02102fae6897170c3b37aa1485c67ba0819e1101` — `docs(validation): visualize claim-ledger width defects`
- `9df04ab62e3c8eaa84db22a7e9a779feb3621efc` — `docs(validation): clarify claim-ledger artifact hashes`
- `b170ea7d74e24ef0b6a2bf4e5732038187443125` — `docs(audit): advance claim-ledger schema task`
- `9a76e9c0061e106ba26210b39fa58609e00c72e2` — `docs(audit): register claim-ledger schema visualization`

Concurrent WIKI handoff commit `658d058d721912fc7746b354c01c90ee8964df11` was incorporated and preserved between this session's evidence and coordination commits.

All writes returned successful authenticated direct-main commit responses. A local `git push` transcript is unavailable because the checkout network path was unavailable. Subsequent remote-main reads are the delivery evidence.

## Coordination updates

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`

The existing stable records `IDX-LEDGER-001`, `CRM-LEDGER-001`, `ST-LEDGER-001`, `CL-LEDGER-001`, and `BLK-LEDGER-001` remain the canonical cross-links. This archive supplies the exact implementation and evidence produced in this unit.

`SESSION_LOG.md` was not replaced. The connector exposes whole-file replacement rather than a byte-safe append primitive, and the append-only file is 282 lines with concurrent `main` activity. Reconstructing and replacing it through partial ranged responses would create an avoidable lost-update/provenance-loss risk. This immutable archive and the latest handoff preserve the complete session record; the missing append remains explicit.

## Scientific boundary and next action

No claim value, timing result, pile-up rate, calibration, confidence interval, detector-performance metric, raw data, or simulation was recalculated. This is a repository schema/provenance result.

`AUD-LEDGER-001` remains `PARTIAL`; `BLK-LEDGER-001` remains open. Completion requires source-backed reconstruction of all 24 malformed rows to exactly 43 fields, preservation of every intended nonempty value and caveat, 26/26 exact-width validation, and rerunning downstream claim/WIKI/link/figure checks. No late field from a malformed row should authorize a scientific claim before that remediation.
