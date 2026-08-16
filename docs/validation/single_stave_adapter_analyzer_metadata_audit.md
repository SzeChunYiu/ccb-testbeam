# Single-stave adapter/analyzer metadata remediation audit

## Scope and evidence class

This is a software and provenance validation unit for `AUD-G4-023`. It does not
contain detector data and does not establish an optical yield, calibration,
resolution, PID, or detector-performance result.

Initial remote `main` was
`1e284f8109e927aea67d0eaf2246477982a6dcc7`. The inspected pre-remediation
adapter blob was `d7b1e797188ea4d20de9a010d040eb578908d418`.

## Confirmed metadata defect

The adapter already retained scintillation, WLS, and Cerenkov generated-track
counts, constructed `n_optical_generated_total`, and rejected selected-end
arrivals above that total. Its metadata nevertheless published
`SCHEMA_ADAPTER_ONLY` and a stale blocker claiming that the analyzer still used
`n_scint_generated` alone.

The current analyzer is version 2.0.0 under policy
`ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`. For the
`CURRENT_COMPONENT_SUM` contract it uses `n_optical_generated_total` as the
arrival bound and the G4S-03 collection-efficiency denominator.

## Additional validator defect found

The audit gate used literal substring matching on `EVENT_CONTRACT.md`. The exact
current document wraps `Analyzer version` and `2.0.0` across a newline. The
former validator therefore rejected the correct current contract even after the
adapter metadata was fixed. Version 1.1.0 now lowercases and collapses all
whitespace before checking the two contract statements. A focused regression
covers wrapped prose.

## Remediation

`adapt_geant4_events.py` is now version 1.1.0 and writes schema
`ccb-single-stave-event-adapter/2`. Its metadata publishes:

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

The obsolete analyzer blocker was removed. A separate `scientific_boundary`
field preserves the real remaining gate: immutable production ROOT execution
with producer sidecar/commit, input and normalized hashes, row-count closure,
result/manifest hashes, and reviewed diagnostics.

## Validation

Executed on the reconstructed exact changed files and the current analyzer
contract semantics:

```text
python -m py_compile \
  scripts/single_stave/adapt_geant4_events.py \
  tools/audit/audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_adapt_geant4_events.py \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py \
  tools/audit/render_single_stave_adapter_analyzer_metadata_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_adapt_geant4_events.py \
  tests/test_audit_single_stave_adapter_analyzer_metadata.py \
  tests/test_adapt_geant4_events_metadata_contract.py

20 passed, 1 skipped in 3.77s
```

The skip is the existing `RunAction.cc` branch-name integration check because
the isolated validation fixture did not contain the Geant4 source tree. The
adapter CLI test executed and verified the complete metadata payload, output
hashing, atomic publication, current analyzer contract, absence of the stale
blocker, and the retained real-ROOT boundary.

The exact-source metadata audit returned `VALIDATED` with zero findings. JSON
parsing and SVG XML parsing passed. Changed Python files are at most 100
characters per line.

## Acceptance state

The focused software remediation is `VALIDATED`. `AUD-G4-023` remains `PARTIAL`
scientifically until the immutable real-ROOT adapter-to-analyzer path is run and
reviewed. No Geant4 event or ROOT file was generated in this unit.
