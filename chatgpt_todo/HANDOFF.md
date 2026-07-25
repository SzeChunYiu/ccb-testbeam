# Latest Handoff — AUD-G4-023 adapter metadata remediation

## Delivery identity

- **Session stamp:** `2026-07-25T160331Z`
- **Initial remote `main`:** `1e284f8109e927aea67d0eaf2246477982a6dcc7`
- **Validated implementation/evidence/archive head:**
  `a3d1e23e29e6578df0f5db2607710d1b3a65cd7b`
- **Destination:** direct contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport
- **Focused remediation acceptance:** `VALIDATED`
- **Cumulative task status:** `PARTIAL`
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T160331Z_AUD-G4-023_ADAPTER_METADATA_REMEDIATION.md`

## Start-of-run state

The run fetched current `main`, confirmed head
`1e284f8109e927aea67d0eaf2246477982a6dcc7`, reviewed recent history, open PRs,
PR #868, current status checks, repository instructions, the latest handoff and
active task, backlog, blockers, session history, the adapter, analyzer,
`EVENT_CONTRACT.md`, focused tests, and prior validation evidence.

PR #868 remains closed, unmerged, and non-mergeable and was not modified. No
status checks were attached to the initial head.

## Confirmed defects

The pre-remediation adapter blob
`d7b1e797188ea4d20de9a010d040eb578908d418` already retained the scintillation,
WLS, and Cerenkov counters, constructed `n_optical_generated_total`, and used it
for the selected-arrival bound. Its metadata nevertheless published
`SCHEMA_ADAPTER_ONLY` and a stale blocker claiming the current analyzer still
used `n_scint_generated` alone.

A second defect was found in the audit gate. Version 1.0.0 used literal
substring checks for contract prose. The exact current document wraps
`Analyzer version` and `2.0.0` across a newline, so the old gate rejected correct
wrapped prose. The corrected gate collapses whitespace before phrase matching.

## Remediation delivered

- `scripts/single_stave/adapt_geant4_events.py` is version `1.1.0` and publishes
  schema `ccb-single-stave-event-adapter/2`.
- Compatibility is now
  `SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE`.
- `downstream_analyzer_contract` records analyzer version `2.0.0`, policy
  `ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`, contract
  `CURRENT_COMPONENT_SUM`, denominator `n_optical_generated_total`, and
  acceptance `SOFTWARE_CONTRACT_VALIDATED_REAL_ROOT_PENDING`.
- The obsolete blocker was removed. A separate scientific-boundary field retains
  the immutable real-ROOT end-to-end requirement.
- The audit gate is version `1.1.0` and normalizes whitespace in contract prose.
- Added `tests/test_adapt_geant4_events_metadata_contract.py` and updated the
  exact-current audit integration expectation.
- Regenerated machine-readable JSON, SVG evidence, and the audit report.

## Validation

```text
python -m py_compile \
  scripts/single_stave/adapt_geant4_events.py \
  tools/audit/audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_adapt_geant4_events.py \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_adapt_geant4_events_metadata_contract.py \
  tools/audit/render_single_stave_adapter_analyzer_metadata_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_adapt_geant4_events.py \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_adapt_geant4_events_metadata_contract.py

20 passed, 1 skipped in 3.77s
```

The skip is the existing `RunAction.cc` branch-name integration check because
the isolated fixture did not contain the Geant4 source tree. The adapter CLI
metadata regression executed and passed. The adapter/analyzer/contract audit
returned `VALIDATED` with zero findings. JSON and SVG parsing passed. Changed
Python files are at most 100 characters per line.

## Direct-main sequence

- `e301d9283075c57c41ba2aabf6eab696b046a7b0` — adapter metadata remediation
- `9147fb1c622a3b6f3ff9e64115c7bd6e63929091` — whitespace-safe audit gate
- `67c29fe1cb5404610c5b5085d14d6fb0f4211486` — current-source audit tests
- `65f3b856a292d4a24c2b153b86ceb49f956ca661` — adapter CLI metadata regression
- `1ae8c916e5be2606ff6ea6751fce26810ec48d14` — machine-readable evidence
- `94dd19a1ddb1eb5d9c4dda4f1e722ebd08e5a75d` — SVG evidence
- `f9ab5666ab37078ee320a031f9b82ffac50daa3a` — audit report
- `80bb4e37ed2ffa892f1cfaa1e3a856f2fa28487a` — active-task update
- `a3d1e23e29e6578df0f5db2607710d1b3a65cd7b` — immutable archive

The connector returns successful commit SHAs rather than conventional textual
`git push` output. A post-write history read must confirm this handoff and all
focused predecessors on remote `main`.

## Scientific boundary

This is software and provenance validation. No immutable production ROOT bytes,
Geant4 event, optical yield, calibration, resolution, PID, or detector-
performance result was produced. `AUD-G4-023` remains `PARTIAL` until the full
adapter-to-analyzer path is executed with producer sidecar/commit, exact input
and normalized hashes, row-count closure, result/manifest hashes, and reviewed
diagnostics.

## Checks not run

Repository-wide pytest/ruff, Geant4 build/CTest, immutable ROOT execution,
repository-wide link inventory, and GitHub Actions were not run. No broad CI or
physics-closure claim is made.

## Coordination boundary

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector exposes whole-file
replacement rather than byte-safe append/patch semantics, and the current
append-only history was available only through truncated pages. Replacing a
partial reconstruction could erase unrelated provenance. The immutable archive
and this handoff are the append-equivalent record; mandatory aggregate
synchronization remains an explicit governance gap.
