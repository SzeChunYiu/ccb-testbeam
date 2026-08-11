# ARU-MC-CS-WORKER-INIT-001 — per-instance fail-closed implementation

Status: **PARTIAL / STATIC_IMPLEMENTATION_ON_PR / COMPILED_GEANT4_BLOCKED / CLAIM_GATED**

Canonical issue: #1182. Parent/source-model dependencies: #1178, #1179, #1053, #880, CL-021.

## Exact contract

Selected transition:

`messenger-selected file names -> validated local parse -> transactional instance state -> readiness -> BeamEnergy/SampleThetaCM -> primary vertex`.

Required state machine:

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`.

For generator instance `j` and generated event `e`, configured-source use requires

`Generate_j(e) => R_j == CONFIGURED_READY`.

`CSFile=null` is a distinct, explicit `UNCONFIGURED_UNIFORM` proposal. A missing, malformed, nonfinite, nonmonotonic, empty, one-row or zero-density configured source must not become that proposal.

Inputs retain the source-model identities already on main: `linear_node_pdf_exact_inverse_v1`, `measured_table_support_truncate_v1`, `unit_direct_sampling_v1`, with cross-section table SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`. Stopping-table numerical units remain the pre-existing loader contract: input energy converted by `938.28/931.5` and input stopping-power scale multiplied by `1000`; the immutable production stopping-table bytes are not present in this repository and remain a validation dependency.

## Live repository provenance and reconciliation

Protected main inspected before implementation: `f181f91ef8fd5826a4acba4973da2e4eeba6c45c`.

Existing PR #1183 was not replaced. Its old head `57a7d387adaf39edc5fa14a35a4bf79706b7d1c4` had diverged from current main, with merge base `f5f96951c3f56986769a16cd53ab8e23dee3e287`. The branch was reconciled without force-push by two-parent merge commit `2c0a25165b6e51e1ea1304df5e27b61f848c4b29`, taking current-main coordination/source state as the merge-tree baseline while preserving the existing static audit artifacts.

Bounded implementation commit: `e5c299fabf67c33ff983007d6dae17e8cbc7c48c`.

Tracked source Git blobs after that commit:

- `geant4/src_patch/ScatteringGenerator.cc`: `6e2d886df78176cd59e9e1d5882f38d651397023`;
- `geant4/src_patch/ScatteringGenerator.hh`: `3492d2b61fcc7320070837cff241089f40e4882d`.

## Competing mechanisms and disposition

1. **Global event-ID-zero load gate.** Rejected as a general per-instance readiness mechanism. It remains observationally adequate only in the narrower historical world of a proven strictly sequential executable with one generator instance receiving event zero first.
2. **Per-instance lazy readiness on first event use.** Preferred and implemented. It is independent of global event numbering and runs before event RNG consumption.
3. **Construction/run-hook initialization.** Still potentially valid in another implementation, but messenger/configuration lifecycle ordering would have to be proven.
4. **Configured-source fault -> uniform fallback.** Rejected because it changes the proposal measure while hiding provenance failure.
5. **Required-input fault -> `exit(0)`.** Rejected because scientific input failure cannot be shell-success completion.
6. **Mutable-vector append loaders.** Rejected as an idempotence mechanism. The implementation parses into local vectors and swaps only after validation.
7. **Silent file-name change after readiness.** Rejected for this bounded implementation: `dEdxFile` or `CSFile` identity change after readiness is fatal rather than silently mixing source states. A deliberate reconfiguration API is a separate lifecycle atom.

## Implementation mechanics

`EnsureSourceReady()` is called at the start of every `GeneratePrimaryVertex()` before target-position or angular RNG. The first call loads the required stopping table and either enters explicit uniform mode (`CSFile=null`) or loads/builds the configured cross-section CDF. Later calls are idempotent provided the messenger-selected file identities are unchanged.

Both table loaders now parse into local vectors. They reject incomplete numeric rows, nonfinite/domain-invalid values, insufficient cardinality, and non-increasing independent coordinates. Member vectors are published with `swap` only after complete validation. CDF construction likewise builds local theta/PDF/CDF vectors and publishes them only after a finite positive normalization exists.

Configured-source CDF failure no longer disables source sampling. `SampleThetaCM()` returns a uniform angle only in `UNCONFIGURED_UNIFORM`; all configured-not-ready or inconsistent-CDF states are fatal. `EvalELoss()` checks stopping-table cardinality before the existing endpoint interpolation uses `Ene[0]`/`dEdx[0]`.

Fatal input/readiness paths use Geant4 `G4Exception(..., FatalException, ...)` and retain `std::abort()` as a non-success fallback if a custom handler unexpectedly returns.

## Executed / executable falsifiers

The original static audit preserved the pre-fix mechanisms: event-zero load gating, hidden uniform fallback, `exit(0)`, unchecked cross-section parsing, unguarded empty stopping arrays, and no explicit readiness state.

The updated deterministic static audit checks the replacement source for:

- absence of the event-zero load gate;
- per-event `EnsureSourceReady()` call;
- explicit-uniform-only random-angle path;
- absence of `exit(0)` input failure;
- fatal exception plus process-failure fallback;
- checked row parsing;
- stopping-table cardinality guard;
- explicit readiness state;
- configuration identity guard;
- transactional publication of stopping/source/CDF vectors;
- fatal configured CDF inconsistency.

Synthetic negative controls keep the legacy event-zero/fail-open world blocked and demonstrate that merely adding a readiness token does not erase other fail-open mechanisms.

Repository exact-head CI is required for the final PR head. This repository workflow exercises the Python/static regression and linting but does **not** compile `geant4/src_patch`; therefore green repository CI is not compiled generator validation.

## Cross-scale compatibility

Local software closure is necessary but insufficient. The source model remains conditioned on measured 26.49–169.78 deg CM support and unresolved #1179 nuisance/covariance semantics. A future compiled event sample is authorising only if the same source-model IDs, exact source/stopping bytes, readiness state, generator commit, executable/build identity, thread mode, seed(s), worker count and event count are serialized in provenance. Downstream detector claims still require the complete detector-response chain and identical DATA-like reconstruction.

## Four sequential AI review passes

### (a) Source/runtime lead — **ACCEPT software mechanism / BLOCK runtime authorisation**

Evidence inspected: current-main `ScatteringGenerator.cc/.hh`, issue #1182, source-model sidecar, `setup_and_run.sh`, prior static audit, Geant4 lifecycle/fatal-exception documentation. Strongest counter-hypothesis: event-zero loading is sufficient because the real production executable is strictly sequential. Attempted falsifier: repository search for immutable run-manager/thread-count provenance; none was found, while `setup_and_run.sh` clones upstream hibeam_g4 without pinning a commit. Residual uncertainty: real executable commit, worker mode, messenger lifecycle, real stopping-table compatibility, and compiled behavior. Vote: **ACCEPT bounded implementation / BLOCK runtime authorisation**.

### (b) Adversarial mechanism reviewer — **REVISE / BLOCK until compiled fault matrix**

Evidence inspected: legacy hidden fallback and success-exit paths versus new explicit state/fatal paths, transactional vector publication, reconfiguration guard. Strongest counter-hypothesis: static tokens can look correct while C++ exception/lifecycle behavior remains wrong. Attempted falsifier: static regression separates the legacy and replacement mechanisms, but no Geant4 build is available here. Residual uncertainty: compile/link validity, actual `FatalException` handling, worker-local command propagation, external `patch_scatter.py` parity. Vote: **REVISE; no runtime acceptance yet**.

### (c) Independent statistics/validation reviewer — **ACCEPT deterministic contract / BLOCK physics inference**

Evidence inspected: state-machine invariant and proposal-measure distinction. Strongest counter-hypothesis: seeded CDF agreement alone would validate the generator. Falsifier: source-readiness faults are orthogonal to the conditional distribution after successful loading; a perfect ready-state CDF cannot show that every instance reached ready state or that failed inputs stopped the run. Residual uncertainty: compiled sequential/parallel hostile controls and manifest-bound event populations. Vote: **ACCEPT static discriminator / BLOCK inference**.

### (d) Claims/provenance reviewer — **BLOCK CL-021 promotion**

Evidence inspected: CL-021/source sidecar gating, repository CI scope, unpinned upstream clone in `geant4/setup_and_run.sh`, open #1178/#1179. Strongest counter-hypothesis: source code repair plus green Python CI is sufficient provenance. Falsifier: no compiled run, exact upstream executable commit, stopping-table digest, worker count, or production manifest is presently bound. Residual uncertainty: all of those plus downstream detector regeneration. Vote: **BLOCK claim promotion**.

## Child atoms spawned / retained

- **Runtime build/execution child:** compile exact tracked source into a pinned hibeam_g4 commit and execute missing/empty/one-row/malformed/nonfinite/nonmonotonic/zero-density CS and stopping-table fixtures, explicit `CSFile=null`, repeated readiness, seeded sequential, and multi-worker controls if supported.
- **Executable provenance child:** replace or supplement the unpinned `git clone` reproduction step with exact upstream commit/run-manager/build flags and worker-count provenance.
- **Stopping-table contract child:** recover immutable production `dedx_p_in_CD2.txt` bytes/hash and prove the new checked parser/domain assumptions against them.
- **Patch parity child:** `geant4/src_patch/patch_scatter.py` still mirrors only the earlier source-law repair; prove or implement parity for the readiness state machine before external checkout production use.
- **Manifest child:** serialize readiness mode plus generator/source/stopping hashes, source-model IDs, executable/build/thread metadata, seeds and event count.
- **Lifecycle child:** decide whether intentional file reconfiguration between runs is supported; current implementation fails closed rather than silently reloading.

## Claim boundary

No beam ROOT bytes were opened. No production Geant4 campaign or compiled generator test was run. No angular population, B2/B8 result, detector response, ESS, p-value, PID, penetration, timing, energy, pile-up, rate or detector-performance result was regenerated or promoted. #1182, #1178, #1179 and CL-021 remain open/gated.
