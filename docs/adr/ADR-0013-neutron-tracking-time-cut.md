# ADR-0013: Implicit QGSP_BIC neutron tracking-time cut is BLOCKED until measured

**Status:** accepted (BLOCKED physics claim)  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 09  
**Issues:** #1091

## Context

QGSP_BIC may kill neutrons after an implicit ~10 µs tracking-time cut that the
single-stave application neither configures nor records. Full-event Geant4 truth
(all-time Edep/light) can therefore inherit an undocumented late-neutron boundary
distinct from the SiPM acquisition window (#1090) and production cuts (#1089).

## Decision

1. Do **not** invent a CCB-specific neutron time cut or declare delayed neutrons
   negligible without a sensitivity study.
2. Run metadata records
   `neutron_tracking_time_cut_us=IMPLICIT_QGSP_BIC_DEFAULT_10_UNVALIDATED` and
   `neutron_tracking_time_cut_status=BLOCKED_ISSUE_1091`.
3. Any authorising claim that depends on late neutron capture/activation/pile-up
   must fail closed via the Python gate until an explicit configured cut and
   measured sensitivity exist.
4. Competing hypotheses (remove cut; set cut equal to DAQ window; keep 10 µs as
   named legacy) remain open.

## Consequences

- Software provenance is honest; physics remains BLOCKED.
- No auto-close of #1091.
