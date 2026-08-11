# ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001 — execution addendum

Status: **VALIDATED bounded upstream repair / preventive child OPEN**

This addendum supersedes the transient CI/merge status in the earlier checkpoint archive `2026-08-11T225800Z_ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001.md`.

## Final upstream execution evidence

- Broken core main inspected: `0fc78af6679c421f7a01a85f421170bbb92cce82`.
- Exact repair head: `98be281d3b48d4fe2fc2e00f985ec62374f07766`.
- Repair tree: `23beb8a7e1df3fc5d2bebc1e1c21e54c29d4ae2d`.
- Restored exact parent blobs:
  - `src/Config.cc` -> `7e4d84ec684d3b11eb3a7e1c6012fe22edfb53ba`;
  - `src/ResponseSimulator.cc` -> `51d5e74863d8075235fa27d4ad93f19c9a7565a7`;
  - `tests/test_core.cc` -> `3df1ea0d20bf93fbd10245791fb216ba1581f7ec`.
- Core PR #16 exact-head Core CI: run `31544391525`, job `93953654545`, conclusion **SUCCESS**; checkout, configure, build, Test/CTest all successful.
- PR #16 was marked ready only after that exact-head result, then squash-merged with expected head `98be281d...`.
- New remote core main: `caf6bdc592a05b55ae6bc343b4532a9934eb8344`, exact tree `23beb8a7...`.
- Independent post-merge main-push Core CI: run `31544689778`, job `93954555539`, conclusion **SUCCESS**; checkout, configure, build, Test/CTest all successful.

Therefore the bounded incident repair is validated at the C++ build/test and provenance-state level and is present on remote upstream main.

## Residual children

This does **not** close the material preventive child `ARU-CORE-MAIN-PROTECTION-001` (upstream core #17). Core main remains unprotected and still lacks an enforced exact-head required-check/conflict-marker gate. The bad merge witness proves that this is not an optional cleanup.

Root #1067 remains OPEN for physical measured-impulse source/calibration authorization, resampling closure and historical-output audit. Root #1066 is OPEN/PARTIAL after correcting its accidental completion state.

## Claim boundary

No root gitlink change was made in this atom; root main remained on the earlier conflict-free core lineage. No measured electronics calibration, beam data, production Geant4 sample, waveform performance, pile-up/saturation result, timing/PID metric, rate, ESS, p-value or detector-performance claim was generated or promoted.

## Final role votes

- Build/reproducibility lead: **ACCEPT bounded repair VALIDATED** — both exact-head and post-merge Core CI succeeded.
- Adversarial mechanism/provenance reviewer: **ACCEPT parent-blob resolution / REJECT PR #15 incoming conflict side**.
- Independent validation reviewer: **ACCEPT software execution closure / BLOCK detector inference**.
- Claims/provenance reviewer: **ACCEPT upstream quarantine repair / BLOCK #1067 completion and measured-electronics claims**.

Next scientific atom after this integrity repair: `ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`. Governance child #17 should proceed independently and must remain open until branch/ruleset enforcement is actually installed and exercised.
