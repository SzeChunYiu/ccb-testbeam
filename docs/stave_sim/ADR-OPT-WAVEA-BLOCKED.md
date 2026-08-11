# ADR-OPT-WAVEA: Optical / WLS / material atoms — Lane 02 Wave A

**Status:** partially accepted (fail-closed optical validation) + **BLOCKED** for unverified hardware composition/coupling  
**Date:** 2026-08-11  
**Branch:** `fix/lane02-waveA`  
**Issues:** #978 #979 #980 #996 #1000 #1005 #1035 #1036 #1085 #1086 #1088

## Decision

1. **Fail-closed optical tables are production default** (#978 #980 #996).
   - `AppConfig::strict_optical = true` by default.
   - Permissive path requires `--allow-optical-fallback` / `CCB_ALLOW_OPTICAL_FALLBACK=1` and forces `authorising=false`.
   - Semantic unit/range validation rejects wrong units, out-of-range fractions/lengths, malformed rows, extra tokens, and duplicate wavelengths before event 0.
   - Action-level `sipm_pde` uses the same strictness; empty PDE no longer silently becomes 40% in authorising runs.

2. **Hard-coded optical scalars move into a versioned ledger** (#979 #1088 #1086).
   - `geant4/single_stave/optical/optical_constants_ledger.conf` sources RINDEX/yield/timing/WLS multiplicity/TiO2 UNIFIED constants.
   - `WLSMEANNUMBERPHOTONS` is explicit; default unit-yield is labelled `ASSUMPTION_UNIT_YIELD`, not detector truth.
   - TiO2 finish is `ground` (valid for `dielectric_metal`) with explicit UNIFIED lobe/spike/backscatter constants (`EXPLICIT_LAMBERTIAN_HYPOTHESIS` when zeros).

3. **Unverified materials/coupling remain BLOCKED hypotheses** (#1000 #1005 #1035 #1036 #1085).
   - Do **not** invent CCB-true compositions. Named CLI/config hypotheses are available for nuisance scans; production metadata records status strings below.
   - Closing these atoms requires hardware/construction evidence or a dedicated measurement campaign.

## BLOCKED atoms (evidence gap)

| Issue | Atom | Current production posture | Status label |
|---|---|---|---|
| #1000 | Scintillator base polymer/density | default `polystyrene_legacy`; optional `vinyltoluene_pvt_hypothesis` | `BLOCKED_UNVERIFIED_HARDWARE` |
| #1005 | 0.25 mm coating charged-particle mass | default `air_massless_placeholder`; optional `tio2_paint_hypothesis` | `BLOCKED_UNVERIFIED_HARDWARE` |
| #1035 | Direct Y-11 charged-particle scintillation | default yield 0 (historic omission); optional nonzero hypothesis | `OMISSION_UNKNOWN_EXTERNAL` |
| #1036 | Fibre–scintillator coupling fill | default `optical_interface_model=UNKNOWN_EXTERNAL` (air annulus); grease/epoxy/bonded install catalogue-index hypotheses | `UNKNOWN_EXTERNAL` / `HYPOTHESIS_CATALOGUE_NOT_CCB_HARDWARE` |
| #1085 | Y-11 attenuation model form | long-component single exponential over full stave | `MANUFACTURER_LONG_COMPONENT_PRIOR` (short-distance form BLOCKED) |
| #1088 | Y-11 fluorescence quantum yield | explicit `WLSMEANNUMBERPHOTONS` with assumption status | `ASSUMPTION_UNIT_YIELD` until source-bound |

## Authorising rule

A run may be labelled `authorising=true` only when:

- `strict_optical=true`,
- no optical-table fallback was used,
- and consumers treat BLOCKED/HYPOTHESIS/ASSUMPTION status fields as non-closure for the corresponding physics claim.

## Rejected shortcuts

- Silent percent↔fraction or Å↔nm conversion.
- Silent 40% PDE fallback under strict/authorising mode.
- Calling polystyrene “BC-408 equivalent” without a quantified transport study.
- Treating catalogue grease/epoxy indices or pure-TiO2 density as CCB hardware truth.
