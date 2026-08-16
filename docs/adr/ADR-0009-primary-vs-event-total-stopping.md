# ADR-0009: Primary vs event-total scintillator path length

**Status:** accepted (estimator split); historical event-total field retained  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 05  
**Issues:** #1007

## Context

`track_len_scint_mm` / `edep_scint_*` accumulated **all** non-optical tracks in
the scintillator while comments claimed “primary path length”. PSTAR is a
single-particle stopping-power reference; secondary contamination changes the
measurand.

## Decision

1. Keep event-total columns for calorimetric bookkeeping.
2. Persist primary-only columns (`ParentID==0`):
   `primary_track_len_scint_mm`, `primary_edep_scint_raw_MeV`,
   `primary_edep_scint_MeV`.
3. Stopping-power validators prefer primary columns when present and annotate
   `track_length_scope`.
4. PSTAR `physics_comparable` requires `pstar_primary_identity_ok`.
5. Authorizing helpers refuse event-total scope (`require_primary_scope_for_pstar`).

## Consequences

- Legacy CSVs with only event-total columns remain readable as diagnostics but
  are not PSTAR-identity comparable.
- Rebuild of `ccb_stave_sim` is required for new ntuple columns to appear.
