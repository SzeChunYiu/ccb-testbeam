# Latest Handoff — AUD-G4-023 adapter/analyzer metadata consistency

## Delivery identity

- **Session stamp:** `2026-07-25T150441Z`
- **Initial remote `main`:** `9104fc1c0a6b1e3ce3323a08869444e1b68d6c16`
- **Validated implementation/evidence/archive head:**
  `920813e245c3bf74c585325d5e8e8a414a982101`
- **Validated delivery handoff / recorded after-SHA:**
  `80e82c451aac50147621073aa5a02a3f014e94df`
- **Destination:** direct contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport
- **Push result:** every contents write returned a successful commit SHA;
  post-write remote history confirmed `80e82c451aac50147621073aa5a02a3f014e94df`
  and all focused predecessors on `main`
- **Focused audit-gate acceptance:** `VALIDATED`
- **Current adapter metadata status:** `FLAWED`
- **Cumulative task status:** `PARTIAL`
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T150441Z_AUD-G4-023_ADAPTER_ANALYZER_METADATA.md`

## Start-of-run state

The run inspected current remote history and permissions, current status checks,
PR #868, open PRs, the latest handoff and active task, backlog and session log,
the current Geant4 event adapter, analyzer, event-contract documentation,
focused tests, and the immediately preceding event-contract/analyzer-remediation
history.

PR #868 remains closed, unmerged, and non-mergeable. It was not modified. No
active completed task was duplicated.

## Confirmed provenance defect

The current adapter blob `d7b1e797188ea4d20de9a010d040eb578908d418`
is version 1.0.0. Its normalized output already preserves scintillation, WLS,
and Cerenkov generated-track counts, constructs
`n_optical_generated_total`, and rejects selected-end arrivals above that total.
Its emitted metadata nevertheless still publishes:

- `analysis_compatibility = SCHEMA_ADAPTER_ONLY`; and
- a downstream blocker saying `analyze_single_stave.py` still validates
  arrivals against `n_scint_generated` alone and must be changed to use the
  total.

The current analyzer blob `4da04847bfb1e4c30aa8b8714624d9f5d7e8e8fd`
is version 2.0.0 under
`ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`.
For `CURRENT_COMPONENT_SUM` it uses `n_optical_generated_total` as the arrival
and G4S-03 collection-efficiency denominator. Current contract blob
`fb201f7b2be40db7b28f5d713cc0adb7aa03fd78` already documents that behavior.

Thus a successful adapter run emits a machine-readable record that contradicts
both its consumer code and the current documentation. The stale blocker also
obscures the actual remaining boundary: immutable real-ROOT end-to-end
execution.

## Better contract

The adapter metadata should be versioned and publish:

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

The obsolete blocker must be removed while retaining the real scientific
boundary: no immutable production ROOT sample has completed the full path with
producer sidecar/commit, input and normalized hashes, row-count closure,
result/manifest hashes, and reviewed diagnostics.

## Files delivered

- `tools/audit/audit_single_stave_adapter_analyzer_metadata.py`
- `tests/test_audit_single_stave_adapter_analyzer_metadata.py`
- `tools/audit/render_single_stave_adapter_analyzer_metadata_evidence.py`
- `docs/validation/single_stave_adapter_analyzer_metadata_validation.json`
- `docs/validation/single_stave_adapter_analyzer_metadata.svg`
- `docs/validation/single_stave_adapter_analyzer_metadata_audit.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`
- immutable archive listed above
- this handoff

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
stale fixture failed closed. Tests cover analyzer denominator mutation, missing
contract statements, invalid UTF-8, atomic JSON publication, and destructive
output aliasing. JSON and SVG parsing passed. Changed Python lines are at most
100 characters.

The skipped test is the exact-current-source integration check. The execution
container has no complete checkout and cannot resolve `github.com`; exact Git
blob identities and relevant line ranges are retained in the validation JSON.
No claim is made that the current-source CLI audit ran in a complete checkout.

## Direct-main sequence

- `59990feccc0cf23cabe6d3295c6228c2dc35a598` — fail-closed audit gate
- `b788cc0da886f13d180c25fabba7bfa2864b2484` — focused tests
- `d051d6a65e7ea92ec3f9325fa6756dacdeed45c7` — evidence renderer
- `4ef86f09eb19ee244ae52dd1947e28e4a9d5c051` — validation JSON
- `d3137782ae17fb83fa8910ad4d1af08e1aa74e98` — visual evidence
- `5ff3edb0a85f83c76892c59d21128b1e27d860f3` — audit report
- `b4e732224bf61ebe23d6579fb98fd35920b6aedf` — active-task update
- `920813e245c3bf74c585325d5e8e8a414a982101` — immutable archive
- `80e82c451aac50147621073aa5a02a3f014e94df` — complete handoff

The connector returns commit SHAs rather than conventional textual `git push`
stdout. Remote history confirmed the delivery handoff on `main`.

## Checks not run

Repository-wide pytest/ruff, exact-current-source integration pytest in a full
checkout, repository-wide link inventory, Geant4 build/CTest, immutable ROOT
execution, and GitHub Actions were not run. No broad CI or physics-closure claim
is made.

## Coordination boundary

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector exposes whole-file
replacement while their complete current long-lived contents were available
only through paged or truncated responses. Replacing a partial reconstruction
could erase unrelated append-only provenance. The immutable archive and this
handoff are the append-equivalent record; mandatory aggregate synchronization
remains an explicit governance gap.

## Scientific boundary and next gate

No Geant4 event, ROOT file, optical yield, calibration, resolution, PID, or
detector-performance quantity was generated or changed.

`AUD-G4-023` remains `PARTIAL`. The next focused unit must update adapter
metadata/version, remove the obsolete blocker, add an exact CLI regression, run
the audit against exact current source in a complete checkout, and require zero
findings. Immutable real-ROOT execution remains a separate acceptance gate.
