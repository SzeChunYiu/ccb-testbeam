# ARU-MC-G4-TOOL-PROBE-BINDING-001

Concern: `PROV-G4-CMAKE-002`

Parent: #1182 / compiled Geant4 provenance. Predecessor: merged #1201 / `ccb_geant4_cmake_toolchain_attestation_v1`.

## Exact atom

The v1 toolchain attestation records a cache-selected tool path, resolves and hashes its target, and then runs `--version` through the original cache spelling. Those are two pathname observations. If the spelling is a symlink or otherwise mutable between hash and `exec`, the stored SHA-256 and version text need not be observations of the same executable entrypoint.

For a selected tool alias `p`, resolved target `r`, opened file description `f`, target bytes `B(f)`, and probe result `V(f)`, the local contract is:

1. parent v1 receipt is self-digested PASS;
2. current `p -> r` projection and target hash equal the parent projection;
3. open `r` once and require a regular executable file;
4. hash bytes from that same open file description before the probe;
5. execute `/proc/self/fd/{fd} --version` while inheriting that descriptor;
6. re-hash the same open descriptor after the probe and require identical device/inode/mode/size/SHA-256;
7. re-resolve/re-hash `p` after the probe and require the same projection as before;
8. serialize the new receipt with parent digest, exact target identity, opened device/inode/mode, probe stdout/stderr hashes, explicit scope, and limitations.

Units: none. State variables are filesystem path projection, regular-file identity, executable permission bits, byte hashes, exit status, and bounded probe output bytes. Scientific meaning is software provenance only: it binds the executable entrypoint used to report a tool version to the exact opened bytes that were measured.

## Mechanism universe

### H1 — hash resolved target, probe original alias
Rejected. A symlink/path transition between the two observations can decouple byte identity from the probed entrypoint.

### H2 — hash resolved target, probe resolved pathname, check after
Improves alias stability but still lets pathname replacement occur between the hash and the kernel opening the executable. It is a bounded improvement but not the strongest available mechanism on the target Linux environment.

### H3 — open target once, hash and execute that same open file description
Survives for the local version-probe entrypoint atom. Linux `/proc/self/fd/{fd}` plus `pass_fds` makes the executed entrypoint refer to the already-open object rather than re-resolving the cache alias. Re-hashing the same descriptor and rechecking the alias projection detects persistent mutation.

### H4 — infer build/runtime dependency identity from the bound tool entrypoint
Rejected. Dynamic loader inputs, compiler wrappers/child processes, actual compiler/linker invocations, and runtime-loaded Geant4/VGM/ROOT/system libraries are different atoms.

Equivalent aliases resolving to the same target bytes are collapsed as one executable-byte identity while their path spelling remains provenance metadata.

## Invariants and limiting cases

Let `H_pre(f)` and `H_post(f)` be SHA-256 of the same open descriptor before and after the probe. Required:

`H_parent == H_path_pre == H_pre(f) == H_post(f) == H_path_post`.

The parent path projection before/after must also agree in resolved path, size, symlink flag/target, and target SHA-256.

A stable direct path and a stable symlink are both allowed. A symlink transition during the probe, target mutation during the probe, changed parent-attested bytes, non-executable target, unavailable `/proc/self/fd`, excessive probe output, timeout, execution error, or nonzero exit all fail closed.

This is not a proof that dynamically loaded libraries are the same between probe and build/run, nor that a wrapper does not launch a different child compiler. Those become child atoms rather than hidden assumptions.

## Executed falsifiers

Local deterministic reconstruction on Linux, Python runtime, no RNG:

`pytest -q test_ccb_probe.py` -> `6 passed in 0.06s`.

Fixtures:

1. two stable direct executable scripts -> PASS;
2. stable symlink alias -> PASS and resolved target hash retained;
3. target script rewrites the alias to a second target during the probe -> BLOCK on post-probe path/target transition;
4. probed script mutates its own executable file -> BLOCK on open-descriptor post-probe hash/identity change;
5. tool bytes changed after parent receipt creation but before binding -> BLOCK on parent/current projection mismatch;
6. probe exits 9 -> BLOCK.

No Geant4 binary, production build cache, beam ROOT, production MC ROOT, or detector product entered these tests.

## Four sequential AI review passes

### (a) Build/physics integration lead — ACCEPT bounded entrypoint binding / REVISE overall build provenance
Evidence: merged #1201 code, exact parent receipt semantics, Linux open-file execution mechanism, hostile fixtures. Strongest counter-hypothesis: probing the original cache spelling is already equivalent to probing the hashed target. Falsifier: mutable alias transition separates the two pathname observations. Residual: actual compiler/linker invocation and real HIBEAM build tree remain unobserved.

### (b) Adversarial mechanism reviewer — ACCEPT H3 / BLOCK transitive dependency claims
Evidence: symlink-transition and self-mutation fixtures. Strongest counter-hypothesis: executing `/proc/self/fd/{fd}` binds the entire compiler environment. Falsifier: the bound entrypoint can be dynamically linked or itself spawn wrappers/children whose bytes are not in this receipt. Residual: loader and child-process identity.

### (c) Independent validation reviewer — ACCEPT deterministic local oracle / BLOCK physics inference
Evidence: exact byte hashes, device/inode/mode state, zero-RNG hostile tests. Strongest counter-hypothesis: a successful bound `--version` probe validates generated events. Falsifier: no event, source law, seed, thread, transport, response, or statistical estimator is exercised. Residual: full compiled/runtime chain.

### (d) Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion
Evidence: CL-021 remains gated and #1182 acceptance criteria still include runtime/thread/input/output and compiled hostile controls. Strongest counter-hypothesis: CMake/compiler version identity is enough to promote historical MC. Falsifier: library/runtime/input/output identities are absent. Residual: entire downstream detector-response and DATA/MC compatibility chain.

## Child atoms spawned

- `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001`: exact linker inputs plus actually loaded Geant4/VGM/ROOT/system libraries and hashes.
- `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`: source/input namespace consumed by real compiler/linker invocations, not only before/after observations.
- `ARU-MC-G4-WRAPPER-CHAIN-001`: when cache-selected compiler is a wrapper/launcher, identify and bind child compiler command/bytes/environment.
- `ARU-MC-G4-RUNTIME-MANIFEST-001`: run manager/thread mode, RNG engine/seeds, event count, source/support/weight model IDs, runtime inputs, exit status, and output ROOT/tree/schema/hash.

## Claim/wiki consequence

No detector or scattering-model claim is promoted. The only promotable statement after CI is that a version-probe entrypoint can be content-bound to an already-open executable object on the Linux validation/runtime platform. CL-021, #1178/#1179/#1182/#1058 and downstream DATA/MC claims remain gated.
