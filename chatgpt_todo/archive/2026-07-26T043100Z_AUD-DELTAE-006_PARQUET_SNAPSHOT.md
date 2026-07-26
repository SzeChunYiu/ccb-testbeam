# AUD-DELTAE-006 — DeltaE Parquet snapshot provenance

## Session

- **Stamp:** `2026-07-26T043100Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `a29cc75dc403a9af2e804e55a53e8b037efd8942`
- **Destination:** direct commits to `main`; no task branch, force-push, history rewrite, PR merge, or
  deletion of unrelated work.
- **Focused acceptance:** `VALIDATED / COMPLETE`.
- **Scientific acceptance:** A-002 physics remains `PARTIAL / BLOCKED`.

## Start-of-run review

Fetched current `main`, recent history, repository permissions, open PR #933, closed PR #868,
commit status, mandatory coordination files, the canonical DeltaE front door and retained numerical
core, existing CSV-key regressions/audit evidence, backlog, master index, blockers, result map,
claim matrix, and visualization matrix. A concurrent non-overlapping session-log provenance commit
advanced `main` to `a29cc75dc403a9af2e804e55a53e8b037efd8942` before this implementation; work was based on
that head. PR #933 remained draft, open, unmergeable, and red at its repository-wide validation
gate. PR #868 remained closed and unmerged.

## Confirmed defect

Former front-door Git blob `90e0709f5f065062bb4dc9f990975992a53d76b1` handled CSV inputs
through one strict UTF-8 byte snapshot, but handled `.parquet` and `.pq` by calling
`pandas.read_parquet(path)`. No parsed-byte snapshot was retained. `_input_manifest_record()` then
fell back to `POST_READ_FILE_HASH`, so a path replacement between parsing and manifest publication
could pair rows from bytes A with the byte count and SHA-256 of bytes B.

Deterministic path-replacement control:

- original bytes SHA-256:
  `0c7231e4128cb270b7021358c50c8a26c53616544d34f9c036b1db48aaada52b`;
- replacement bytes SHA-256:
  `780ae58dca72ba8a47ad0c126f2f113b8ed5800826b73b714fafe144c2c9936e`;
- former parsed SHA-256: original;
- former manifest SHA-256: replacement;
- former rows/manifest identity: `false`.

Exact former-source audit result: `FLAWED`, seven findings:

- `PARQUET_PATH_READ_NOT_SNAPSHOTTED`;
- `PARQUET_READER_NOT_BOUND_TO_BYTES`;
- `PARQUET_SNAPSHOT_NOT_RETAINED`;
- `PARQUET_POLICY_MISSING`;
- `PARQUET_SNAPSHOT_POLICY_MISSING`;
- `RESULT_CONTRACT_OMITS_PARQUET_POLICY`;
- `MANIFEST_CONTRACT_OMITS_PARQUET_POLICY`.

No evidence was found that a specific historical production path actually changed during a run.
The demonstrated flaw is that the former provenance contract could not prove otherwise.

## Remediation

Policy:

`DELTAE_PARQUET_ROWS_AND_PROVENANCE_MUST_SHARE_ONE_BYTE_SNAPSHOT`

Canonical `scripts/single_stave/deltaE_E.py` now:

1. reads `.parquet` and `.pq` paths exactly once with `Path.read_bytes()`;
2. parses `pandas.read_parquet(io.BytesIO(raw))`;
3. retains byte count and SHA-256 from those same bytes;
4. reuses the retained snapshot in the manifest input record;
5. publishes `SINGLE_READ_EXACT_BYTES` and the explicit Parquet provenance policy in both
   `result.json` and `manifest.json` reader contracts.

The strict CSV composite-key reader remains unchanged in meaning. The retained numerical and
plotting implementation `_deltaE_E_core.py` was not modified.

## Validation

Executed locally:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E.py \
  tools/audit/audit_deltae_parquet_snapshot.py \
  tests/test_deltae_parquet_snapshot_contract.py \
  tools/audit/render_deltae_parquet_snapshot_evidence.py

PYTHONPATH=. pytest -q tests/test_deltae_parquet_snapshot_contract.py

7 passed in 0.04s
```

Environment:

- Python `3.13.5`;
- pandas `2.2.3`;
- NumPy `2.3.5`.

Validated behavior:

- deterministic path replacement gives exact rows/manifest identity under the corrected reader;
- both `.parquet` and `.pq` use `io.BytesIO` and retain a snapshot;
- result and manifest contracts expose the policy;
- exact current-source audit returns `VALIDATED` with zero findings;
- exact former source returns `FLAWED` with seven findings;
- invalid UTF-8 audit input and destructive audit-output aliasing fail closed;
- JSON publication is atomic;
- validation JSON parses and visual evidence parses as XML;
- changed Python lines are at most 98 characters.

A real Parquet engine/file was not exercised; the direct behavioral control monkeypatched
`pandas.read_parquet` to verify the acquisition and provenance boundary independently of an optional
Parquet backend. Repository-wide pytest/ruff, ROOT processing, Actions, and the full link inventory
were not run and are not claimed.

## Exact file identities

- canonical front door: Git blob `a5c255a971a7cf672f011f84b91a3c7b64d1f209`, 6,958 bytes,
  SHA-256 `fc6f049afc0514f0fdc6a95208e8cb4c5c56c2b9ddae5d72914a790ad76f5eea`;
- audit gate: Git blob `ad68cabca6e4bcc379d782cf4aece59af70d7438`, 9,412 bytes,
  SHA-256 `efde6376f539164e5471b9ba2dadcd0c5d1eed4eb094d0299c9af42bf38f5ea2`;
- focused tests: Git blob `d663a1e4103b0b661fd24d8909ae12cdde7080bf`, 5,632 bytes,
  SHA-256 `b3b7768e84ef4659a4ec6ee5f2339e0d70873f5bc7c52e94a7318738d3126d3a`;
- renderer: Git blob `bff50bb72812a8cf8a72680f2a8fd18af72bead7`, 3,885 bytes,
  SHA-256 `9c8ddec507380ffb5ae060dadb4394d560ab9777ef89c0159b46731305ee55ea`.

## Files changed

- `scripts/single_stave/deltaE_E.py`
- `tools/audit/audit_deltae_parquet_snapshot.py`
- `tests/test_deltae_parquet_snapshot_contract.py`
- `tools/audit/render_deltae_parquet_snapshot_evidence.py`
- `docs/validation/deltae_parquet_snapshot_validation.json`
- `docs/validation/deltae_parquet_snapshot.svg`
- `docs/validation/deltae_parquet_snapshot_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this immutable archive record
- matching latest handoff and session-log entry.

## Direct-main commits before archive publication

- `e33e331d71dc74de5586a914a6081ec9faead825` —
  `fix(deltae): bind Parquet rows to exact input bytes`;
- `b528409639cf506a86c9e19945dadb85d454a4ee` —
  `audit(deltae): enforce Parquet snapshot provenance`;
- `9ad3fff4255c9d284d0529b5929bbb3e2b902976` —
  `test(deltae): cover Parquet snapshot provenance`;
- `9469c443617852b82edf05f4fbd6426091b1632a` —
  `docs(validation): add Parquet snapshot evidence renderer`;
- `4564bc727ebf645ad52d251800bc44e3eee3898c` —
  `docs(validation): record Parquet snapshot validation`;
- `233fb5aa2268521f036939d85d502ca0b6346ac0` —
  `docs(validation): visualize Parquet snapshot provenance`;
- `54c4f28a5ebad834b12118f767d47f0ddb7462d0` —
  `docs(validation): document Parquet snapshot audit`;
- `7e5c3a71069c81f6a60cbc2cdfc471345f2852fc` —
  `docs(audit): complete DeltaE Parquet snapshot task`.

## Scientific boundary and next action

No exact A-002 pulse table, ROOT file, amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance result was produced.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001` remain open.
The next scientific unit must obtain immutable convention/polarity evidence and execute a
content-addressed production rerun through the strict table reader, followed by event-cardinality,
uncertainty, plot, and claim validation.
