# ADR-1007: Primary vs event-total stopping-power estimators

## Status

**PARTIAL / BLOCKED for authorising PSTAR closure**

## Context

Issue #1007: `track_len_scint_mm` / `edep_scint_raw_MeV` mixed all non-optical
tracks. Event-total Edep/path is not primary p/d stopping power.

## Decision

1. Persist distinct primary and all-particle fields in `EventData` / `events`
   ntuple (`primary_*`, `secondary_*`, `secondary_scint_activity`).
2. Legacy names remain **calorimetric / event-transport diagnostics only**.
3. Authorising PSTAR comparison requires `primary_*` estimators and
   `secondary_scint_activity=0` (`primary_local_edep_over_path_v1`).
4. Full regenerated stopping-power results remain **BLOCKED** until scintillator
   material identity (#1000) and hadronic/physics-list configuration (#1006)
   are resolved. No invented material or nuclear model is selected here.

## Consequences

- Schema and fail-closed gates land in this Wave B PR.
- Any public primary stopping-power claim without primary-field regeneration
  after #1000/#1006 is unauthorized.
