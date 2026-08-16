# Single-stave Geant4 event-contract audit

- **Task:** `AUD-G4-022`
- **Session:** `2026-07-25T133443Z`
- **Initial `main`:** `2f653429c2b7ead1d35752a23f3bb908506dd23d`
- **Policy:** `CURRENT_GEANT4_EVENT_TREE_MUST_MAP_EXPLICITLY_TO_ANALYSIS_CONTRACT`
- **Focused status:** `VALIDATED`
- **Cumulative task status:** `PARTIAL`

## Confirmed repository mismatch

The current producer writes `event`, `particle`, `ke_MeV`,
`arrival_readout`, `detected_readout`, and `track_len_scint_mm`. The published
analyzer requires `event_id`, `particle_pdg`, `kinetic_energy_MeV`,
`n_end_selected`, `n_detected_pe`, and `track_length_scint_cm`. Its alias table
mapped `event` and `ke_MeV`, but not the two current readout branches or the
track-length unit conversion.

The analyzer also used the scintillation-only count as an upper bound for all
selected-end arrivals. The current producer separately records scintillation,
WLS, and Cerenkov generated optical tracks. Geant4's optical-physics
configuration treats these as distinct optical processes, so the auditable
bookkeeping bound is the explicit sum of the tracked categories, not the
scintillation component alone.

## Engineering correction

Added `scripts/single_stave/adapt_geant4_events.py` with an explicit branch map,
strict finite/count validation, selected-sensor semantics, mm-to-cm conversion,
input identity checks, atomic outputs, and machine-readable provenance. The
adapter adds `n_optical_generated_total` and validates arrivals against that
sum. It does not fuzzy-match branch names or silently choose between source and
normalized columns.

Added `scripts/single_stave/EVENT_CONTRACT.md` and a source-bound regression
suite. The adapter deliberately labels itself `SCHEMA_ADAPTER_ONLY`, because the
legacy analyzer still applies the scintillation-only inequality internally.
This prevents the conversion layer from being mistaken for end-to-end
scientific acceptance.

The public Geant4 README was corrected at commit
`39d9dc0aacccc93d2e4d0ae86ef5da8d58c1f4c1`. It no longer states that the
current ROOT file can be analyzed directly, no longer presents `--mode fast` as
implemented, and links the explicit contract and converter. The corrected
README Git blob is `a0d2cc0ab61562ba9c6d58dcc9bb53fcdba9f3d0`.

## Validation

```text
python -m py_compile \
  scripts/single_stave/adapt_geant4_events.py \
  tests/test_adapt_geant4_events.py \
  tools/audit/render_single_stave_event_contract_evidence.py

pytest -q tests/test_adapt_geant4_events.py

12 passed in 1.62s
```

Controls cover exact current-branch mapping, particle mapping, track-length unit
conversion, WLS-inclusive generated-track accounting, invalid count ordering,
nonfinite/fractional/negative counts, ambiguous columns, duplicate keys,
atomic publication, destructive aliases, and overwrite protection. Changed
Python files obey the repository's 100-character line convention. The
validation JSON parsed and the SVG parsed as XML.

## Evidence identities

The validation record binds:

- producer Git blob `2e10565aa41182618083634cd18b6ddae89660da`;
- analyzer Git blob `5a3fdd88757bec8b8f39b2ca9f7be889b70e848c`;
- exact adapter, test, renderer, event-contract documentation, and audit
  SHA-256 values in `single_stave_event_contract_validation.json`;
- corrected public README Git blob
  `a0d2cc0ab61562ba9c6d58dcc9bb53fcdba9f3d0`.

## Scientific boundary and next gate

This is synthetic software and provenance validation. No real ROOT sample was
opened, no Geant4 event was generated, and no optical yield, calibration,
resolution, PID, or detector-performance quantity was measured.

Completion requires changing the analyzer itself to consume and report the
component and total optical counters without semantic renaming, adding an
integrated current-ROOT regression, and executing the complete path on an
immutable production ROOT file with input/output hashes and row-count closure.
