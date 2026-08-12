# ADR-0005: Outer WLS cladding material identity mismatch

**Status:** **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 02  
**Issues:** #1094 (related #1000, #986, #1092, #1093)

## Context

`DetectorConstruction::BuildFibreOuterClad()` builds `CCB_FibreOuterClad` from
`G4_PLEXIGLASS` at density `1.19 g/cm3` (PMMA) while setting optical `RINDEX`
to `n=1.42` (fluorinated-polymer optical target). Kuraray’s public plastic
scintillating-fibre material table distinguishes PMMA cladding
(`n_D≈1.49`, density `1.19 g/cm3`) from fluorinated outer cladding
(`n_D≈1.42`, density `1.43 g/cm3`).

Optical-index agreement is **not** charged-particle material agreement:
density and composition enter dE/dx, scattering, and secondaries whenever a
track crosses the cladding.

The installed CCB Y-11 fibre type/lot/cladding construction is not recovered
in-repo. Replacing `1.19` with Kuraray’s representative `1.43` without that
evidence would invent a hardware-truth number.

## Decision

1. Keep the current transport material as an explicit **mismatch hypothesis**:
   - `fibre_outer_clad_material_id = pmma_density_fluorinated_index_MISMATCH`
   - `fibre_outer_clad_material_status = BLOCKED_UNVERIFIED_FIBRE_LOT`
2. Do **not** silently retune density/composition to catalogue values.
3. Optional future named hypotheses may be added only with cited sources and
   `claims_authorized=false` until the installed fibre ledger is filled.
4. Elevate severity if expanded phase-space scans (#1092/#1093) show frequent
   cladding crossings that move authorised observables.

## Rejected shortcuts

- Treating `n=1.42` as sufficient material identity for charged-particle
  transport.
- Copying Kuraray representative density `1.43 g/cm3` into production as CCB
  truth without fibre type/lot evidence.

## Consequences

- Charged-particle claims that depend on cladding mass remain non-authorising.
- Closing #1094 requires recovering the installed fibre specification (or a
  dedicated material measurement) and then rebuilding the outer-clad material
  from that ledger.
