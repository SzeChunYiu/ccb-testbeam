# Latest Handoff

## Validated atom: bind Geant4 source/staged-input state to executable identity

Protected `main` advanced from `17349d0a72a267723b805615480e76519ed7b8a8` to `948ea2885e7c54751f4f4feaa3c1fcfc63fc9e8f` when PR #1199 was squash-merged after exact-head CI. The predecessor #1198 external-overlay gate and the #1199 two-boundary build-binding gate are now repository state. #1182 remains open; CL-021 and detector inference remain gated.

### Atomic contract now validated on main

`ARU-MC-G4-BUILD-BINDING-001` implements two content-bound observations around a build:

- `begin`: validate the exact external baseline/reviewed overlay and hash each uniquely labelled staged input from one opened regular non-symlink byte stream as `(resolved path, bytes, sha256)`; record explicit build-contract metadata and a canonical JSON receipt digest.
- `finalize`: verify the begin receipt digest, repeat the external source validation, require source projection equality, re-hash every staged input and require exact identity, then hash the resulting regular non-symlink executable and bind the final receipt to the begin-receipt digest.

This is an integrity statement about what was observed at the two boundaries. It is not an immutable-build proof: a transient mutation that occurs after `begin` and is restored before `finalize` is not identifiable.

### Mechanisms and falsifiers

Pre-build validation alone was rejected because later persistent changes can alter the build. Executable hash alone was rejected because artifact bytes are not attributed to approved source/input state. The surviving bounded mechanism is pre/post source+input equality plus executable identity. Treating those two observations as equivalent to a frozen build namespace was rejected by the mutate-and-restore counterexample.

The repository fixtures now cover unchanged source/input success; persistent reviewed-source mutation failure; staged macro mutation failure; symlink input/executable failure; tampered begin-receipt failure; duplicate semantic label and duplicate physical path failure; empty build-contract failure; and canonical receipt digest generation.

### Exact validation and failure provenance

The first exact head, `cde7b7a4ebe83c3aa4859a8f070ce5190ce59fd3`, ran MC Validation `31444426279`. The full unit-test suite passed (`1486 passed, 1 skipped, 8 xfailed, 1 xpassed`), but workflow enforcement failed because ruff found exactly one `UP035` style error: `Iterable` was imported from `typing` rather than `collections.abc`. The repair changed only that import; no receipt, test-oracle, or scientific semantics changed.

Final exact head `49431dc9976708251f9b7011b70ab8e2dd3cb9ce` passed MC Validation run `31444712724`: curated ruff reported all checks passed, pytest reported `1486 passed, 1 skipped, 8 xfailed, 1 xpassed`, artifact upload succeeded, and enforcement succeeded. The retained final diagnostic artifact has digest `sha256:7c6e286f630b1738ab2103c015f82048c33402e9f6f376b12744f96443e3631f`. PR #1199 was then squash-merged as `948ea2885e7c54751f4f4feaa3c1fcfc63fc9e8f`.

### Four sequential AI review passes

- **Build/source provenance lead — REVISE.** Accepts the validated two-boundary primitive; blocks compiled-physics authorisation because toolchain identity is declared but not independently measured and compiler read timing is not observed.
- **Adversarial mechanism reviewer — ACCEPT bounded detector / BLOCK immutable-build claims.** Persistent visible changes are discriminated; transient mutate-and-restore and dynamic dependency substitution remain live counterexamples.
- **Independent validation reviewer — ACCEPT deterministic integrity oracle / BLOCK physics inference.** The tests validate exact equality/failure semantics only; they contain no generated angular population, weights, seeds, event counts or detector observables.
- **Claims/provenance reviewer — BLOCK CL-021 promotion.** Independently attested toolchain/dependency state, runtime provenance, output identity and downstream physics closure remain absent.

### Next highest-value child

Continue #1182 at the actual consumption boundary: replace mutable source/input path trust with an immutable or content-addressed build namespace (or a sandbox whose compiler inputs are frozen), and independently record compiler, CMake, Geant4, VGM and linked-library identities. Then bind runtime run-manager/thread mode, random engine/seeds, event count, source/support/weight model IDs, all staged runtime inputs, output file/tree/schema/hash, and compiled hostile cross-section/stopping controls. Only after those gates can generated angular/weight closure propagate into the detector-response chain.

No beam ROOT bytes or production Geant4 campaign were executed in this environment, and no angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.
