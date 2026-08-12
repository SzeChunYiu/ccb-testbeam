# Latest Handoff

## Compiled ccb-sipm-core source revision is now bound into the producer executable

Selected atom: `ARU-SIPM-RUN-METADATA-COMPILED-CORE-SHA-001`.

PR #1280 has integrated the bounded source-revision provenance repair. Exact final branch head `9389bd4485ac2af5df0f6420606ea4be8e9ecb7f`, based on protected `main@896c6c0bca2fa0d5fdf50a5d33840e4b8ab75b60`, passed both final-head MC Validation contexts and squash-merged as protected `main@21de9a79cd32a2ecbc4005381c96322367ef3800`. The reviewed SiPM gitlink remains `ccb-sipm-core@3627dc87137a9f33f511a755671414b11853c0a0`.

The defect was that `RunAction::WriteMetadataSidecar()` serialized `digitizer.ccb_sipm_core_commit` from mutable caller environment `CCB_SIPM_CORE_COMMIT`, falling back to `unspecified`, while the systematic launcher did not set that variable. The same metadata block advertised `validation_status=OK`, and `sipm_sensitivity.py` accepted `OK` plus a nonempty config digest without requiring exact core identity. A numerical config/effective-kernel digest cannot substitute for implementation identity because the core source revision is not an input to that digest.

The bounded contract is `H_meta = H_compiled = H_link`. `SipmBuildProvenance.hh` contains the exact reviewed lowercase 40-hex core gitlink. `SipmBuildProvenance.cc` is linked automatically through the existing `src/*.cc` CMake glob and, before `main()`, overwrites the legacy environment bridge from that compiled literal; inability to install the binding aborts before event 0. The regression compares the compiled literal to `git ls-tree HEAD geant4/single_stave/sipm`, compiles/runs the binding translation unit under hostile `CCB_SIPM_CORE_COMMIT=deadbeef`, and guards the CMake composition assumption.

The final-head push validation run `31561698833` checked out exact `9389bd...`, recursively materialized exact core `3627dc...`, passed the core conflict-marker guard, configured and built with GNU C++ 13.3.0, and passed all 7 core CTests. Ruff reported `All checks passed!`. Full non-integration pytest reported `2118 passed, 2 skipped, 8 xfailed, 1 xpassed, 18 warnings in 125.18s`; final enforcement reported SiPM-core, ruff and pytest status 0. Pull-request run `31561716054` independently completed `SUCCESS` on the same final head. The earlier isolated local C++17 hostile-env probe also printed exact `3627dc...`; that local probe is supportive software evidence only.

The four sequential AI reviews remain: **detector-response/provenance lead** `ACCEPT bounded child VALIDATED / BLOCK #977 COMPLETE`; **adversarial mechanism reviewer** `REJECT caller-env/config-digest equivalence / ACCEPT compiled literal`; **independent validation reviewer** `ACCEPT exact-head protected CI / BLOCK detector inference`; **claims/provenance reviewer** `ACCEPT source-revision repair / BLOCK waveform, measured-electronics and detector-performance promotion`.

#977 and #1067 are deliberately reopened and remain `OPEN/PARTIAL`. This child does not establish a compiler/linker/build-input or executable-byte manifest, positive measured-electronics calibration authorization, requested-to-effective operating-point closure, downstream analysis admission, or validity of historical sidecars. Independent post-merge main-push run `31561985291` started on exact `21de9a79...`; its success must be verified separately before citing a post-merge-main execution result.

Archive: `chatgpt_todo/archive/2026-08-12T035600Z_ARU-SIPM-RUN-METADATA-COMPILED-CORE-SHA-001.md`.

Next highest-value child: `ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001`. The analysis consumer must fail closed when exact core execution identity is absent/inconsistent rather than accepting `validation_status=OK` plus a config digest. Separate children remain for historical sidecar audit and full binary/build-manifest provenance.

No beam bytes, production Geant4 detector population, measured electronics waveform/calibration, DATA↔MC result, timing/PID metric, pile-up efficiency, rate, ESS, p-value, or detector-performance quantity was generated or promoted.
