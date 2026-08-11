# Latest Handoff

## Selected atom: bind CMake/C++ version probes to the exact opened executable bytes

Protected `main` is `1968f7352436a74b411db153b47419f2c6cb4a0f`. PR #1201 has now merged; its exact-head MC Validation run `31446858035` succeeded with curated ruff clean and `1493 passed, 1 skipped, 8 xfailed, 1 xpassed`. The v1 CMake toolchain attestation is therefore validated repository state, but its own PR discussion recorded follow-up concern `PROV-G4-CMAKE-002`: it hashes a resolved target, then invokes the original cache path spelling for `--version`.

### Why this child exists

For a mutable alias `p` and resolved target `r`, the v1 sequence is approximately `hash(r)` then `exec(p)`. A symlink/path transition between those observations can make the stored SHA-256 and version output refer to different executable entrypoints. The new atom is `ARU-MC-G4-TOOL-PROBE-BINDING-001`.

### Implemented branch contract

Branch `fix/geant4-tool-probe-binding` adds `ccb_geant4_tool_probe_binding_v1`:

1. require a PASS, self-digested `ccb_geant4_cmake_toolchain_attestation_v1` parent;
2. require the current CMake/C++ alias, resolved path, size, SHA-256 and symlink projection to equal the parent observation;
3. open the already-resolved regular executable once and hash that open descriptor;
4. execute `/proc/self/fd/{fd} --version` with that descriptor inherited, so the probe entrypoint is the same opened object rather than a fresh resolution of the cache alias;
5. re-hash the same descriptor after the probe and require identical device/inode/mode/size/SHA-256;
6. re-resolve/re-hash the original alias and require an unchanged path/target projection;
7. self-digest the child receipt with exact stdout/stderr hashes and explicit non-authorising limitations.

### Competing mechanisms

- Hash target then probe original alias: rejected by path-transition counterexample.
- Hash target then probe resolved pathname with only post-check: bounded improvement, but still reopens by pathname.
- Hash/open once and execute the same open file through Linux procfs: survives for this local entrypoint-binding atom.
- Treat the bound entrypoint as evidence for dynamic libraries, wrapper child compilers, actual build invocations or Geant4 events: rejected; those are separate children.

### Executed deterministic evidence

A standalone reconstruction of the committed implementation and fixtures on Linux/Python returned `6 passed in 0.06s`, no RNG. Fixtures cover stable direct tools, stable symlink aliases, a symlink target transition during the probe, executable self-mutation during the probe, parent-attested bytes changed before probing, and nonzero probe exit.

The repository branch also adds both the tool and tests to the curated ruff lane. Exact-head GitHub CI has not yet been observed for this branch, so it is not merge-authorised yet.

### Four sequential AI reviews

- **Build/physics integration lead — ACCEPT bounded entrypoint binding / REVISE build provenance.** The alias race is real; the new open-file mechanism closes it locally. Actual compiler/linker invocation remains unobserved.
- **Adversarial mechanism reviewer — ACCEPT local mechanism / BLOCK transitive dependency claims.** A bound executable can still be dynamically linked or launch wrapper children whose bytes are not bound.
- **Independent validation reviewer — ACCEPT deterministic software oracle / BLOCK physics inference.** No generated event or detector observable enters these tests.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** #1182 runtime/thread/input/output and compiled hostile controls remain unmet.

### Child atoms

- `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001`: link inputs and actually loaded Geant4/VGM/ROOT/system library bytes.
- `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`: bytes actually consumed by compiler/linker invocations.
- `ARU-MC-G4-WRAPPER-CHAIN-001`: identify/bind child compiler processes when the CMake-selected compiler is a launcher/wrapper.
- `ARU-MC-G4-RUNTIME-MANIFEST-001`: run-manager/thread mode, RNG engine/seeds, event count, model IDs, runtime input hashes, exit status, output ROOT/tree/schema/hash.

No production Geant4 executable/build tree, beam ROOT, production MC ROOT or detector-chain output was used. No angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.
