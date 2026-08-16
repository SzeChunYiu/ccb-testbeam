# ADR-1079: Birks kB parameter contract

## Status

**PARTIAL / BLOCKED for canonical physical kB selection**

## Context

Python digitizer used an implicit `birks_quench` default (0.008 cm/MeV) while
Geant4 single-stave defaults to 0.126 mm/MeV and Chapter-10 prose discusses
kB=0. These are distinct quenching worlds.

## Decision

1. Production digitizer paths require explicit `birks_kB_mm_per_MeV` whenever
   `apply_birks=True` (canonical unit aligned with Geant4 `AppConfig`).
2. Convert to cm/MeV only at the `birks_quench` call boundary.
3. Reject configs that label the API boundary as cm/MeV without conversion.
4. Persist requested/effective kB and `quenching_model_id` in waveform provenance.
5. **Do not invent** which numerical kB is the CCB detector truth. Material-
   bound selection awaits #1000 / calibration evidence (#1008 owns model-form
   uncertainty separately).

## Consequences

Cross-implementation numerical closure is testable for a shared first-order
law once both sides are given the same explicit kB. Physical default selection
remains BLOCKED.
