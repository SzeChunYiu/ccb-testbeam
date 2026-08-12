# ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001

- **Status:** `PARTIAL / BOUNDED SOFTWARE-PROVENANCE CHILD VALIDATED`
- **Parent:** #977 (`OPEN/PARTIAL`)
- **Cross-dependencies:** #1067, #1072, #1280, #1282, #1284
- **Implementation:** PR #1285
- **Pre-merge main:** `d155b0f2f5a626fe39fc228b68809db8fb686a2e`
- **Exact validated PR head:** `a7dbf2e129caa5fef1b710610c5141cc0fcdd493`
- **Merged main:** `d2cd26bf5ee02b80defec2df5e3a178e8b963c5d`
- **Pinned ccb-sipm-core:** `3627dc87137a9f33f511a755671414b11853c0a0`

## Atomic contract and scientific meaning

This atom is build/execution provenance, not detector-response validation. The input state consists of a frozen campaign source-intent manifest, one clean superproject source revision, the ccb-sipm-core gitlink, a configured CMake build directory, configured CMake/C++ compiler and Geant4 package sentinel, and an executable `ccb_stave_sim`. The output is a canonical immutable build receipt plus a runtime probe that can be checked before event zero and after the run.

Let `H_src` be the campaign superproject commit, `H_core` the core gitlink resolved from that commit, `H_compiled_src` and `H_compiled_core` the source labels compiled into the executable, `H_exe = SHA256(bytes(ccb_stave_sim))`, and `R_build` the canonical build receipt. The bounded authorising invariant is

`H_compiled_src = H_src`,

`H_compiled_core = H_core`,

`SHA256(executing ccb_stave_sim) = R_build.executable.sha256`,

with exact path/byte-count/SHA-256 re-observation of `CMakeCache.txt`, the configured CMake executable, configured C++ compiler, and `Geant4Config.cmake`. The receipt's own canonical bytes are SHA-256 bound into campaign execution intent.

This closes the stale-build substitution mechanism at the executable/source-revision layer. It does not attest every compiler/linker command, every input header/library byte, the runtime dynamic-loader image set, or detector physics.

## Competing mechanisms and eliminations

1. **Current BUILD path or checkout implies executable identity.** Eliminated: a stale binary can survive a source-tree advance.
2. **Compile-bound ccb-sipm-core SHA alone identifies the whole simulator.** Eliminated: Geant4 integration/source and toolchain can change independently.
3. **mtime or caller `CCB_GIT_COMMIT` identifies the executable.** Eliminated: these are mutable and not content-addressed.
4. **Source intent + compile-bound root/core + independently measured executable SHA + runtime self-hash + frozen configured-toolchain/package sentinels.** Survives as the bounded implementation.

Equivalent weak descriptions based only on labels, paths or timestamps are collapsed into the same non-authorising family because none binds executable bytes.

## Exact implementation

PR #1285 adds:

- `--build-provenance-json`, executed before AppConfig/Geant4 initialization, reporting compile-time root/core/toolchain labels and SHA-256/byte count of `/proc/self/exe`;
- `CCB_AUTHORISING_BUILD_RECEIPT=ON`, which requires a clean Git source and creates `ccb_stave_sim.build.json` plus its digest after linking;
- `scripts/single_stave/sipm_build_receipt.py`, which hashes stable regular-file snapshots of the executable, CMake cache, configured CMake and C++ compiler binaries, and `Geant4Config.cmake`, probes the runtime executable, and checks source/campaign identity;
- campaign freezing and compute-node pre/post-run receipt verification; and
- `ccb-sipm-campaign-point/2`, recording source/core/executable closure without promoting detector truth.

## Adversarial CI falsifier preserved

Initial exact PR head `e7a278708c411ac634ed0d34dd13218f33e8ce8a` ran MC Validation `31572927526`, job `94038592792`. Recursive core checkout, core build/7-of-7 CTests, ruff and governance gates passed, but the full Python suite ended:

`5 failed, 2139 passed, 2 skipped, 8 xfailed, 1 xpassed`.

All five failures were the same production-cleanliness rejection:

`D geant4/single_stave/sipm`.

The test fixture had inserted a `160000` gitlink with `git update-index --cacheinfo` but had not materialized the nested worktree. Therefore Git correctly classified the submodule path as deleted. The failure demonstrates that the clean-source gate was active and fail-closed; it did not justify weakening that gate.

## Solve-first fixture repair and exact-head validation

Commit `a7dbf2e129caa5fef1b710610c5141cc0fcdd493` changes the synthetic fixture to create a real nested Git repository, commit exact core fixture bytes, record that actual commit as the superproject gitlink, assert the root worktree is clean, and propagate the dynamic core SHA into the fake executable/manifest. The production `require_clean=True` source predicate is unchanged. An incidental invalid Python regex-escape warning was removed with a raw-string assertion.

Both exact final-head protected contexts succeeded:

- pull-request MC Validation run `31573602554`, job `94040671016`;
- push MC Validation run `31573598586`, job `94040659427`.

The PR-run log records recursive checkout of exact core `3627dc87137a9f33f511a755671414b11853c0a0`, GNU C++ `13.3.0`, conflict-marker guard PASS, core build success, 7/7 CTests PASS, ruff PASS, governance PASS, and full suite:

`2144 passed, 2 skipped, 8 xfailed, 1 xpassed, 18 warnings in 126.07s`.

Enforcement observed `SIPM_CORE_STATUS=0`, `RUFF_STATUS=0`, `PYTEST_STATUS=0`. Validation artifact `validation-logs-31573602554-1` is artifact ID `9132366852`, ZIP SHA-256 `b13a5a119053be8c84250ef9f72ac8929707e72d7107e48f22bf9f883bab6b7b`.

After both contexts were green, PR #1285 was marked ready and squash-merged with expected-head guard. Protected `main` advanced from `d155b0f2...` to exact `d2cd26bf5ee02b80defec2df5e3a178e8b963c5d`. The merge message uses `Refs`, not `Closes`.

## New child assumption exposed by Git semantics

`ARU-SIPM-BUILD-SUBMODULE-WORKTREE-IDENTITY-001` remains unresolved. A Git-only negative control constructed a superproject containing a gitlink. With the gitlink path absent,

`git status --porcelain=v1 --untracked-files=all`

returned ` D geant4/single_stave/sipm`. After creating only an empty directory at that path, the same command returned an empty status. Therefore

`clean(superproject)  NOT=>  is_git_worktree(core_path) AND HEAD(core_path)=H_core`.

An authorising source-worktree contract must explicitly establish

`is_git_worktree(P_core) AND HEAD(P_core)=H_core AND clean(P_core)`

rather than relying on root cleanliness alone. This child is material, so the broader build/source provenance parent remains `PARTIAL` even though #1285's stale-executable closure is integrated.

## Cross-scale propagation

- **Micro/software:** exact executing binary bytes and selected configured-toolchain/package sentinels are content-bound.
- **Run:** orchestrated campaign jobs verify the receipt before event zero and after the run and compare sidecar root/core identity.
- **Study:** campaign rows can now distinguish source intent from stale executable substitution for this path.
- **Claim:** no detector-performance, measured-electronics, timing, PID, pile-up, efficiency or DATA↔MC claim is promoted. #977 and #1067 remain open; #1072 requested-versus-effective response physics remains unresolved.

## Four sequential AI reviews

### (a) Detector-response/build-provenance lead
- Background: C++/CMake, Geant4 integration, executable provenance.
- Evidence inspected: exact #1285 diff, build receipt/runtime probe, initial red CI, repaired exact-head CI, campaign launcher and sidecar checks.
- Strongest counter-hypothesis: source path/current checkout is sufficient to identify the binary.
- Falsifier: stale-build substitution contract and exact executable SHA/runtime self-hash path.
- Residual uncertainty: compiler/linker invocation stream, runtime libraries, nested core worktree identity.
- Vote: **ACCEPT #1285 bounded stale-build closure; BLOCK #977 COMPLETE**.

### (b) Adversarial Git/provenance reviewer
- Background: Git object/worktree semantics, supply-chain substitution, fail-closed state machines.
- Evidence inspected: cacheinfo-only fixture, exact CI failure, local missing-path versus empty-directory Git negative control.
- Strongest counter-hypothesis: clean superproject status proves the core gitlink is materially checked out correctly.
- Falsifier: empty directory at the gitlink path can leave root status clean.
- Residual uncertainty: explicit nested worktree/HEAD/clean check not yet implemented.
- Vote: **ACCEPT fixture correction; REJECT root-cleanliness sufficiency; BLOCK complete source-worktree identity**.

### (c) Independent validation reviewer
- Background: reproducible testing, negative controls, exact-head CI, software-validation boundaries.
- Evidence inspected: red head `e7a278...`, repaired head `a7dbf2...`, both required workflows, aggregate tests and enforcement statuses.
- Strongest counter-hypothesis: the first red run invalidates the production design.
- Falsifier: all failures localize to the synthetic gitlink fixture while unrelated production/core gates pass; corrected fixture makes both exact-head contexts green without weakening production code.
- Residual uncertainty: no authorising Geant4 campaign or detector population was executed.
- Vote: **ACCEPT deterministic/software integration closure; BLOCK detector inference**.

### (d) Claims/provenance reviewer
- Background: code→artifact→claim traceability and research-universe state governance.
- Evidence inspected: #977 acceptance criteria, #1067/#1072 dependencies, #1285 merge message and scientific-scope labels.
- Strongest counter-hypothesis: build receipt integration completes run provenance.
- Falsifier: unresolved effective-response/calibration, nested worktree, runtime dependency, historical-output, and requested/effective operating-point children remain.
- Residual uncertainty: historical pre-#1280 outputs and measured-response authorization.
- Vote: **ACCEPT bounded child as VALIDATED/PARTIAL; KEEP #977/#1067 OPEN and claims gated**.

## Next highest-value atom

`ARU-SIPM-BUILD-SUBMODULE-WORKTREE-IDENTITY-001`: explicitly require `geant4/single_stave/sipm` to resolve as its own Git worktree, require its exact `HEAD` to equal the superproject gitlink used by the receipt/campaign, require the nested worktree to be clean, add empty-directory and wrong-HEAD hostile fixtures, and execute exact-head protected CI. After that, remaining higher-level provenance children include exact compiler/linker/runtime dependency attestation, shared launcher/verifier byte binding, direct/manual analyzer receipt gating, and historical sidecar authenticity.

No beam bytes, production Geant4 detector population, measured electronics calibration, DATA↔MC result, timing/PID metric, pile-up efficiency, rate, ESS, p-value, or detector-performance quantity was generated or promoted.