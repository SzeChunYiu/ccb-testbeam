# AUD-DELTAE-008 — DeltaE event-table output integrity

## Session

- Stamp: `2026-07-26T052912Z`
- Owner: scheduled scientific-review session
- Initial remote main: `ed3633055695184bd5ef68ab90bb6951e81d9354`
- Policy: `DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT`
- Focused acceptance: `VALIDATED / COMPLETE`
- Scientific acceptance: `NOT_AUTHORIZED`; A-002 physics remains blocked.

## Review and confirmed defect

Reviewed the canonical DeltaE front door, retained numerical/output core, recent history, PR #868,
draft PR #933, mandatory coordination records, prior DeltaE reader/signal audits, backlog, blockers,
master index, and current status checks.

Former front-door blob `be00a58dbbc3c2b9de424c80bea3b5a4be6fe119` delegated event-table output
to retained-core blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414`. The retained `_write_table()`
wrote directly to a final Parquet path, caught every exception, and then wrote a different final CSV
path. It did not reject aliases with validated input snapshots, preserve a previous final through an
atomic replacement, or reject stale alternate-format output.

A deterministic PermissionError control wrote partial Parquet bytes, then the former algorithm
published `events.csv.gz` and left the partial Parquet file. This demonstrates that an arbitrary
serialization/filesystem failure could masquerade as optional-engine fallback and leave two
contradictory event tables.

## Remediation

The canonical front door now overrides `_core._write_table` and:

1. rejects resolved or existing-file aliases between both output candidates and retained exact input
   snapshots;
2. rejects stale alternate-format output without deleting unreviewed bytes;
3. serializes into a unique same-directory temporary file;
4. verifies temporary-file creation, fsyncs the completed file, and publishes with `os.replace`;
5. cleans failed temporaries and preserves a prior final file;
6. permits CSV-gzip fallback only for a recognized missing Parquet engine;
7. fails closed on every other Parquet or CSV error;
8. records the output contract in result and manifest metadata.

The full output directory is not made one atomic transaction by this focused unit. The existing
content-addressed strict runner remains the production bundle gate.

## Files

- `scripts/single_stave/deltaE_E.py`
- `tests/test_deltae_table_output_contract.py`
- `tools/audit/audit_deltae_table_output_contract.py`
- `tests/test_audit_deltae_table_output_contract.py`
- `tools/audit/render_deltae_table_output_contract_evidence.py`
- `docs/validation/deltae_table_output_contract_validation.json`
- `docs/validation/deltae_table_output_contract.svg`
- `docs/validation/deltae_table_output_contract_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/HANDOFF.md`
- this immutable archive record.

## Validation

```text
python -m py_compile \
  scripts/single_stave/deltaE_E.py \
  tests/test_deltae_table_output_contract.py \
  tools/audit/audit_deltae_table_output_contract.py \
  tests/test_audit_deltae_table_output_contract.py \
  tools/audit/render_deltae_table_output_contract_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_deltae_table_output_contract.py \
  tests/test_audit_deltae_table_output_contract.py

14 passed in 0.05s
```

JSON parsing, SVG XML parsing, syntax, and 100-character Python line checks passed. Exact current
source audit status is `VALIDATED` with zero findings. Controls cover atomic Parquet success,
engine-only fallback, arbitrary-error rejection, previous-final preservation, direct/symlink aliases,
stale alternate formats, replacement failure, result metadata, malformed source, invalid UTF-8,
audit aliasing, and atomic audit JSON publication.

Environment: Python `3.13.5`, pandas `2.2.3`, NumPy `2.3.5`.

## Exact identities

- corrected front door blob `71e32dd2acdb70c6b57d3b88fbfac3771f40b52f`, 14,703 bytes,
  SHA-256 `a0ad0b288cd4b5494fa8461089d9a0d192049690a9b8bc15f0cd3036e61b876d`;
- writer regression blob `a3539bf31f9a100baff64754f0bec5f7da141375`, 6,278 bytes,
  SHA-256 `7289e3effab00838ebec2aca33195f0287e8aec60ccb1b89a6605213f5657407`;
- source audit blob `a46598fb6fb27f33b7ec84ec71ea36805ce797c8`, 9,095 bytes,
  SHA-256 `ed3030ab649a3113108d6dc5eb842a7f0905e4363daa62c072a14693aa49d712`;
- audit regression expected blob `858b02abc85d1b32d925533c8a25234469517094`, 3,220 bytes,
  SHA-256 `510a41bc6b46c9ac5b608247330d6c815f5bd3dc8f292697f1001a535c8a95a4`.

## Direct-main commits before coordination finalization

- `80ec61f6de1187301a5205197b9dfe2ec63e3fc1` — task claim;
- `4745faec729b35d7018c2df9ed39bedce72567c9` — implementation;
- `0c1138dba5cbd9940b728c5aaa5e7fb0f1603587` — writer tests;
- `244ffbd840627d70fb04b883a521441b51b40940` — source audit;
- `0485990f0a9093a734b5052f8e6e5ad4ec8f1369` — audit tests;
- `8bb9ff358c51c611df76211006b5e792f7e46b75` — renderer;
- `b8ea33a6b3de1c8dc29d4f499fb49e5c3bf89f02` — validation JSON;
- `3fe3acc179e49d44d36589c530a7113016af0847` — SVG evidence;
- `e24f7e6226bea22ac2ed7b8b5e56f7d2acf12f2b` — audit report.

All writes were direct to `main`; no force-push, branch transport, PR merge, history rewrite, or
unrelated deletion occurred.

## Boundaries and next actions

No exact A-002 table, ROOT data, amplitude convention, pulse polarity, stopping fraction, DeltaE-E
PID, uncertainty budget, calibration, or detector-performance result was produced. Repository-wide
pytest/ruff, ROOT processing, link inventory, and GitHub Actions were not run.

Resolve `AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001`, then
execute the content-addressed production rerun and review all generated tables, plots, uncertainties,
and claims. A separate engineering unit may extend transactionality from the two event tables to the
entire output bundle.
