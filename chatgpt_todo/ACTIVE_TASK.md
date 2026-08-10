# Active Task

- **Task ID:** `ARU-MC-CS-WORKER-INIT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T180650Z`
- **Branch-point protected main:** `fa62e8bb6ce7de10f840ebfa016eaa40cd9f74ec` (PR #1180 source-table provenance validated and merged).
- **Parent implementation in flight:** PR #1181 exact head `edf71180b2f622b7cf16a8c1243d2140c2369eb9` implements the bounded deterministic inverse/support repair for #1178. MC Validation run `31415757686` succeeded, but a duplicate required `test` check (`31415753649`) remained in progress during this session; branch protection rejected the attempted squash merge and was not bypassed.
- **Selected atom:** generator configuration/readiness lifecycle `configured tables -> per-instance validated state -> BeamEnergy/SampleThetaCM -> primary event`.
- **Deterministic source finding:** `GeneratePrimaryVertex()` still uses `if(event->GetEventID()==0) LoadFiles();`; `BeamEnergy()->EvalELoss()` assumes populated stopping arrays; empty/inconsistent CDF state can become uniform `theta_cm`; required-file open failure uses `exit(0)`; cross-section `sscanf` conversion count is unchecked; there is no explicit idempotent per-instance readiness state.
- **Required state contract:** `UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`; configured source failure must never collapse into the explicit unconfigured uniform proposal.
- **Geant4 lifecycle boundary:** official Geant4 documentation makes event-zero unsuitable as a general worker-local initialization primitive because user actions are per worker in MT and event numbers handled by a worker are not sequential. The actual hibeam_g4 production run-manager/thread mode remains unresolved and must be bound from exact executable/build/runtime provenance before claiming this mechanism affected a historical run.
- **Repository work:** issue #1182 owns the runtime leaf; branch `audit/mc-source-readiness-contract` adds an executable static audit, focused tests, machine-readable result, immutable ARU archive, and coordination updates. The current static verdict is `BLOCK_RUNTIME_AUTHORIZATION` and is explicitly nonauthorising.
- **Claim state:** #1178 and CL-021 remain GATED for generator-runtime claims. #1179 remains the separate source statistical/systematic nuisance atom. #880/#1053 remain required for historical `PrimaryWeight` carrier/measure interpretation.
- **No promoted result:** no beam ROOT data, production Geant4 run, detector response, ESS, p-value, PID, penetration, timing, energy, pile-up, rate, or detector-performance quantity changed.
- **Next highest-value atom:** after #1181 is allowed only by completed required checks, implement #1182 per-instance fail-closed readiness on top of that exact inverse; then compile and execute hostile source/stopping-table fixtures plus seeded sequential/parallel generator-only closure with manifest binding.
- **Status:** `ACTIVE / STATIC_READINESS_FALSIFIER_IMPLEMENTED / PR_CI_REQUIRED / ACTUAL_THREAD_MODE_UNRESOLVED / COMPILED_GEANT4_BLOCKED / SOURCE_UNCERTAINTY_BLOCKED / DETECTOR_INFERENCE_BLOCKED`
