# ARU-MC-G4-BUILD-BINDING-001 — build source/input → executable binding

Status: `ACTIVE / IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED / RUNTIME_PROVENANCE_BLOCKED`

Parent: #1182 / `ARU-MC-CS-COMPILED-PROVENANCE-001`

Concern: `PROV-G4-BUILD-BINDING-001`

## Atomic input/output contract

### Inputs

- an external `hibeam_g4` work tree whose approved baseline commit/tree and reviewed `ScatteringGenerator.hh/.cc` overlay pass `ccb_geant4_external_overlay_v1`;
- every staged file that can influence the build/run configuration, represented by a unique semantic label and regular non-symlink path;
- a non-empty, explicit build-contract JSON object containing the declared configure/build/toolchain identity fields available to the caller.

### Output

A two-phase, canonical-JSON receipt:

1. `ccb_geant4_build_binding_begin_v1` records the validated external source state and same-open-stream SHA-256/byte count for every staged input before compilation;
2. `ccb_geant4_build_binding_final_v1` revalidates the external source, re-hashes every staged input, requires exact equality with the begin receipt, hashes the regular non-symlink executable, and binds the final receipt to the begin receipt digest.

All hashes are SHA-256 over bytes; byte counts are bytes. No detector observable is measured by this atom. Its scientific meaning is provenance/integrity only: the source and input states observed at the two build boundaries are identical and the resulting executable has an exact content identity.

## Invariants

For external source projection `S`, staged input records `I_k=(label,path,bytes,sha256)`, and executable record `E`:

- `S_begin = S_finalize`;
- `I_k,begin = I_k,finalize` for every declared input and with a one-to-one label/path declaration;
- all source/input/executable paths inspected as payloads are regular non-symlink files;
- `receipt_sha256 = SHA256(canonical_JSON(receipt_without_receipt_sha256))`;
- `final.begin_receipt_sha256 = begin.receipt_sha256`.

These are exact equality relations, not statistical tests. They have no sampling uncertainty.

## Competing mechanisms

### H1 — pre-build source validation only

Rejected as sufficient. A source/input may change after the validator returns but before/during compilation.

### H2 — executable hash only

Rejected as sufficient. An executable content hash identifies the artifact but does not bind it to an approved source/input state.

### H3 — pre/post source and staged-input observations + executable hash

Survives as a bounded, observable integrity contract and is implemented here.

### H4 — H3 is equivalent to an immutable build snapshot

Rejected. A transient mutation after `begin` that is restored before `finalize` is observationally indistinguishable from no mutation. H3 therefore cannot prove what bytes every compiler read performed.

### H5 — trust pathnames or metadata without opening bytes

Rejected. The implementation uses one opened byte stream for digest and byte count and verifies descriptor/path identity before/after the read. Symlinks and non-regular files fail closed.

## Executed/encoded discriminating fixtures

`tests/test_geant4_build_binding_receipt.py` encodes:

- unchanged reviewed source + unchanged staged inputs + regular executable → PASS;
- reviewed source mutation after begin → BLOCK;
- staged macro mutation after begin → BLOCK;
- symlink staged input → BLOCK;
- symlink executable → BLOCK;
- tampered begin-receipt JSON with stale digest → BLOCK;
- duplicate semantic input labels → BLOCK;
- duplicate physical input paths under different labels → BLOCK;
- empty build contract → BLOCK;
- canonical JSON serialisation/digest presence → PASS.

Exact-head GitHub CI is required before these fixtures are described as validated. No production Geant4 build was executed by this ChatGPT environment.

## Four sequential AI review passes

### 1. Build/source provenance lead

Background: reproducible scientific software builds and Geant4 source/configuration provenance.

Evidence inspected: #1198 merged validator, `geant4/setup_and_run.sh`, #1182, staged-input history, current MC CI.

Strongest counter-hypothesis: the #1198 pre-build source gate plus historical input hashes is already enough to identify a build.

Attempted falsifier: mutate a staged macro after the begin observation. The historical pathname/hash and pre-build source state remain unchanged while the actual later input differs; H1 is therefore insufficient.

Residual uncertainty: compiler/CMake/Geant4/VGM identity is presently only declared in `build_contract`, not independently measured; actual compiler read timing is not observable.

Vote: `REVISE` — accept the two-boundary binding primitive, block compiled-physics authorisation.

### 2. Adversarial mechanism reviewer

Background: filesystem races, artifact substitution, supply-chain and build-integrity failure modes.

Evidence inspected: same-stream hashing implementation, source validator, receipt canonicalisation and hostile fixtures.

Strongest counter-hypothesis: repeating the same checks after build is equivalent to freezing the source.

Attempted falsifier: transient mutate-and-restore between begin and finalize. It can evade two observations, so the stronger equivalence is false.

Residual uncertainty: immutable source/input snapshots or a build sandbox are still required to eliminate that class; dynamic-link dependencies are not yet bound.

Vote: `BLOCK` immutable-build claims / `ACCEPT` H3 as a bounded detector for persistent visible transitions.

### 3. Independent validation/statistics reviewer

Background: test-oracle design, identifiability and statistical-unit separation.

Evidence inspected: exact equality invariants and deterministic fixture design.

Strongest counter-hypothesis: a successful receipt provides statistical evidence that the generator distribution is correct.

Attempted falsifier: none of the receipt fields contains generated angles, event weights, seeds, event counts or detector observables. The provenance atom is logically upstream of those measurements.

Residual uncertainty: no compiled hostile source/stopping controls or production campaign sample exists in this environment.

Vote: `ACCEPT` deterministic integrity oracle / `BLOCK` generator or detector inference.

### 4. Claims/provenance reviewer

Background: scientific claim ledgers, source-to-claim traceability and reproducibility governance.

Evidence inspected: #1182 dependency graph, CL-021 gating, current main and the exact scope strings in both receipt phases.

Strongest counter-hypothesis: once an executable hash is recorded, CL-021 can be promoted.

Attempted falsifier: the receipt still lacks independently attested toolchain/dynamic dependencies and runtime seed/thread/event/output provenance, and it has no physics closure data.

Residual uncertainty: full run manifest and downstream detector-response compatibility.

Vote: `BLOCK` CL-021 promotion.

## Upward propagation and child atoms

`reviewed source bytes → pre-build external overlay gate (#1198) → begin source/input receipt → build → final source/input recheck + executable identity → [OPEN] immutable consumption-bound build snapshot/toolchain/dependency closure → [OPEN] runtime RNG/thread/event/model/input/output manifest → [OPEN] compiled hostile source/stopping controls → [OPEN] generated angular/weight validation → [OPEN] detector-response chain → claims`.

Material children spawned/retained:

- immutable source/input snapshot or sandbox eliminating transient mutate-and-restore;
- independently measured compiler, CMake, Geant4, VGM and linked-library identity;
- runtime run-manager/thread mode, random engine/seeds, event count and model IDs;
- output file/tree/schema/hash identity and source-event closure;
- compiled missing/malformed/reconfigured cross-section and stopping-table negative controls.

No parent closure is claimed while those children remain unresolved.
