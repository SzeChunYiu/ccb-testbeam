# Latest Handoff

## Session

- **Task:** `AUD-DELTAE-006`
- **Stamp:** `2026-07-26T043100Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `a29cc75dc403a9af2e804e55a53e8b037efd8942`
- **Validated implementation/evidence head before handoff:** `1e7a9a80a10a9b726e536febf5517b47e898b6cd`
- **Destination:** direct commits to `main`; no task branch, force-push, history rewrite, PR merge, or
  deletion of unrelated work.
- **Focused acceptance:** canonical Parquet reader and same-snapshot provenance
  `VALIDATED / COMPLETE`.
- **Scientific acceptance:** A-002 physics remains `PARTIAL / BLOCKED`.

## Start-of-run review

Fetched current `main`, recent history, repository permissions, open PR #933, closed PR #868,
commit status, all mandatory coordination records, the canonical DeltaE front door and retained
numerical core, existing CSV-key tests/audit evidence, backlog, blockers, master index, result map,
claim matrix, and visualization matrix. A concurrent non-overlapping session-log provenance commit
advanced `main` to `a29cc75dc403a9af2e804e55a53e8b037efd8942` before implementation; work was based on that
head. PR #933 remained draft, open, unmergeable, and red at its repository-wide validation gate.
PR #868 remained closed and unmerged.

## Confirmed defect

Former front-door Git blob `90e0709f5f065062bb4dc9f990975992a53d76b1` read `.parquet` and
`.pq` inputs using `pandas.read_parquet(path)`. It did not retain the bytes that supplied the rows.
During manifest creation, `_input_manifest_record()` therefore fell back to `POST_READ_FILE_HASH`,
measuring the path after analysis rather than the parsed artifact.

A deterministic path-replacement control parsed original bytes with SHA-256
`0c7231e4128cb270b7021358c50c8a26c53616544d34f9c036b1db48aaada52b`, then replaced the path
with bytes whose SHA-256 was
`780ae58dca72ba8a47ad0c126f2f113b8ed5800826b73b714fafe144c2c9936e`. The former reader paired
rows from the first artifact with provenance from the second. Exact former-source audit status was
`FLAWED` with seven findings.

Policy:

`DELTAE_PARQUET_ROWS_AND_PROVENANCE_MUST_SHARE_ONE_BYTE_SNAPSHOT`

## Remediation

The canonical front door now:

1. reads `.parquet` and `.pq` paths once with `Path.read_bytes()`;
2. parses `pandas.read_parquet(io.BytesIO(raw))`;
3. retains byte count and SHA-256 from the same bytes;
4. reuses that retained snapshot in manifest input records;
5. publishes the policy and `SINGLE_READ_EXACT_BYTES` in result and manifest reader contracts.

CSV strict-UTF-8/lossless-key behavior and the established numerical/plotting core remain
unchanged.

## Files changed

- `scripts/single_stave/deltaE_E.py`
- `tools/audit/audit_deltae_parquet_snapshot.py`
- `tests/test_deltae_parquet_snapshot_contract.py`
- `tools/audit/render_deltae_parquet_snapshot_evidence.py`
- `docs/validation/deltae_parquet_snapshot_validation.json`
- `docs/validation/deltae_parquet_snapshot.svg`
- `docs/validation/deltae_parquet_snapshot_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/archive/2026-07-26T043100Z_AUD-DELTAE-006_PARQUET_SNAPSHOT.md`
- matching `SESSION_LOG.md` entry and this handoff.

## Exact identities

- former front-door blob: `90e0709f5f065062bb4dc9f990975992a53d76b1`, 5,854 bytes,
  SHA-256 `edbf8f5513a39c95fdab7a6f895c7b5a4868ee1dad0b41148f195ceeab1c9c21`;
- corrected front-door blob: `a5c255a971a7cf672f011f84b91a3c7b64d1f209`, 6,958 bytes,
  SHA-256 `fc6f049afc0514f0fdc6a95208e8cb4c5c56c2b9ddae5d72914a790ad76f5eea`;
- audit blob: `ad68cabca6e4bcc379d782cf4aece59af70d7438`, 9,412 bytes,
  SHA-256 `efde6376f539164e5471b9ba2dadcd0c5d1eed4eb094d0299c9af42bf38f5ea2`;
- focused-test blob: `d663a1e4103b0b661fd24d8909ae12cdde7080bf`, 5,632 bytes,
  SHA-256 `b3b7768e84ef4659a4ec6ee5f2339e0d70873f5bc7c52e94a7318738d3126d3a`;
- renderer blob: `bff50bb72812a8cf8a72680f2a8fd18af72bead7`, 3,885 bytes,
  SHA-256 `9c8ddec507380ffb5ae060dadb4394d560ab9777ef89c0159b46731305ee55ea`.

## Validation

Executed:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E.py \
  tools/audit/audit_deltae_parquet_snapshot.py \
  tests/test_deltae_parquet_snapshot_contract.py \
  tools/audit/render_deltae_parquet_snapshot_evidence.py

PYTHONPATH=. pytest -q tests/test_deltae_parquet_snapshot_contract.py

7 passed in 0.04s
```

Environment: Python `3.13.5`, pandas `2.2.3`, NumPy `2.3.5`.

Validated behavior:

- deterministic path replacement fails former rows/manifest identity and passes current identity;
- both `.parquet` and `.pq` use `io.BytesIO` and retain the exact snapshot;
- exact current-source audit returns `VALIDATED` with zero findings;
- exact former source returns `FLAWED` with seven findings;
- invalid UTF-8 audit source and destructive output aliasing fail closed;
- audit JSON publication is atomic;
- JSON and SVG parsing and changed-file line-length checks pass.

A real Parquet engine/file was not executed. The behavioral regression monkeypatched
`pandas.read_parquet` to test the acquisition/provenance boundary independently of an optional
backend. Repository-wide pytest/ruff, ROOT processing, GitHub Actions, and the complete link
inventory were not run and are not claimed.

## Direct-main commits before handoff

- `e33e331d71dc74de5586a914a6081ec9faead825` — `fix(deltae): bind Parquet rows to exact input bytes`;
- `b528409639cf506a86c9e19945dadb85d454a4ee` — `audit(deltae): enforce Parquet snapshot provenance`;
- `9ad3fff4255c9d284d0529b5929bbb3e2b902976` — `test(deltae): cover Parquet snapshot provenance`;
- `9469c443617852b82edf05f4fbd6426091b1632a` — evidence renderer;
- `4564bc727ebf645ad52d251800bc44e3eee3898c` — validation JSON;
- `233fb5aa2268521f036939d85d502ca0b6346ac0` — visual evidence;
- `54c4f28a5ebad834b12118f767d47f0ddb7462d0` — audit report;
- `7e5c3a71069c81f6a60cbc2cdfc471345f2852fc` — active-task completion;
- `95c8bda66442938f4fdcf48ec1c5b6f9c4206033` — immutable archive;
- `1e7a9a80a10a9b726e536febf5517b47e898b6cd` — backlog synchronization.

GitHub returned successful direct-main commit SHAs for every write. Recent remote history confirmed
the focused sequence consecutively on `main`; no force update was used.

## Scientific boundary and next action

No exact A-002 pulse table, ROOT file, amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance result was produced.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001` remain open.
The next scientific step is to bind immutable convention/polarity evidence and execute a
content-addressed production rerun through this strict input boundary, followed by event-cardinality,
uncertainty, plot, and claim validation.
