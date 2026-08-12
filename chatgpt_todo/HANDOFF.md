# Latest Handoff

## Root SiPM gitlink now points at a conflicted core commit; repair and CI closure are in flight

Selected atom: `ARU-SIPM-ROOT-GITLINK-EXECUTION-CLOSURE-001`.

Protected root `main@09991a0f598b51b030ca180507c6ea5741acc7e0` was inspected after #1266 merged. That merge changed only `geant4/single_stave/sipm`, advancing it from `ccb-sipm-core@692857b...` to exact `0fc78af6679c421f7a01a85f421170bbb92cce82`. Exact upstream source at `0fc78af...` contains unresolved Git merge delimiters in compiled/test files, including `src/Config.cc`; therefore the current root gitlink is not an executable/source-closed dependency state.

Current upstream core is `3627dc87137a9f33f511a755671414b11853c0a0`, a strict two-commit descendant of `0fc78af...`. `caf6bdc...` repairs the three contaminated files, and `3627dc...` adds `tools/check_conflict_markers.py` plus a Core CI gate that runs the self-test/repository scan before configure/build/CTest. Exact main-push Core CI run `31548111836` completed SUCCESS on `3627dc...`.

The root protection gap is independent and material. Pre-repair `.github/workflows/mc_validation_ci.yml` used plain `actions/checkout@v4`; submodule checkout is not enabled by default. Thus root protected Python/static CI could be green without materializing or compiling the exact core commit named by the gitlink. This is the mechanism that must be closed at the root integration layer, not merely documented upstream.

Repair branch `audit/sipm-pin-conflict-repair-v1` was created from exact root main with no force-push. Commit `20475c13663553735289e210a4714cbefae7e852` repins only the gitlink to `3627dc...`. Commit `92586447255b98ad851ab1116f444e5b38c8ce33` upgrades the required root test job to recursively checkout submodules and run the pinned core conflict-marker self-test/scan, CMake configure/build, and CTest before the root Python suite. The controlling invariant is:

`AUTHORISE_ROOT_SIPM(h_root,h_core) => gitlink(h_root)=h_core && CoreCI(h_core)=SUCCESS && ConflictMarkerScan(h_core)=PASS && RootRequiredCI(h_root,h_core)=SUCCESS`.

A direct local `git ls-remote` attempt failed with `Could not resolve host: github.com` (status 128), so no local clone/build PASS is claimed. Upstream exact-head Core CI is real execution evidence; root exact-head protected CI remains the next merge gate.

A governance contradiction was also confirmed. #1067 is currently closed/completed, but its own acceptance criteria and prior issue reviews retain unresolved source-byte binding, calibration/resampling validation, positive measured-authorisation semantics, run-metadata serialization, and historical-output audit. The campaign ledger labels #1067 `FIXED (core)` and still describes a prior `cf12c6b...` pin, which is no longer the current root state. This atom therefore requires reopening/correcting #1067 to PARTIAL/BLOCKED rather than treating the existence of fail-closed code upstream as scientific completion.

### Four sequential AI votes

**Detector-response integration lead — ACCEPT repair design / BLOCK merge pending protected root CI.** Exact broken source falsifies the counter-hypothesis that the desired fail-closed changes make `0fc78af...` an acceptable pin. Residual: final root branch bytes have not yet passed their required workflow.

**Adversarial mechanism/provenance reviewer — REJECT pointer-only validation / ACCEPT recursive dependency execution.** A green superproject Python job did not observe the C++ dependency because submodules were not checked out. Future authorization must execute the exact gitlink.

**Independent validation reviewer — ACCEPT upstream Core CI / BLOCK root integration until exact-head root CI.** Core run `31548111836` is sufficient software evidence for `3627dc...` itself, but not for its composition into root main. No detector sample participates.

**Claims/provenance reviewer — REOPEN/REVISE #1067 / BLOCK measured-electronics claims.** Source/build integrity is necessary but does not provide measured calibration authority or output-level provenance closure.

Archive: `chatgpt_todo/archive/2026-08-12T015000Z_ARU-SIPM-ROOT-GITLINK-EXECUTION-CLOSURE-001.md`.

Next immediate action is exact-final-head root CI on the bounded PR and integration only after every required duplicate context succeeds. Once the gitlink execution gate is integrated, the highest-value scientific child is `ARU-ELEC-IMPULSE-RUN-METADATA-SERIALIZATION-001`: bind the exact core SHA, provenance status, waveform-affecting configuration, and canonical effective runtime-kernel identity into the production sidecar from the same state actually used by event simulation. Source-byte/calibration closure and historical-output audit remain separate children.

No beam bytes, production Geant4 sample, measured electronics waveform, DATA↔MC result, timing/PID metric, pile-up efficiency, rate, ESS, p-value, or public detector-performance quantity was generated or promoted.
