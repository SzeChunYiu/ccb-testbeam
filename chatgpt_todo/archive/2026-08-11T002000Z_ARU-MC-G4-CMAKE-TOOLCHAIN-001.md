# ARU-MC-G4-CMAKE-TOOLCHAIN-001 — CMake-selected build toolchain attestation

Status: `ACTIVE / IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED / REAL_EXTERNAL_BUILD_NOT_OBSERVED / DYNAMIC_LINK_IDENTITY_BLOCKED / RUNTIME_MANIFEST_BLOCKED`

Parent: #1182. Related: #1198, #1199, #1058, #1178, #1179, CL-021.

## Triggering contradiction

PR #1199 validated a two-boundary source/input/executable binding, but its `build_contract` is caller-supplied JSON. A string such as `compiler_id=fixture-cxx` can be self-consistent and still not identify the compiler selected by CMake. The historical `geant4/setup_and_run.sh` also states that a conda compiler/ROOT combination was required while invoking `cmake`/`make` from a mutable environment. Therefore declared toolchain metadata and measured configured-build state are separate atoms.

## Exact contract

Inputs:

- one PASS `ccb_geant4_build_binding_final_v1` receipt;
- the exact build tree `CMakeCache.txt`;
- required cache keys chosen by the run specification;
- package sentinels declared as `LABEL=CACHE_KEY:RELATIVE_SENTINEL` (for example a Geant4/VGM CMake package file under the cache-selected package root).

Output schema: `ccb_geant4_cmake_toolchain_attestation_v1`.

Required invariants:

1. final build-binding receipt digest verifies exactly;
2. the executable path re-hashes to the exact `(path, bytes, sha256)` stored by #1199;
3. `CMakeCache.txt` is read once from a regular non-symlink stream and its exact bytes/hash are recorded;
4. `CMAKE_COMMAND`, `CMAKE_CXX_COMPILER`, and `CMAKE_GENERATOR` exist exactly once and are resolved, not `*-NOTFOUND`;
5. CMake and C++ compiler executable paths are absolute, resolved to regular executable files, hashed, and `--version` probes return zero with bounded output;
6. requested package cache roots are absolute and each declared sentinel resolves below that root to a regular file whose target bytes are hashed;
7. the result is canonical-JSON self-digested.

No physical units enter this atom. Its measurand is configured build provenance, not detector response.

## External authoritative semantics

CMake documentation states that `CXX` is used only on the first configuration to select the compiler, after which the selection is stored as `CMAKE_CXX_COMPILER`; the `CMAKE_<LANG>_COMPILER` variable is the command CMake uses for that language and is not meant to change after selection. `CMAKE_GENERATOR` identifies the selected native build-system generator. These facts justify inspecting the configured CMake state rather than trusting only shell labels.

Primary documentation:

- https://cmake.org/cmake/help/latest/envvar/CXX.html
- https://cmake.org/cmake/help/latest/variable/CMAKE_LANG_COMPILER.html
- https://cmake.org/cmake/help/latest/variable/CMAKE_GENERATOR.html
- https://cmake.org/cmake/help/latest/variable/CMAKE_COMMAND.html
- https://cmake.org/cmake/help/latest/variable/CMAKE_MAKE_PROGRAM.html

## Competing mechanisms

### H1 — declared build-contract version strings are sufficient

Rejected. Caller metadata can disagree with the CMake-selected compiler without changing the executable/source receipt.

### H2 — probe whatever `cmake`/`c++` resolve from the current PATH

Rejected as sufficient. The current PATH can differ from the one used to configure the build. CMake's configured absolute tool selection is the stronger observable.

### H3 — CMake-cache selected compiler/CMake identity plus package sentinels

Survives as a bounded configured-build attestation and is implemented on this branch.

### H4 — CMake configuration proves every compiler/linker invocation and runtime shared-library identity

Rejected. Cache state does not observe each process execution, compiler read timing, transient substitution, link-editor inputs, or runtime loader resolution. These remain child atoms.

Equivalent symlink spellings that resolve to the same regular tool/package target collapse to one byte identity; both the invocation path and resolved target are retained.

## Deterministic experiments executed locally

Command:

`cd /tmp && python -m pytest -q test_geant4_toolchain_attestation.py`

Environment: Python 3.13 local automation runtime. RNG: none.

Result: `7 passed in 0.05s`.

Hostile fixtures:

- cache-selected CMake/C++ tools + Geant4/VGM sentinels + unchanged bound executable -> PASS;
- caller-declared fake compiler ID cannot override the compiler path/hash measured from `CMAKE_CXX_COMPILER` -> PASS discriminator;
- executable mutation after #1199 final receipt -> BLOCK;
- duplicate `CMAKE_CXX_COMPILER` cache key -> BLOCK;
- missing required cache key -> BLOCK;
- nonzero compiler `--version` probe -> BLOCK;
- relative package cache root -> BLOCK;
- symlink package sentinel -> accepted only with explicit symlink target plus resolved target hash.

Local ruff was unavailable (`ruff: command not found`), so repository exact-head CI is required before merge.

## Cross-scale propagation

This atom strengthens

`approved source/input -> #1199 executable identity -> measured configured CMake/compiler/package state`.

It does not close

`immutable compiler consumption -> link input/shared-library identity -> run manager/thread mode -> random engine/seeds -> event count -> runtime source/support/weight IDs -> output ROOT/tree/schema/hash -> detector-response reconstruction -> DATA/MC claim`.

A PASS therefore cannot promote CL-021, B2/B8, PID, penetration, timing, energy, pile-up, ESS, p-values, rates, or detector performance.

## Four sequential AI review passes

### (a) Build/physics integration lead — REVISE

Evidence inspected: #1199 receipt semantics, current `geant4/setup_and_run.sh`, CMake compiler/generator documentation. Strongest counter-hypothesis: caller-declared `build_contract` already identifies the toolchain. Falsifier: fixture deliberately places a false compiler label in the receipt while CMake cache points to a different executable; the attestation follows the measured cache path/hash. Residual uncertainty: no real external HIBEAM build cache was available. Vote: **REVISE / ACCEPT bounded configured-state mechanism, BLOCK compiled physics authorisation**.

### (b) Adversarial mechanism reviewer — BLOCK overclaim

Evidence: mutable PATH, cache/path/tool distinction, executable recheck. Strongest counter-hypothesis: a cache-selected compiler hash proves the compiler necessarily consumed the approved bytes. Falsifier: cache state can remain unchanged while source mutates transiently or a wrapper/tool is substituted during individual invocations. Residual: immutable build namespace and per-invocation/link provenance. Vote: **ACCEPT local detector / BLOCK immutable-consumption claim**.

### (c) Independent validation/statistics reviewer — ACCEPT deterministic oracle / BLOCK inference

Evidence: seven known-answer fixtures, exact hashes, duplicate/missing-key controls, no stochastic estimator. Strongest counter-hypothesis: version text alone is adequate. Falsifier: target byte hash and cache-selected absolute path are also required. Residual: no real build sample and no generated-event population. Vote: **ACCEPT software-provenance mechanics / BLOCK physics inference**.

### (d) Claims/provenance reviewer — BLOCK promotion

Evidence: #1182 acceptance criteria, CL-021 gates, no runtime/output identity. Strongest counter-hypothesis: source + executable + compiler version is enough to relabel historical MC as validated. Falsifier: dynamic dependencies, RNG/thread/event count, runtime inputs and output identity remain absent. Residual: entire downstream detector chain. Vote: **BLOCK CL-021 and detector-claim promotion**.

## Child atoms spawned

1. `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001`: bind link-editor inputs and actual runtime-loaded Geant4/VGM/ROOT/system libraries to exact files/hashes.
2. `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`: remove the #1199 mutate-and-restore gap with a frozen/content-addressed build namespace or equivalent compiler-consumption proof.
3. `ARU-MC-G4-RUNTIME-MANIFEST-001`: run-manager/thread mode, random engine/seeds, event count, model IDs, runtime input hashes, exit status, output ROOT/tree/schema/hash.
4. Compiled hostile cross-section/stopping-table controls remain required under #1182/#1058.

## Repository actions in this run

- PR #1200 exact-head CI was verified successful and the coordination-only PR was squash-merged as `main@dbb57b46f30da6298ce2850571dec3aab4b3674d`.
- #1182 had been auto-closed despite its own unresolved compiled/runtime acceptance criteria; it was reopened before this child implementation.
- Branch `audit/geant4-cmake-toolchain-attestation` adds the attestation utility, hostile tests, curated ruff coverage, and coordination/archive updates.

No production Geant4 executable/build cache was available in this runtime; no beam ROOT bytes were opened and no physics result was regenerated.
