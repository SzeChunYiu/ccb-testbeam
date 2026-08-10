# ARU-MC-CS-WORKER-INIT-001 — configured scattering-source readiness

Status: **PARTIAL / STATIC_FALSIFIER_EXECUTED / RUNTIME_MODE_UNRESOLVED / COMPILED_VALIDATION_BLOCKED**

Parent/dependencies: #1178, #1179, #1053, #880, CL-021. Canonical child issue: #1182.

## Contract

The selected atom is the transition from generator configuration to a per-instance source-ready state before any event observable is produced:

`messenger configuration -> validate stopping/source inputs -> source readiness -> BeamEnergy + SampleThetaCM -> primary vertex`.

Required state machine:

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`.

For generator instance/worker `j` and event `e`, the authorising invariant is

`Generate_j(e) => Ready_j`, with `Ready_j = CONFIGURED_READY` whenever a cross-section source is configured.

A configured source failure must never collapse into the explicit no-source proposal `theta_cm ~ Uniform(0,pi)`. Those are different statistical measures.

## Evidence inspected

Protected main at the branch point: `fa62e8bb6ce7de10f840ebfa016eaa40cd9f74ec` (PR #1180 source-table provenance).

PR #1181 reviewed exact head: `edf71180b2f622b7cf16a8c1243d2140c2369eb9`.

At both the branch-point source and the #1181 source where relevant:

- `GeneratePrimaryVertex()` gates `LoadFiles()` on `event->GetEventID()==0`, then calls `BeamEnergy()`.
- `BeamEnergy()->EvalELoss()` assumes populated stopping arrays; the empty-table path can reach `dEdx[0]` / `Ene[0]`.
- an empty configured CDF is observationally collapsed into `pi * G4UniformRand()` by `SampleThetaCM()`.
- missing input file handling uses `exit(0)`.
- `LoadCrossSection()` does not check the conversion count returned by `sscanf`.
- no explicit idempotent per-instance readiness state is present.

The retained S21 source review had already noted that the event-zero load gate plus mutable table vectors require stricter validation in multithreaded execution.

Authoritative Geant4 documentation inspected:

- Book for Application Developers, Basic Examples / multithreading: user actions are defined thread-locally in MT worker `Build()`.
- Book for Application Developers, Run: event assignment to worker threads is first-come-first-served and event numbers handled by each thread are not sequential.
- Mandatory User Actions: `Build()` defines worker/sequential user action instances.

The exact hibeam_g4 production run-manager/build mode is **not** present as immutable evidence in this runtime. Therefore the MT failure path is a conditional but material survivor, not a claim that production definitely ran multithreaded.

## Competing mechanisms

1. **H1 — event zero is a valid initialization signal.** Survives only if the exact executable is proven strictly sequential and one instance necessarily receives event zero first. Rejected as a general Geant4 per-worker contract.
2. **H2 — idempotent per-instance lazy readiness after messenger configuration.** Preferred software mechanism.
3. **H3 — construction/run-hook initialization.** Potentially valid only if lifecycle ordering proves messenger-selected file paths are already final.
4. **H4 — configured source failure degrades to uniform sampling.** Rejected: it changes the proposal measure.
5. **H5 — required source failure exits with success status.** Rejected as provenance/automation semantics.

Mutexing or slightly altering the global event-ID predicate is not an independent solution; it does not establish readiness of every generator instance.

## Executed deterministic falsifier

Repository work on `audit/mc-source-readiness-contract` adds:

- `tools/audit/research_scattering_source_readiness.py`;
- `tests/test_scattering_source_readiness.py`;
- `results/research/scattering_source_readiness_v1.json`.

The executable static predicates freeze the currently observed mechanisms: event-zero load gating, uniform fallback on empty CDF, success-status input failure, unchecked source-row parsing, unsafe empty stopping-table dereference pattern, and absence of explicit instance readiness. No RNG, detector data or Monte Carlo sample is used.

The current machine-readable verdict is `BLOCK_RUNTIME_AUTHORIZATION`. The runtime thread mode is intentionally encoded as `UNRESOLVED_REQUIRES_EXACT_EXECUTABLE_PROVENANCE`.

## Required hostile controls after implementation

- two or more generator instances whose event sequences do not all contain event zero;
- missing, empty, one-row, malformed, nonfinite, negative-density, duplicate-angle, decreasing-angle and all-zero source files;
- analogous stopping-table faults;
- explicit `CSFile=null` positive control demonstrating intentional uniform mode;
- repeat readiness call proving no vector duplication/append;
- compiled seeded sequential runtime;
- compiled seeded multi-worker runtime if supported by the exact executable;
- manifest binding generator commit, Geant4 version/build mode, worker count, seed(s), source/stopping hashes, source-model IDs, readiness mode and event count.

## Four sequential review passes

### (a) Source/runtime lead — REVISE / BLOCK runtime authorization

Evidence: event-zero gate; required stopping lookup; official Geant4 lifecycle; prior S21 review. Strongest counter-hypothesis: production is guaranteed sequential. Attempted falsifier: repository search for exact run-manager/thread provenance; no immutable scatter-executable evidence was found. Residual: actual production thread mode and messenger/config lifecycle.

### (b) Adversarial mechanism reviewer — REJECT fail-open semantics

Evidence: uniform fallback, `exit(0)`, unchecked `sscanf`, empty-table dereference. Strongest counter-hypothesis: invalid inputs always fail obviously. Static source directly falsifies that guarantee. Residual: compiled failure behavior after repair.

### (c) Independent statistics/validation reviewer — ACCEPT deterministic software falsifier / BLOCK physics inference

Evidence: source-state transition does not require stochastic estimation. Strongest counter-hypothesis: a seeded CDF closure alone validates the source. Rejected because readiness/fault semantics are orthogonal to the sampled CDF once ready. Residual: compiled worker/sequential closure and production manifest.

### (d) Claims/provenance reviewer — BLOCK CL-021 runtime promotion

Evidence: #1181 itself states Python CI does not compile `geant4/src_patch`. Strongest counter-hypothesis: green exact-head Python CI authorizes the generator. Rejected. Residual: compiled runtime, source faults, exact executable provenance, downstream regeneration.

## PR #1181 coordination

One exact-head MC Validation run (`31415757686`) completed successfully. A second required `test` check on the same head (`31415753649`) was still in progress during this session. A squash-merge attempt was rejected by protected-branch enforcement with `Required status check "test" is in progress`; no bypass was attempted.

The deterministic inverse in #1181 is still the preferred numerical repair and #1182 is not a request to reintroduce its legacy sampler defect. #1178/CL-021 nevertheless remain gated for runtime claims.

## Scientific/claim boundary

No beam ROOT file was opened. No Geant4 campaign was executed. No sampled angular distribution, source uncertainty, ESS, p-value, PID, penetration, timing, energy, pile-up, rate or detector-performance result was regenerated or promoted.

## Next

First allow #1181 only after every required exact-head check is complete. Then implement #1182's per-instance fail-closed readiness on top of the exact-inverse source, compile in the known Geant4 11.2.2 environment or a provenance-equivalent environment, and execute the hostile source matrix plus seeded generator-only sequential/parallel controls. #1179 source covariance follows after runtime source identity is stable.
