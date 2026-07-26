# Latest Handoff

## Session

- **Task:** `AUD-DELTAE-008`
- **Stamp:** `2026-07-26T052912Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `ed3633055695184bd5ef68ab90bb6951e81d9354`
- **Validated implementation/evidence head before handoff:** `122baac3bb3bb704a2ab97f5efd76843a24439b2`
- **Destination:** direct commits to `main`; no task branch, force-push, history rewrite, PR merge, or deletion of unrelated work.
- **Focused acceptance:** canonical event-table output boundary `VALIDATED / COMPLETE`.
- **Scientific acceptance:** A-002 physics remains `PARTIAL / BLOCKED`.

## Start-of-run review

Fetched current `main`, recent history, repository permissions, open draft PR #933, closed PR #868,
commit status, mandatory coordination records, the canonical DeltaE front door and retained numerical
core, prior CSV-key/Parquet/signal-value audits, focused tests, backlog, blockers, master index, and the
latest handoff. No existing active or complete task represented this output-publication defect.

PR #933 remained draft, open, non-mergeable, and blocked by its red repository-wide gate. PR #868
remained closed, unmerged, and non-mergeable. Neither PR was modified or merged.

## Confirmed defect

Former front-door blob `be00a58dbbc3c2b9de424c80bea3b5a4be6fe119` delegated event-table
publication to retained-core blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414`. The retained
`_write_table()` wrote to a final Parquet path, caught every `Exception`, then wrote a different final
CSV path. It did not:

- distinguish a missing optional Parquet engine from permission, data, filesystem, or serialization
  failure;
- reject output paths that alias exact validated input snapshots;
- publish through a completed same-directory temporary file and atomic replacement;
- reject a stale alternate-format output.

A deterministic control injected `PermissionError` after writing partial Parquet bytes. The former
algorithm then published `events.csv.gz` and left the partial `events.parquet`, creating two
contradictory artifacts while converting a real failure into apparent format fallback.

Policy:

`DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT`

## Remediation

The canonical front door now overrides `_core._write_table` and:

1. resolves both output candidates and rejects equality or `samefile()` aliasing with any retained
   input snapshot;
2. rejects a stale alternate-format final without deleting unreviewed bytes;
3. writes to a unique same-directory temporary path;
4. verifies temporary-file creation, fsyncs it, and publishes with `os.replace`;
5. removes failed temporaries while preserving a previous final file;
6. permits CSV-gzip fallback only for a recognized missing Parquet engine;
7. fails closed on every other Parquet or CSV publication error;
8. records the event-table output contract in both result and manifest metadata.

The full output directory is not one atomic transaction in this focused unit. The existing
content-addressed strict runner remains the production bundle gate.

## Files changed

- `scripts/single_stave/deltaE_E.py`
- `tests/test_deltae_table_output_contract.py`
- `tools/audit/audit_deltae_table_output_contract.py`
- `tests/test_audit_deltae_table_output_contract.py`
- `tools/audit/render_deltae_table_output_contract_evidence.py`
- `docs/validation/deltae_table_output_contract_validation.json`
- `docs/validation/deltae_table_output_contract.svg`
- `docs/validation/deltae_table_output_contract_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/archive/2026-07-26T052912Z_AUD-DELTAE-008_TABLE_OUTPUT_INTEGRITY.md`
- this handoff.

## Exact identities

- former front-door blob: `be00a58dbbc3c2b9de424c80bea3b5a4be6fe119`;
- retained-core blob: `fe5dd5e4673f32fa5a4b94776531f2b392e12414`;
- corrected front-door blob: `71e32dd2acdb70c6b57d3b88fbfac3771f40b52f`, 14,703 bytes,
  SHA-256 `a0ad0b288cd4b5494fa8461089d9a0d192049690a9b8bc15f0cd3036e61b876d`;
- direct-test blob: `a3539bf31f9a100baff64754f0bec5f7da141375`, 6,278 bytes,
  SHA-256 `7289e3effab00838ebec2aca33195f0287e8aec60ccb1b89a6605213f5657407`;
- auditor blob: `a46598fb6fb27f33b7ec84ec71ea36805ce797c8`, 9,095 bytes,
  SHA-256 `ed3030ab649a3113108d6dc5eb842a7f0905e4363daa62c072a14693aa49d712`;
- audit-test expected blob: `858b02abc85d1b32d925533c8a25234469517094`, 3,220 bytes,
  SHA-256 `510a41bc6b46c9ac5b608247330d6c815f5bd3dc8f292697f1001a535c8a95a4`.

## Validation

Executed against the exact proposed front door, tests, audit gate, and renderer:

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

Environment: Python `3.13.5`, pandas `2.2.3`, NumPy `2.3.5`.

Validated controls:

- atomic Parquet success;
- CSV-gzip fallback only for a missing Parquet engine;
- no fallback after arbitrary Parquet failure;
- preservation of a prior final after serialization or replacement failure;
- direct and symlink input/output aliases;
- stale alternate-format rejection without deletion;
- result-contract publication;
- exact-source zero-finding audit;
- malformed-contract, invalid UTF-8, audit alias, and atomic audit-JSON controls;
- JSON and SVG parsing; Python lines at most 100 characters.

The focused reconstruction used the exact proposed front door/tests/auditor/renderer and a minimal
retained-core stub. A complete clone could not be materialized because `github.com` DNS resolution
failed. Repository-wide pytest/ruff, ROOT or production Parquet processing, GitHub Actions, and the
full link inventory were not run and are not claimed.

## Better-method decision

Catching all Parquet failures and publishing CSV was rejected because it conceals real errors.
Unconditional Parquet was not selected because the repository intentionally supports environments
without an optional engine. Automatic deletion of stale alternate output was rejected because it
would destroy unreviewed provenance. Explicit missing-engine fallback with fail-closed alias/stale
checks and atomic file publication was selected. Transactional whole-bundle publication remains a
separate higher-level method already represented by the strict runner.

## Direct-main commits before handoff

- `80ec61f6de1187301a5205197b9dfe2ec63e3fc1` — task claim;
- `4745faec729b35d7018c2df9ed39bedce72567c9` — implementation;
- `0c1138dba5cbd9940b728c5aaa5e7fb0f1603587` — direct tests;
- `244ffbd840627d70fb04b883a521441b51b40940` — fail-closed audit;
- `0485990f0a9093a734b5052f8e6e5ad4ec8f1369` — audit tests;
- `8bb9ff358c51c611df76211006b5e792f7e46b75` — evidence renderer;
- `b8ea33a6b3de1c8dc29d4f499fb49e5c3bf89f02` — validation JSON;
- `3fe3acc179e49d44d36589c530a7113016af0847` — visual evidence;
- `e24f7e6226bea22ac2ed7b8b5e56f7d2acf12f2b` — audit report;
- `44aeef79cb928c3f2dd5f8438b399494c872453a` — immutable archive;
- `122baac3bb3bb704a2ab97f5efd76843a24439b2` — active-task completion.

GitHub returned successful direct-main commit SHAs for every write. No force update was used.

## Coordination limitation

`BACKLOG.md`, `MASTER_INDEX.md`, and `SESSION_LOG.md` were reviewed but not replaced before this
handoff. The connector exposes complete-file replacement rather than byte-safe patch/append, and the
long shared files were available only in paged or truncated responses. Replacing a partial
reconstruction could erase unrelated or append-only provenance. This unmet mandatory synchronization
step is recorded explicitly here and in the immutable archive rather than reported as complete.

## Scientific boundary and next action

No exact A-002 pulse table, ROOT file, amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance result was produced.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001` remain open.

Next, obtain hash-bound convention and polarity evidence and execute a content-addressed production
rerun through the strict reader/value/output boundaries, followed by event-cardinality, uncertainty,
plot, and claim validation.
