# Latest Handoff

## Selected atom: configured scattering-source readiness (#1182)

Protected `main` inspected is `f181f91ef8fd5826a4acba4973da2e4eeba6c45c`. Existing PR #1183 was reconciled without force-push by two-parent merge `2c0a25165b6e51e1ea1304df5e27b61f848c4b29`, preserving the prior audit while taking current main as the implementation base.

### Runtime-state implementation on the PR branch

Tracked `ScatteringGenerator.cc/.hh` now implement the explicit per-instance state machine

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`.

`EnsureSourceReady()` executes at the beginning of `GeneratePrimaryVertex()` before event RNG. A configured cross-section source can produce an event only after the same generator instance reaches `CONFIGURED_READY`; the only uniform `theta_cm` path is explicit `CSFile=null`. Missing/invalid configured source or stopping data and inconsistent configured CDF state use Geant4 `FatalException` plus `std::abort()` fallback rather than `exit(0)` or hidden uniform degradation.

Stopping and cross-section rows are parsed into local vectors with checked required fields, finite/domain/cardinality/order validation, then published transactionally. `EvalELoss()` guards table cardinality. Changing `dEdxFile` or `CSFile` after readiness is fatal instead of mixing source identities; deliberate between-run reconfiguration remains a separate lifecycle child.

The central source law is unchanged: `linear_node_pdf_exact_inverse_v1`, `measured_table_support_truncate_v1`, `unit_direct_sampling_v1`; source table SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`.

### External patch/source split-brain child

The historical `patch_scatter.py` still embedded the superseded fail-open source path after the tracked C++ repair. That representation has now been eliminated: the helper atomically installs the exact tracked `ScatteringGenerator.hh/.cc` bytes into an explicitly selected external hibeam_g4 tree and verifies byte identity after replacement. A temporary-tree regression requires exact equality; a missing `include/` or `src/` layout must fail closed. This establishes static deployment parity only and does not prove the external tree compiles or that any production executable used those bytes.

### Static CI history and boundary

MC Validation run `31433066785` reached `1462 passed, 1 skipped, 8 xfailed, 1 xpassed` before failing two regression expectations. Both were test-contract defects rather than production C++ evidence: one declaration-only enum fixture incorrectly expected scoped readiness-state usage, and one sampler test froze an incidental prose phrase instead of the quadratic inverse operations. The tests were repaired without weakening the source invariant.

Current PR head after the external-installer and coordination updates is the latest commit on `audit/mc-source-readiness-contract`; exact-head CI must be rechecked before merge. Repository CI exercises Python/static tests and linting but does not compile `geant4/src_patch`, so green CI cannot close the compiled runtime universe. No production Geant4 campaign, beam ROOT data, or detector response was executed.

### Four sequential review votes

- **Source/runtime lead — ACCEPT bounded mechanism / BLOCK runtime authorisation:** per-instance lazy readiness solves the event-number dependency in source code, but exact hibeam_g4 executable commit, run-manager/thread mode, messenger lifecycle and real stopping-table compatibility are not yet bound.
- **Adversarial mechanism reviewer — ACCEPT static patch parity / BLOCK compiled fault matrix:** exact-byte installation removes text-patch drift, while compile/link behavior, `FatalException` runtime semantics, worker-local command propagation and hostile source/stopping fixtures remain unexecuted.
- **Independent statistics/validation reviewer — ACCEPT deterministic state/deployment contract / BLOCK physics inference:** readiness and byte parity are software invariants, not evidence that a generated angular population or downstream detector observable is correct.
- **Claims/provenance reviewer — BLOCK CL-021 promotion:** `geant4/setup_and_run.sh` still clones upstream hibeam_g4 without a pinned commit, production `dedx_p_in_CD2.txt` bytes/hash are absent, and no production manifest binds readiness/source/build/thread metadata.

### Child atoms / next work

1. Require green exact-head #1183 CI and do not reinterpret that Python/static gate as compiled Geant4 validation.
2. Recover/pin immutable hibeam_g4 source/build/run-manager provenance and worker count for representative production runs; `geant4/setup_and_run.sh` currently clones upstream without pinning a commit.
3. Recover immutable `dedx_p_in_CD2.txt` bytes/hash and prove parser/domain compatibility.
4. Compile the exact installed generator in Geant4 11.2.2 or a provenance-equivalent pinned environment and execute missing/empty/one-row/malformed/nonfinite/nonmonotonic/zero-density source and stopping-table controls, explicit `CSFile=null`, repeated readiness, seeded sequential, and multi-worker controls where supported.
5. Serialize readiness mode plus generator/source/stopping hashes, model IDs, executable/build/thread metadata, seeds and event count in production provenance before downstream products are authorising.

#1182, #1178, #1179 and CL-021 remain open/gated. No B2/B8, PID, penetration, timing, energy, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.
