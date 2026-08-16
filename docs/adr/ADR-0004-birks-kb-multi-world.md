# ADR-0004: Birks kB multi-world — no invented canonical value

**Status:** accepted (fail-closed)  
**Date:** 2026-08-11  
**Lane:** Wave C Lane 08  
**Issues:** #1079 (related: #1008, #979, #994, #1078)

## Context

At least three quenching parameter states exist in the repository:

| World | kB | Source |
|---|---|---|
| H1 | 0 | Chapter-10 MV0 prose after a scan |
| H2 | 0.008 cm/MeV (= 0.08 mm/MeV) | Python `birks_quench` helper default |
| H3 | 0.126 mm/MeV (= 0.0126 cm/MeV) | Geant4 single-stave `AppConfig` default |

These can all be legitimate hypotheses. They cannot all be "the" production
response model.

## Decision

1. `DigitizerPipeline` with `apply_birks=True` **requires** an explicit
   `birks_kB` + `birks_kB_unit` (`cm_per_MeV` or `mm_per_MeV`).
2. The pipeline must not silently use the `birks_quench` function default.
3. Canonical internal unit is **cm/MeV**; mm/MeV inputs are converted by `/10`.
4. This ADR does **not** choose H1/H2/H3. Authorising energy/PID claims remain
   blocked until a shared detector-property ledger (#979) and response-model
   identity (#1078) bind one world.
5. No `Fixes`/`Closes` auto-close of #1079 from this contract alone.

## Consequences

- Misconfigured Birks-on runs fail closed before event 0.
- Unit label errors (cm vs mm) become explicit rather than a silent 10× factor.
- Physics choice remains human/ledger-gated; software only enforces naming.
