# ADR-0004: Birks / fibre-clad / observation-window contradictions as versioned hypotheses

**Status:** accepted (infrastructure); physical closure **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 05  
**Issues:** #1008, #1090, #1094 (related #994, #1000, #1014)

## Context

Independent surfaces silently treat incompatible response assumptions as truth:

| Axis | Claim A | Claim B | Issue |
|---|---|---|---|
| Quenching model form | Geant4 Birks `kB=0.126 mm/MeV` as production light response | Literature multi-model (Birks/Chou/Wright/Voltz); kB scan ≠ model-form test | #1008 |
| Fibre outer cladding | Optical `n=1.42` labelled fluorinated PMMA | Transport density/composition still PMMA `1.19 g/cm3` vs representative fluorinated `1.43 g/cm3` | #1094 |
| Observation window | All-time Geant4 Edep/PE counters | SiPM production ADC gated to representative `[-20, 250] ns` | #1090 |

Silently picking one side would bake the wrong light yield, material budget, or
calibration denominator into PID/energy claims.

## Decision

1. **Do not resolve** Birks/material/window contradictions by choosing preferred numbers in code.
2. Publish each side as a **named HYPOTHESIS profile** under `configs/response/`
   (`registry_version: 2026.0-waveB-lane05`).
3. **Fail closed** when quenching / fibre-clad / observation-window profile ids
   are unset (`ccb_mc_validation.response.registry`).
4. Profiles with `status: HYPOTHESIS` have `claims_authorized: false`.
5. Persist observation semantic class `FULL_TRANSPORT` vs `ACQUISITION_WINDOW`
   and refuse unmatched calibration ratios unless explicitly opted in.
6. Promote to `APPROVED` only after material identity (#1000), fibre lot ledger
   (#1094), and hardware time axis (#1014) close; bump `registry_version`.

## Consequences

- Runs must declare which response hypotheses they assume.
- Nominal Birks is explicitly **not** “validated p/d light-response truth”.
- Physical acceptance for #1008/#1090/#1094 remains **BLOCKED** pending evidence.
