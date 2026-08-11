# Latest Handoff

## Selected atom: bind CMake/C++ version probes to the exact opened executable bytes

Protected main is now `49797c9f54e889204b4679848ea7bf805184710c`. PR #1201 is validated on main, and concurrent PR #1189 subsequently merged the repository's current-base ancestry guard. That concurrent change is directly relevant here: #1202's first exact-head MC Validation run was green, but main advanced before merge, so its first green head is now intentionally non-authorising until the branch is refreshed and retested.

### Why this child exists

For a mutable alias `p` and resolved target `r`, the v1 toolchain attestation sequence is approximately `hash(r)` then `exec(p)`. A symlink/path transition between those observations can make the stored SHA-256 and version output refer to different executable entrypoints. The selected atom is `ARU-MC-G4-TOOL-PROBE-BINDING-001` / `PROV-G4-CMAKE-002` under #1182.

### Implemented contract

PR #1202 / branch `fix/geant4-tool-probe-binding` adds `ccb_geant4_tool_probe_binding_v1`:

1. require a PASS, self-digested `ccb_geant4_cmake_toolchain_attestation_v1` parent;
2. require the current CMake/C++ alias, resolved path, size, SHA-256 and symlink projection to equal the parent observation;
3. open the already-resolved regular executable once and hash that open descriptor;
4. execute `/proc/self/fd/{fd} --version` with that descriptor inherited, so the probe entrypoint is the same opened object rather than a fresh resolution of the cache alias;
5. re-hash the same descriptor after the probe and require identical device/inode/mode/size/SHA-256;
6. re-resolve/re-hash the original alias and require an unchanged path/target projection;
7. self-digest the child receipt with exact stdout/stderr hashes and explicit non-authorising limitations.

### Competing mechanisms and falsifiers

Hash-target/probe-original-alias is rejected by an injected alias transition. Hash-target/probe-resolved-path/post-check is a bounded improvement but still reopens by pathname. Open-once/hash/execute-that-open-object/re-hash/recheck-alias survives for this local Linux entrypoint-binding atom. Treating the bound entrypoint as evidence for dynamic libraries, wrapper child compilers, actual build invocations or generated physics remains rejected.

Local deterministic reconstruction, no RNG, returned `6 passed in 0.06s`. Fixtures cover stable direct tools, stable symlink aliases, symlink target transition during the probe, executable self-mutation during the probe, parent-attested bytes changed before probing, and nonzero probe exit.

First GitHub exact-head MC Validation run `31447800441` on `148bd06266665c2ef597697538d821b9b8752120` completed with curated ruff clean and `1499 passed, 1 skipped, 8 xfailed, 1 xpassed`. During that run protected main advanced from `1968f735...` to `49797c9f...` via #1189. The subsequent normal protected squash attempt on #1202 was rejected; no bypass or force update was attempted. This is now a positive real-world application of #1189's rule: stale green CI is evidence about the old integration base, not the current one.

### Four sequential AI reviews

- **Build/physics integration lead — ACCEPT bounded entrypoint binding / REVISE build provenance.** The alias race is real and the open-file mechanism closes it locally. Actual compiler/linker invocation remains unobserved.
- **Adversarial mechanism reviewer — ACCEPT local mechanism / BLOCK transitive dependency claims.** A bound executable can still be dynamically linked or launch wrapper children whose bytes are not bound. Probe output is also only bounded after capture in v1 of this child, so streaming/output-resource bounds remain a non-physics implementation child if hostile tools are in scope.
- **Independent validation reviewer — ACCEPT first deterministic CI / REQUIRE fresh current-base rerun.** The first exact-head CI is green, but it predates current main ancestry and cannot authorise merge after #1189.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** #1182 runtime/thread/input/output, link/runtime-library identity and compiled hostile controls remain unmet.

### Current repository action

Refresh #1202 onto `main@49797c9f54e889204b4679848ea7bf805184710c` through a normal non-force merge commit that preserves #1189's files and resolves only the competing `ACTIVE_TASK.md`/`HANDOFF.md` coordination edits. Require a fresh exact-head `test` CI on the refreshed head before retrying the protected merge.

### Child atoms

- `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001`: link inputs and actually loaded Geant4/VGM/ROOT/system library bytes.
- `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`: bytes actually consumed by compiler/linker invocations.
- `ARU-MC-G4-WRAPPER-CHAIN-001`: identify/bind child compiler processes when the CMake-selected compiler is a launcher/wrapper.
- `ARU-MC-G4-PROBE-OUTPUT-BOUND-001`: if hostile/untrusted tools are considered, make probe-output memory bounds operational rather than post-capture only.
- `ARU-MC-G4-RUNTIME-MANIFEST-001`: run-manager/thread mode, RNG engine/seeds, event count, model IDs, runtime input hashes, exit status, output ROOT/tree/schema/hash.

No production Geant4 executable/build tree, beam ROOT, production MC ROOT or detector-chain output was used. No angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.
