# Latest Handoff

## Selected atom: configured scattering-source readiness (#1182)

Protected `main` inspected for this atom is `f181f91ef8fd5826a4acba4973da2e4eeba6c45c`. Existing PR #1183 was materially stale (`57a7d387...` had diverged from current main), so the branch was reconciled without force-push by two-parent merge `2c0a25165b6e51e1ea1304df5e27b61f848c4b29`. Current-main source/UQ coordination was used as the merge-tree baseline while the existing #1182 static audit artifacts were retained.

### Runtime-state implementation now on the PR branch

Bounded implementation commit `e5c299fabf67c33ff983007d6dae17e8cbc7c48c` changes the tracked Geant4 source from event-zero/fail-open loading to the explicit per-instance state machine

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`.

`EnsureSourceReady()` now runs at the beginning of every `GeneratePrimaryVertex()` before event RNG. A configured cross-section source can produce an event only after the same generator instance reaches `CONFIGURED_READY`; the only path to uniform `theta_cm` is the explicit `CSFile=null` state. Missing/invalid configured files and inconsistent configured CDF state use Geant4 `FatalException` plus `std::abort()` fallback rather than `exit(0)` or uniform degradation.

Stopping and cross-section tables are parsed into local vectors with checked required numeric fields, finite/domain/cardinality/order validation, then published by `swap` only after validation. `EvalELoss()` now guards the table cardinality before using endpoint arrays. Once readiness is established, changing `dEdxFile` or `CSFile` is fatal rather than silently mixing source identities; deliberate between-run reconfiguration is a separate lifecycle child.

The central source law remains unchanged: `linear_node_pdf_exact_inverse_v1`, `measured_table_support_truncate_v1`, `unit_direct_sampling_v1`; source table SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`.

### Static validation and scientific boundary

The updated executable audit/tests distinguish the old mechanisms from the proposed replacement. Legacy event-zero loading, hidden empty-CDF uniform fallback, success-status source failure, unchecked source parsing and unguarded stopping arrays remain explicit negative controls. The replacement source is expected to report `STATIC_CONTRACT_IMPLEMENTED_COMPILED_VALIDATION_REQUIRED` rather than runtime authorisation.

Repository exact-head CI is still required. The MC Validation workflow exercises Python/static tests and linting but does not compile `geant4/src_patch`, so even a green run cannot close the compiled runtime universe. No production Geant4 campaign, beam ROOT data, or detector response was executed.

### Four sequential review votes

- **Source/runtime lead — ACCEPT bounded mechanism / BLOCK runtime authorisation:** per-instance lazy readiness solves the event-number dependency in source code, but exact hibeam_g4 executable commit, run-manager/thread mode, messenger lifecycle and real stopping-table compatibility are not yet bound.
- **Adversarial mechanism reviewer — REVISE / BLOCK until compiled fault matrix:** static paths remove the known fail-open mechanisms, but C++ compile/link behavior, `FatalException` runtime semantics, worker-local command propagation and external-patch parity remain untested.
- **Independent statistics/validation reviewer — ACCEPT deterministic contract / BLOCK physics inference:** readiness is a software state invariant, not evidence that a generated angular population or downstream detector observable is correct.
- **Claims/provenance reviewer — BLOCK CL-021 promotion:** current reproduction script clones upstream hibeam_g4 without a pinned commit, production `dedx_p_in_CD2.txt` bytes/hash are absent, and no manifest binds readiness/source/build/thread metadata.

### Child atoms / exact next work

1. Inspect exact-head #1183 CI and repair any static/lint failures without weakening the contract.
2. Recover/pin immutable hibeam_g4 source/build/run-manager provenance and worker count for representative production runs; repository `geant4/setup_and_run.sh` currently clones upstream without pinning a commit.
3. Recover immutable `dedx_p_in_CD2.txt` bytes/hash and prove parser/domain compatibility.
4. Bring `geant4/src_patch/patch_scatter.py` into semantic parity with the tracked readiness implementation, with a transformation/parity regression.
5. Compile the patched generator in Geant4 11.2.2 or a provenance-equivalent pinned environment and execute missing/empty/one-row/malformed/nonfinite/nonmonotonic/zero-density source and stopping-table controls, explicit `CSFile=null`, repeated readiness, seeded sequential, and multi-worker controls where supported.
6. Serialize readiness mode plus generator/source/stopping hashes, model IDs, executable/build/thread metadata, seeds and event count in production provenance before downstream products are authorising.

#1182, #1178, #1179 and CL-021 remain open/gated. No B2/B8, PID, penetration, timing, energy, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.
