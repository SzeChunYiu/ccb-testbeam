# DeltaE event-table output integrity audit

- **Task:** `AUD-DELTAE-008`
- **Session stamp:** `2026-07-26T052912Z`
- **Initial remote main:** `ed3633055695184bd5ef68ab90bb6951e81d9354`
- **Policy:** `DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT`
- **Focused status:** `VALIDATED`
- **Scientific status:** `NOT_AUTHORIZED`

## Repository facts reviewed

The canonical front door at former Git blob
`be00a58dbbc3c2b9de424c80bea3b5a4be6fe119` retained the numerical/output
implementation from `_deltaE_E_core.py`. The retained core blob
`fe5dd5e4673f32fa5a4b94776531f2b392e12414` implemented `_write_table()` as:

1. call `DataFrame.to_parquet()` on the final path;
2. catch every `Exception`;
3. call `DataFrame.to_csv()` on a different final path;
4. return whichever path was reached.

The output candidates were not compared with the two exact input snapshots, serialization used the
final path directly, and stale alternate-format output was not rejected. These are artifact-integrity
defects, independent of the unresolved A-002 physics convention.

## Demonstrated failure mode

A deterministic software control injected `PermissionError` after writing a partial Parquet file.
The former algorithm then called the CSV writer, published `events.csv.gz`, and left the partial
`events.parquet` beside it. A permission, filesystem, serialization, or data error could therefore be
misclassified as an optional-dependency condition while two contradictory event tables remained in
the output directory.

A second path-level risk follows directly from the canonical CLI: inputs are read before outputs are
written, and an input may be named exactly `deltaE_E_events_data.parquet` below the requested output
directory. The former writer did not reject that alias and could overwrite the validated input bytes.

## Remediation

The front door now overrides the retained writer and publishes the machine-readable contract:

- policy: `DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT`;
- publication: `SAME_DIRECTORY_TEMP_FSYNC_OS_REPLACE`;
- fallback: `CSV_GZIP_ONLY_WHEN_PARQUET_ENGINE_UNAVAILABLE`;
- stale alternate format: `REJECT`.

The implementation:

1. resolves both final event-table candidates and rejects equality or `samefile()` aliasing with any
   retained input snapshot;
2. rejects a stale alternate-format final before publication rather than deleting unreviewed bytes;
3. writes to a unique same-directory temporary path;
4. verifies that the writer created the temporary artifact;
5. flushes through the writer, opens the completed temporary file, calls `fsync`, and publishes with
   `os.replace`;
6. removes the temporary path after any failure, preserving a previous final file;
7. permits CSV-gzip fallback only for a recognized Parquet-engine `ImportError`;
8. converts every other Parquet or CSV publication failure to `EventTableOutputError`;
9. records the output contract in both `result.json` and `manifest.json`.

## Method comparison

| Method | Portability | Failure discrimination | Input safety | Stale-output safety | Decision |
|---|---|---|---|---|---|
| Catch every exception and publish CSV | High | Invalid | None | None | Rejected |
| Require Parquet unconditionally | Lower | Strong | Needs separate gate | Needs separate gate | Not selected |
| Explicit missing-engine fallback with atomic publication | High | Strong | Fail closed | Fail closed | Selected |
| Transactional whole-directory bundle | Highest integrity | Strong | Strong | Strong | Separate follow-up |

The selected method preserves optional Parquet portability without treating arbitrary failures as a
format-selection decision. The full output directory is still not one atomic transaction; the
content-addressed strict runner remains the higher-level production gate.

## Validation

Executed in the local focused reconstruction:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E.py \
  tools/audit/audit_deltae_table_output_contract.py \
  tests/test_deltae_table_output_contract.py \
  tests/test_audit_deltae_table_output_contract.py \
  tools/audit/render_deltae_table_output_contract_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_deltae_table_output_contract.py \
  tests/test_audit_deltae_table_output_contract.py

14 passed in 0.06s
```

Covered controls:

- successful atomic Parquet publication;
- CSV-gzip fallback only for a missing Parquet engine;
- no fallback after arbitrary Parquet failure;
- preservation of a previous final file after serialization or replacement failure;
- direct and symlink input/output alias rejection;
- stale alternate-format rejection without deletion;
- result-contract publication;
- strict source audit, invalid UTF-8 handling, atomic audit JSON, and audit input/output aliasing.

The source audit returns `VALIDATED` with zero findings. JSON parsing, SVG XML parsing, syntax, and
100-character line-length checks pass.

## Exact validated identities before GitHub publication

- proposed front door: 14,703 bytes, SHA-256
  `a0ad0b288cd4b5494fa8461089d9a0d192049690a9b8bc15f0cd3036e61b876d`, expected Git blob
  `71e32dd2acdb70c6b57d3b88fbfac3771f40b52f`;
- writer regression: 6,278 bytes, SHA-256
  `7289e3effab00838ebec2aca33195f0287e8aec60ccb1b89a6605213f5657407`, expected Git blob
  `a3539bf31f9a100baff64754f0bec5f7da141375`;
- source audit: 9,095 bytes, SHA-256
  `ed3030ab649a3113108d6dc5eb842a7f0905e4363daa62c072a14693aa49d712`, expected Git blob
  `a46598fb6fb27f33b7ec84ec71ea36805ce797c8`;
- audit regression: 3,220 bytes, SHA-256
  `510a41bc6b46c9ac5b608247330d6c815f5bd3dc8f292697f1001a535c8a95a4`, expected Git blob
  `858b02abc85d1b32d925533c8a25234469517094`.

## Scientific boundary

No exact A-002 pulse table, ROOT file, amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance result was produced.
This remediation prevents artifact ambiguity; it does not validate the scientific inputs or the
reported physics.

Repository-wide pytest, ruff, ROOT processing, the full Markdown link inventory, and GitHub Actions
were not run. A production rerun remains blocked under `AUD-DELTAE-001`, `AUD-DELTAE-002`,
`AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001`.
