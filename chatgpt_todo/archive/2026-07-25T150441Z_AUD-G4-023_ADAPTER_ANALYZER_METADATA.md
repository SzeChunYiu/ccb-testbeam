# AUD-G4-023 — Adapter/analyzer metadata consistency

## Session identity

- Session stamp: `2026-07-25T150441Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `9104fc1c0a6b1e3ce3323a08869444e1b68d6c16`
- Destination: direct commits to remote `main`; no force-push, history rewrite,
  task branch, or PR transport
- Focused audit-gate status: `VALIDATED`
- Current adapter metadata status: `FLAWED`
- Cumulative task status: `PARTIAL`

## Start-of-run inspection

Inspected current remote history and permissions, PR #868, current combined
status, open PR inventory, `chatgpt_todo/ACTIVE_TASK.md`, `HANDOFF.md`,
`BACKLOG.md`, `SESSION_LOG.md`, the current event-contract documentation, the
adapter, analyzer, focused adapter tests, and the immediately preceding
single-stave event-contract and analyzer-remediation histories.

PR #868 remains closed, unmerged, and non-mergeable. It was not modified. Open
PRs were checked for overlap; no active completed task was duplicated.

## Confirmed defect

The adapter blob `d7b1e797188ea4d20de9a010d040eb578908d418` is
version 1.0.0. Its normalized output already preserves the scintillation, WLS,
and Cerenkov component counts, builds `n_optical_generated_total`, and rejects
arrival counts above that total. Its emitted metadata nevertheless still says:

- `analysis_compatibility = SCHEMA_ADAPTER_ONLY`; and
- `analyze_single_stave.py still validates arrivals against
  n_scint_generated alone; it must use n_optical_generated_total ...`.

The current analyzer blob `4da04847bfb1e4c30aa8b8714624d9f5d7e8e8fd`
is version 2.0.0 under policy
`ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`.
For `CURRENT_COMPONENT_SUM`, it returns `n_optical_generated_total` as the
arrival and G4S-03 collection-efficiency denominator. Current contract blob
`fb201f7b2be40db7b28f5d713cc0adb7aa03fd78` already documents that behavior.

Thus a successful current adapter run emits a machine-readable record that
contradicts both the consumer code and the current contract documentation.
The actual remaining blocker is immutable real-ROOT end-to-end execution, not
an unimplemented analyzer denominator correction.

## Better metadata contract

The adapter must be versioned and publish:

```json
{
  "analysis_compatibility": "SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE",
  "downstream_analyzer_contract": {
    "version": "2.0.0",
    "policy": "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL",
    "optical_generation_contract": "CURRENT_COMPONENT_SUM",
    "collection_efficiency_denominator": "n_optical_generated_total",
    "acceptance": "SOFTWARE_CONTRACT_VALIDATED_REAL_ROOT_PENDING"
  }
}
```

The stale downstream blocker must be removed. The scientific boundary must
remain explicit: no immutable current production ROOT bytes have completed the
adapter-to-analyzer path with producer sidecar/commit, input and normalized
hashes, row-count closure, result/manifest hashes, and reviewed diagnostics.

## Files delivered

- `tools/audit/audit_single_stave_adapter_analyzer_metadata.py`
- `tests/test_audit_single_stave_adapter_analyzer_metadata.py`
- `tools/audit/render_single_stave_adapter_analyzer_metadata_evidence.py`
- `docs/validation/single_stave_adapter_analyzer_metadata_validation.json`
- `docs/validation/single_stave_adapter_analyzer_metadata.svg`
- `docs/validation/single_stave_adapter_analyzer_metadata_audit.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`
- this immutable archive
- updated latest handoff

## Validation

```text
python -m py_compile \
  tools/audit/audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py \
  tools/audit/render_single_stave_adapter_analyzer_metadata_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py

6 passed, 1 skipped in 1.96s
```

The corrected fixture returned `VALIDATED` with zero findings. The current-like
stale fixture failed closed. Tests also cover analyzer denominator mutation,
missing contract statements, invalid UTF-8, atomic JSON publication, and
destructive output aliasing. JSON and SVG parsing passed; changed Python lines
are no longer than 100 characters.

The skipped integration check requires the full current repository checkout.
This container cannot resolve `github.com`; exact current Git blob identities
and relevant line ranges are retained in the JSON. No claim is made that the
current-source CLI audit was executed in a complete checkout.

## Direct-main sequence before handoff

- `59990feccc0cf23cabe6d3295c6228c2dc35a598` — audit gate
- `b788cc0da886f13d180c25fabba7bfa2864b2484` — focused tests
- `d051d6a65e7ea92ec3f9325fa6756dacdeed45c7` — evidence renderer
- `4ef86f09eb19ee244ae52dd1947e28e4a9d5c051` — machine-readable evidence
- `d3137782ae17fb83fa8910ad4d1af08e1aa74e98` — visual evidence
- `5ff3edb0a85f83c76892c59d21128b1e27d860f3` — audit report
- `b4e732224bf61ebe23d6579fb98fd35920b6aedf` — active-task update

The connector returns commit SHAs rather than conventional `git push` stdout.
A post-write history check must confirm the final handoff on remote `main`.

## Checks not run

Repository-wide pytest/ruff, exact-current-source integration pytest in a full
checkout, repository-wide link inventory, Geant4 build/CTest, immutable ROOT
execution, and GitHub Actions were not run. No broad CI or physics-closure claim
is made.

## Coordination boundary

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed. They were not replaced in this run because the connector
exposes whole-file replacement and the complete current long-lived contents
were only available through paged/truncated responses. Replacing an incomplete
reconstruction could erase unrelated append-only provenance. This immutable
record and the latest handoff provide the append-equivalent session record; the
mandatory aggregate synchronization gap remains explicit.

## Scientific boundary and next gate

No Geant4 event, ROOT file, optical yield, calibration, resolution, PID, or
detector-performance quantity was generated or changed.

`AUD-G4-023` remains `PARTIAL`. The next focused unit must update adapter
metadata/version, remove the obsolete blocker, add an exact CLI regression, run
the audit against exact current source in a complete checkout, and require zero
findings. Immutable real-ROOT execution remains a separate acceptance gate.
