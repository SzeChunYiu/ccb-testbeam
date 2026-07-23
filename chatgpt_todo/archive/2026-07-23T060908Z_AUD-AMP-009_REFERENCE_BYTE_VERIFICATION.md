# AUD-AMP-009 — Evidence-reference byte verification

## Session identity

- **UTC:** 2026-07-23T06:09:08Z
- **Owner:** scheduled ChatGPT audit session
- **Initial remote main:** `1b00e612cd9358486f2d9db0164def1ec09fec20`
- **Write target:** direct to `main`
- **Repository:** `SzeChunYiu/ccb-testbeam`

## Repository and concurrency review

- Confirmed push/admin access to the exact repository.
- Inspected recent `main` history and based all changes on the latest initial head.
- Re-read `HANDOFF.md`, `ACTIVE_TASK.md`, `BACKLOG.md`, `MASTER_INDEX.md`, `CODE_RESULT_MAP.md`, `BLOCKERS.md`, and `SESSION_LOG.md`.
- Inspected PR #868: GitHub reports it closed, not merged, and non-mergeable at head `7992aa318b6f13b5f4bcbd828ad97996075fed4b`; no merge was attempted.
- Inspected open pull-request inventory for concurrent work. This task is a focused continuation of the amplitude-provenance audit and does not duplicate the active repository-wide inventory.

## Confirmed defect

`validate_amplitude_evidence_map.py` v1.1.0 required a canonical `evidence_reference_sha256`, but validated only its textual format. It did not resolve the referenced schema, producer-code, or pedestal-evidence file and did not compare the declaration with measured bytes.

`amplitude_convention_audit.py` v3.0.0 consumed that schema-valid record as physics authorization. Consequently, a missing, mutated, or fabricated supporting-artifact digest could still authorize `ABSOLUTE` pedestal subtraction or `NET` pass-through.

## Corrected method

### Evidence-map validator v1.2.0

- Resolves the file component of `evidence_reference`, retaining optional `#fragment` text for human traceability.
- Uses an explicit `--evidence-root`, defaulting to the evidence-map directory.
- Rejects absolute paths, paths escaping the controlled root, and missing files.
- Streams the supporting artifact through SHA-256 and requires exact equality with `evidence_reference_sha256`.
- Emits measured digest, resolved path, and `evidence_reference_verified=true` only after byte equality is established.
- Marks schema-only programmatic validation as unverified rather than implying byte verification.

### Convention auditor v3.1.0

- Loads CLI maps through measured reference-byte verification.
- Accepts physics authorization only from a `ValidatedEvidenceMap` carrying verified references.
- Treats an otherwise valid raw programmatic dictionary as non-authorizing and emits `EVIDENCE_REFERENCE_BYTES_UNVERIFIED`.
- Exposes the verified reference, declared/measured digest, and verification state in each result record.
- Preserves all earlier full-table, malformed/nonfinite, ambiguity, pedestal-schema, and baseline-data gates.

## Validation

The exact proposed implementation and six affected test modules were reconstructed locally and executed:

```text
python -m py_compile \
  tools/audit/validate_amplitude_evidence_map.py \
  tools/audit/amplitude_convention_audit.py \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_integration.py \
  tests/test_hash_bound_amplitude_evidence.py \
  tests/test_amplitude_convention_anchor_gate.py \
  tests/test_amplitude_baseline_acceptance_gate.py \
  tests/test_amplitude_physics_baseline_gate.py

python -m pytest \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_integration.py \
  tests/test_hash_bound_amplitude_evidence.py \
  tests/test_amplitude_convention_anchor_gate.py \
  tests/test_amplitude_baseline_acceptance_gate.py \
  tests/test_amplitude_physics_baseline_gate.py -q

35 passed in 0.12s
```

A changed-file line-length scan found and corrected all lines longer than 100 characters before the final local rerun. Ruff was not installed in the execution container. The full repository suite and GitHub Actions were not run, so no broader success is claimed.

Regression cases include:

- valid file-byte verification;
- missing evidence file;
- declared/measured digest mismatch;
- supporting-artifact mutation after map creation;
- absolute and root-escaping reference rejection;
- schema-only maps remaining unverified;
- direct programmatic-map bypass remaining non-authorizing;
- verified `NET` and executable verified `ABSOLUTE` acceptance;
- prior baseline and convention safety gates.

## Main commits before final coordination handoff

- `eec5aa761a075dc422558dabf6beaec9ae009f43` — `fix(audit): verify amplitude evidence artifact bytes`
- `e37f61bc6b50342d4565b0df33eb6d751d25cfa3` — `fix(audit): require measured evidence-reference equality`
- `c8bc2ad8a3855815d50adb726817c6dc1a08faa5` — `test(audit): verify evidence artifact byte matching`
- `d32aff3a4e74435c8bcac8d32c0054553508e6f2` — `test(audit): block unverified evidence-reference bytes`
- `54d80bded56b763c7642879de9b33d2f5e9786a0` — `test(audit): verify hash-bound reference artifacts`
- `382de1f501edf850ca52aa787ca78c262540a839` — `test(audit): verify convention-anchor artifacts`
- `7b246c55d7141f45ce9a720879de871360e60cd0` — `test(audit): verify baseline evidence artifacts`
- `a15b9dd29f186bf0b6967e7073d96a98cbda2dc0` — `test(audit): verify physics evidence artifacts`
- `579805fa00e76daaaa3391752fff8ef04532b93e` — `docs(audit): claim evidence-reference byte verification`
- `b7a27eeef046c86efe51996a8da86a42ba3013b7` — `docs(audit): track evidence-reference byte verification`
- `5f8ffb356fbf08d633eae0c2ee9452b211db39d1` — `docs(audit): index amplitude evidence authorization`
- `fc9c9a8efeca4564fd5c852cfe6f4b927ef6aea1` — `docs(audit): map amplitude evidence to physics use`
- `f1430c313eb47f7dcee3603f0a1f445c01ad47fe` — `docs(audit): record amplitude evidence-data blocker`

## Scientific boundary

No real A-002 pulse table, schema artifact, producer-code snapshot, or pedestal review artifact was available. This session does not determine whether the real `amplitude_adc` column is absolute or net and does not regenerate stopping counts, fractions, event CSV, DeltaE-E plot, calibration, or detector-performance results. Historical A-002 outputs remain quarantined.

## Acceptance status

- Supporting-artifact path containment and measured SHA-256 gate: VALIDATED by focused synthetic regression.
- Raw programmatic-map bypass prevention: VALIDATED by focused synthetic regression.
- Full repository CI/lint: NOT RUN.
- Real A-002 convention and regenerated outputs: BLOCKED by `BLK-AMP-001`.

## Next action

Obtain the exact A-002 table and the exact supporting evidence artifact. Place the evidence map under a controlled root, run both tools without `--max-rows`, review every warning and error, and regenerate scientific outputs only after the result reports a verified evidence reference and `physics_acceptance=ACCEPTABLE`.
