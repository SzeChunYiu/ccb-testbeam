# Immutable handoff — AUD-G4-023 adapter metadata remediation

- Session: `2026-07-25T160331Z`
- Initial remote main: `1e284f8109e927aea67d0eaf2246477982a6dcc7`
- Validated implementation/evidence head: `80bb4e37ed2ffa892f1cfaa1e3a856f2fa28487a`
- Task: correct the adapter's stale analyzer metadata and validate the exact
  current contract.
- Result: focused software remediation `VALIDATED`; cumulative task `PARTIAL`.

## Findings

1. Adapter v1.0.0 already produced the current component-sum event contract but
   labelled itself `SCHEMA_ADAPTER_ONLY`.
2. It published an obsolete blocker saying the analyzer still used
   `n_scint_generated` alone.
3. The audit gate was whitespace-sensitive and rejected the exact wrapped
   `EVENT_CONTRACT.md` statement even when its meaning was correct.

## Changes

- adapter version `1.1.0`, metadata schema
  `ccb-single-stave-event-adapter/2`;
- compatibility `SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE`;
- exact downstream analyzer version, policy, optical contract, denominator, and
  acceptance boundary;
- stale blocker removed and real-ROOT scientific boundary retained;
- audit version `1.1.0` collapses whitespace before prose checks;
- CLI and audit regressions updated;
- JSON, SVG, and Markdown evidence regenerated.

## Validation

```text
PYTHONPATH=. pytest -q \
  tests/test_adapt_geant4_events.py \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_adapt_geant4_events_metadata_contract.py

20 passed, 1 skipped in 3.77s
```

The skip is the pre-existing `RunAction.cc` source-tree integration check in the
isolated fixture. The executable adapter CLI metadata regression and exact
adapter/analyzer/contract audit passed. Audit status: `VALIDATED`, zero findings.

## Scientific boundary

No production ROOT bytes, Geant4 events, optical yield, calibration, resolution,
PID, or detector-performance result was produced. Completion requires immutable
real-ROOT adapter-to-analyzer execution with producer sidecar/commit, exact
input/output hashes, row-count closure, result/manifest hashes, and reviewed
plots.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector exposes whole-file
replacement rather than byte-safe append/patch semantics, and the current
append-only history is too large to reconstruct safely from truncated pages in
this run. This archive and the latest handoff preserve the complete session
record without risking unrelated provenance.
