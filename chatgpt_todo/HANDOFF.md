# Latest Handoff

## Selected atom: independently attest the CMake-selected Geant4 build toolchain

Protected `main` is `dbb57b46f30da6298ce2850571dec3aab4b3674d`. PR #1200 was merged only after exact-head MC Validation run `31445196091` succeeded. It records #1199's two-boundary build-binding milestone and leaves immutable consumption/toolchain/runtime provenance open. Issue #1182 had nevertheless been auto-closed; this run reopened it because its own compiled/runtime acceptance criteria remain unsatisfied.

### Why this atom exists

#1199's final receipt binds observed source/input state to an executable hash, but `build_contract` is caller-supplied JSON. A declared compiler/version string can therefore be internally consistent while disagreeing with the compiler actually selected in the CMake build tree. The historical `geant4/setup_and_run.sh` additionally states that one conda compiler/ROOT combination was necessary while invoking `cmake`/`make` from a mutable shell environment.

`ARU-MC-G4-CMAKE-TOOLCHAIN-001` therefore measures configured build state from the exact `CMakeCache.txt` and package sentinels instead of treating labels as evidence.

### Implemented contract on branch

Branch `audit/geant4-cmake-toolchain-attestation` adds schema `ccb_geant4_cmake_toolchain_attestation_v1`:

1. verify a PASS `ccb_geant4_build_binding_final_v1` receipt and its canonical digest;
2. re-hash the bound executable and require exact identity with the #1199 receipt;
3. read one regular non-symlink `CMakeCache.txt` byte stream, record SHA-256/byte count, and parse the exact bytes;
4. require unique resolved `CMAKE_COMMAND`, `CMAKE_CXX_COMPILER`, and `CMAKE_GENERATOR` plus caller-required cache keys;
5. resolve/hash the cache-selected CMake and C++ compiler executables and require successful bounded `--version` probes;
6. derive package sentinel paths from cache-selected absolute package roots and record symlink spelling plus resolved target hash;
7. emit a canonical self-digested attestation with explicit limitations.

CMake's official documentation supports the distinction: the first configuration selects the C++ compiler and stores it as `CMAKE_CXX_COMPILER`, while `CMAKE_GENERATOR` identifies the native build-system generator. The attestor uses that configured state rather than current-PATH guesses.

### Competing mechanisms and eliminations

- **Declared build-contract labels only:** rejected; they are caller assertions.
- **Probe current PATH `cmake`/`c++`:** rejected as sufficient because current PATH need not equal configure-time selection.
- **CMake-cache selected compiler/CMake paths plus package sentinels:** survives as a bounded configured-build provenance mechanism.
- **Treat cache state as proof of every compiler/link/runtime load:** rejected; transient source substitution, per-invocation wrapper/tool substitution, link inputs and runtime loader resolution are not observed.

Symlink aliases that resolve to the same regular target are collapsed as one byte identity while retaining both spelling and target metadata.

### Executed deterministic falsifiers

Local command: `cd /tmp && python -m pytest -q test_geant4_toolchain_attestation.py`.

Result: `7 passed in 0.05s`, Python 3.13, no RNG.

Fixtures cover a nominal cache-selected CMake/C++ + Geant4/VGM package world; a deliberately false caller-declared compiler string; executable mutation after the final #1199 receipt; duplicate compiler cache keys; missing required cache keys; failing compiler version probe; relative package cache roots; and symlink package sentinels with resolved-target hashing.

Local ruff was unavailable (`ruff: command not found`), so the branch is **not** merge-authorised until exact-head repository CI passes.

### Four sequential AI review passes

- **Build/physics integration lead — REVISE:** accepts the configured-state measurement and rejects metadata-only toolchain identity. Strongest counter-hypothesis: build-contract labels are already sufficient. Falsifier: declared fake compiler label versus independently cache-selected path/hash. Residual: no real external HIBEAM build cache in this runtime.
- **Adversarial mechanism reviewer — ACCEPT bounded detector / BLOCK immutable-consumption claim:** cache state and executable identity are stable observables, but they cannot exclude mutate-and-restore or per-invocation substitution. Residual: frozen build namespace and link provenance.
- **Independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference:** exact hashes and seven hostile fixtures close local software semantics; no event population or detector observable enters the test.
- **Claims/provenance reviewer — BLOCK CL-021 promotion:** dynamic dependency identity, run manager/thread mode, random engine/seeds, event count, runtime input hashes, output ROOT/tree/schema/hash and downstream detector-response compatibility remain absent.

### Child atoms

- `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`: frozen/content-addressed compiler input namespace or equivalent proof at consumption time.
- `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001`: link-editor inputs and actual runtime-loaded Geant4/VGM/ROOT/system library files/hashes.
- `ARU-MC-G4-RUNTIME-MANIFEST-001`: run-manager/thread mode, RNG engine/seeds, event count, source/support/weight IDs, runtime inputs, exit status, output file/tree/schema/hash.
- Compiled hostile cross-section and stopping-table controls remain open under #1182/#1058.

No production Geant4 executable/build cache, beam ROOT bytes, or detector-chain output was available here. No angular population, weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance quantity was regenerated or promoted.
