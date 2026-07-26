# DeltaE Parquet snapshot provenance audit

- **Task:** `AUD-DELTAE-006`
- **Session stamp:** `2026-07-26T043100Z`
- **Initial remote main:** `a29cc75dc403a9af2e804e55a53e8b037efd8942`
- **Policy:** `DELTAE_PARQUET_ROWS_AND_PROVENANCE_MUST_SHARE_ONE_BYTE_SNAPSHOT`
- **Scope:** canonical `scripts/single_stave/deltaE_E.py` Parquet reader and manifest provenance.
- **Scientific status:** software/provenance validation only; no A-002 physics result is authorized.

## Confirmed defect

The exact former front-door Git blob
`90e0709f5f065062bb4dc9f990975992a53d76b1` read `.parquet` and `.pq` inputs with
`pandas.read_parquet(path)`. It did not retain the bytes parsed. During final manifest generation,
`_input_manifest_record()` therefore fell back to `POST_READ_FILE_HASH`, measuring the path after
analysis rather than the bytes that supplied the rows.

A deterministic path-replacement control used original bytes with SHA-256
`0c7231e4128cb270b7021358c50c8a26c53616544d34f9c036b1db48aaada52b` and replacement bytes with
SHA-256 `780ae58dca72ba8a47ad0c126f2f113b8ed5800826b73b714fafe144c2c9936e`.
The former source parsed the original bytes but recorded the replacement digest, so the rows and
manifest did not identify the same input artifact.

The exact former source returned `FLAWED` with seven findings:

1. `PARQUET_PATH_READ_NOT_SNAPSHOTTED`;
2. `PARQUET_READER_NOT_BOUND_TO_BYTES`;
3. `PARQUET_SNAPSHOT_NOT_RETAINED`;
4. `PARQUET_POLICY_MISSING`;
5. `PARQUET_SNAPSHOT_POLICY_MISSING`;
6. `RESULT_CONTRACT_OMITS_PARQUET_POLICY`;
7. `MANIFEST_CONTRACT_OMITS_PARQUET_POLICY`.

This is a provenance defect. It does not prove that an existing production artifact was mutated,
but it means the former manifest could not prove that its digest belonged to the parsed Parquet
rows.

## Remediation

The canonical front door now:

- reads `.parquet` and `.pq` inputs once with `Path.read_bytes()`;
- parses `pandas.read_parquet(io.BytesIO(raw))` from that immutable in-memory snapshot;
- retains byte count and SHA-256 from the same bytes;
- publishes `SINGLE_READ_EXACT_BYTES` and the explicit Parquet provenance policy in `result.json`
  and `manifest.json` reader contracts;
- reuses the retained snapshot in each manifest input record.

CSV behavior remains strict UTF-8 with lossless text dtypes for the three composite-key columns.
The established numerical and plotting core remains unchanged.

## Validation

Executed locally against the exact validated files:

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

Validated controls:

- deterministic path replacement gives a former rows/manifest mismatch and a corrected exact match;
- both `.parquet` and `.pq` use `io.BytesIO` and retain the snapshot;
- result and manifest reader contracts publish the Parquet policy;
- the exact current-source audit returns `VALIDATED` with zero findings;
- the exact former Git blob returns `FLAWED` with seven findings;
- invalid UTF-8 audit source and destructive output aliasing fail closed;
- JSON publication is atomic;
- validation JSON parses and the SVG parses as XML;
- changed Python lines are at most 98 characters.

## Exact validated file identities

| File | Git blob | Bytes | SHA-256 |
|---|---|---:|---|
| `scripts/single_stave/deltaE_E.py` | `a5c255a971a7cf672f011f84b91a3c7b64d1f209` | 6958 | `fc6f049afc0514f0fdc6a95208e8cb4c5c56c2b9ddae5d72914a790ad76f5eea` |
| `tools/audit/audit_deltae_parquet_snapshot.py` | `ad68cabca6e4bcc379d782cf4aece59af70d7438` | 9412 | `efde6376f539164e5471b9ba2dadcd0c5d1eed4eb094d0299c9af42bf38f5ea2` |
| `tests/test_deltae_parquet_snapshot_contract.py` | `d663a1e4103b0b661fd24d8909ae12cdde7080bf` | 5632 | `b3b7768e84ef4659a4ec6ee5f2339e0d70873f5bc7c52e94a7318738d3126d3a` |
| `tools/audit/render_deltae_parquet_snapshot_evidence.py` | `bff50bb72812a8cf8a72680f2a8fd18af72bead7` | 3885 | `9c8ddec507380ffb5ae060dadb4394d560ab9777ef89c0159b46731305ee55ea` |

## Visual evidence

`docs/validation/deltae_parquet_snapshot.svg` contrasts the former split-read path with the current
one-snapshot path. It is explicitly labelled synthetic software/provenance evidence and does not
represent beam or detector data.

Generation command:

```text
python tools/audit/render_deltae_parquet_snapshot_evidence.py \
  --input docs/validation/deltae_parquet_snapshot_validation.json \
  --output docs/validation/deltae_parquet_snapshot.svg
```

Success criterion: parsed-row SHA-256 equals the manifest input SHA-256 after a deterministic path
replacement. Former source fails; current source passes.

## Limitations and next action

This unit does not process a real Parquet table, ROOT file, or A-002 production input. It does not
resolve amplitude convention, pulse polarity, stopping fractions, DeltaE-E PID, uncertainty,
calibration, or detector performance. Those remain blocked under `AUD-DELTAE-001`,
`AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001`.

A later immutable production run must retain the exact table digest, code commit, command,
environment, event-cardinality closure, result/manifest hashes, uncertainties, and reviewed plots.
