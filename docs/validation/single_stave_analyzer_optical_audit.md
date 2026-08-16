# Single-stave analyzer optical-bookkeeping remediation audit

- **Task:** `AUD-G4-022`
- **Session:** `2026-07-25T141517Z`
- **Initial remote main:** `48e3192dc69dd8c9408930171ed66f7a0627979e`
- **Policy:** `ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`
- **Acceptance:** `VALIDATED` for synthetic software/bookkeeping remediation; real-ROOT closure remains open.

## Confirmed defect

The former analyzer blob `5a3fdd88757bec8b8f39b2ca9f7be889b70e848c`
checked `n_end_selected <= n_scint_generated` and divided the G4S-03
collection-efficiency observable by `n_scint_generated`. The current producer
blob `2e10565aa41182618083634cd18b6ddae89660da` records separate scintillation,
WLS, and Cerenkov optical-track counters. A valid current event may therefore
have more readout arrivals than scintillation-created tracks while remaining
below the total created optical tracks.

Synthetic control:

```text
n_scint_generated = 10
n_wls_generated = 5
n_cerenkov_generated = 0
n_optical_generated_total = 15
n_end_selected = 11
```

The former ratio was `11/10 = 1.1`; the correct current-contract ratio is
`11/15 = 0.7333333333333333`.

## Correction

Analyzer version 2.0.0 now:

1. preserves all three component counters and the declared total;
2. rejects partial current contracts;
3. rejects nonfinite, negative, and fractional counts;
4. verifies the exact row-wise component sum;
5. bounds arrivals by `n_optical_generated_total` for current-contract input;
6. labels old tables `LEGACY_SCINTILLATION_ONLY` rather than silently treating
   them as current bookkeeping;
7. records the optical contract and denominator in validation, result JSON,
   summary CSV, and G4S-03 plot metadata/source data;
8. records input and output byte counts and SHA-256 values in the manifest.

The Geant4 README and event-contract documentation now describe the corrected
normalized path and retain the real-ROOT scientific boundary.

## Validation

```text
python -m py_compile \
  scripts/single_stave/analyze_single_stave.py \
  tests/test_analyze_single_stave_optical_contract.py \
  tools/audit/render_single_stave_analyzer_optical_evidence.py

PYTHONPATH=. pytest -q tests/test_analyze_single_stave_optical_contract.py

9 passed in 0.12s
```

A 120-row synthetic current-contract table also completed the full analyzer
path. `result.json` reported `PASS_SMOKE`, contract `CURRENT_COMPONENT_SUM`, and
G4S-03 denominator `n_optical_generated_total`; the G4S-03 source table carried
the same explicit metadata. JSON and SVG parsing passed. The maximum changed
Python line length is 100 characters. Ruff was not available in the execution
environment.

## Scientific boundary

This is synthetic software/provenance validation. No immutable production ROOT
file was available, no Geant4 event was generated, and no optical yield,
calibration, resolution, PID, or detector-performance quantity was measured or
changed. Completion of the cumulative task requires real adapter-to-analyzer
execution with producer sidecar, ROOT hash, row-count closure, normalized/result
hashes, and review of the generated diagnostics.
