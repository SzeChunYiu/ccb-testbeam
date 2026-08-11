# Latest Handoff

## Validated atom: exact opened-byte binding for CMake/C++ version probes

PR #1202 is now on protected `main@6c7a74295d799c9e0a231365d3e5efb690bd25a9`. The predecessor v1 CMake toolchain attestation hashed a resolved tool target but probed the original cache spelling; a mutable alias could therefore separate recorded bytes from the executable entrypoint that produced `--version` output.

The merged child `ccb_geant4_tool_probe_binding_v1` requires the parent attestation digest and path/target projection to remain unchanged, opens the already-resolved regular executable, hashes that open file description, executes the same inherited object through Linux `/proc/self/fd/{fd}`, re-hashes the same descriptor after the probe, and finally re-resolves/re-hashes the original alias. Linux exposes process file descriptors under `/proc/<pid>/fd`, and Python 3.11 `subprocess.pass_fds` preserves selected POSIX descriptors in the child; these are mechanism facts only, not Geant4 validation.

### Executed falsifiers and CI

Local deterministic reconstruction, no RNG, returned `6 passed in 0.06s`. Hostile fixtures cover stable direct executables, stable symlink aliases, symlink target transition during probe, executable self-mutation during probe, parent-attested bytes changed before probing, and nonzero probe exit.

The first exact-head CI run `31447800441` on `148bd06266665c2ef597697538d821b9b8752120` was ruff-clean with `1499 passed, 1 skipped, 8 xfailed, 1 xpassed`, but became stale when #1189 advanced main. The attempted normal protected merge was rejected; no bypass or force update was used. The branch was then refreshed by a non-force merge commit onto `main@49797c9f54e889204b4679848ea7bf805184710c`. Compare reported `status=ahead`, `behind_by=0`, merge base exactly current main. Fresh exact-head run `31448197610` was ruff-clean with `1502 passed, 1 skipped, 8 xfailed, 1 xpassed`; only that refreshed evidence authorised the squash merge to `6c7a74295d799c9e0a231365d3e5efb690bd25a9`.

### Four sequential AI reviews

- **Build/physics integration lead — ACCEPT bounded entrypoint binding / REVISE build provenance.** The alias race is closed locally; actual compiler/linker invocation remains unobserved.
- **Adversarial systems reviewer — ACCEPT local mechanism / BLOCK transitive dependency claims.** A bound entrypoint can still be dynamically linked or launch wrapper children. Probe output is checked after capture rather than streaming-bounded; keep that as `ARU-MC-G4-PROBE-OUTPUT-BOUND-001` if hostile tools become part of the threat model.
- **Independent validation reviewer — ACCEPT repository software closure / BLOCK physics inference.** Both stale-base and refreshed-current-base cases were observed, and only the refreshed green head merged. No generated event entered the tests.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** #1182 still lacks link/runtime-library identity, immutable consumption, run-manager/thread/RNG/input/output provenance and compiled hostile controls.

### Next highest-value atom

`ARU-MC-G4-LINK-RUNTIME-IDENTITY-001`: distinguish configured package labels/roots, link-time dependency inputs, and the shared objects actually mapped at runtime. Start from the exact executable hash already bound by #1199/#1201/#1202; derive and test a contract around linker metadata, `DT_NEEDED`/RPATH/RUNPATH (or platform equivalent), loader search order/environment, resolved library path plus SHA-256, static-link cases, symlink replacement and runtime mappings. Negative controls should preserve nominal version/soname while changing bytes, change loader search order, and separate build-tree link identity from runtime-loaded identity.

Parallel children remain `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`, `ARU-MC-G4-WRAPPER-CHAIN-001`, `ARU-MC-G4-PROBE-OUTPUT-BOUND-001`, and `ARU-MC-G4-RUNTIME-MANIFEST-001`. Compiled hostile cross-section/stopping-table controls remain under #1182/#1058.

No production Geant4 campaign, beam ROOT, production MC ROOT, detector response, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.
