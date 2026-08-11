# ARU-MC-G4-LOADER-PREEXEC-ENV-001 — pre-exec launch-state binding

**Status:** ACTIVE / IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED / REAL_HIBEAM_RUNTIME_BLOCKED / PHYSICS_INFERENCE_BLOCKED

## Parent and purpose

Parent: #1182 / `ARU-MC-G4-LOADER-SEARCH-001`, immediately after validated `ARU-MC-G4-LOADER-SECURE-STATE-001` (#1210).

This atom exists because the runtime loader receipts can observe process state after `exec`, while the loader search decision depends on the launch boundary itself. The bounded goal is to control and bind the exact executable, argument vector, working-directory object, and environment map used for a new Geant4/HIBEAM launch. It is not a retrospective reconstruction of a historical run.

During this session, #1210 exact head `ae6e8506f7caa79c31f211f56c7bb31761007600` passed both required `test` checks. MC Validation run `31476519812` completed successfully; its job had curated ruff and full unit-test steps green, with `1564 passed, 1 skipped, 8 xfailed, 1 xpassed`. #1210 was then marked ready and squash-merged as protected `main@d6dc5ab29fc0ae6ac9d921a50c08b4554d14902d`. This does not close #1182 or CL-021.

## Exact input/output contract

Inputs:

1. one self-digested PASS `ccb_geant4_build_binding_final_v1` receipt;
2. the final-receipt executable path and its expected `(bytes, SHA-256)` identity;
3. one absolute, non-symlink launch working directory;
4. the exact `argv` byte sequence to pass to the target;
5. the exact environment mapping to pass to `execve`;
6. one new, absolute, non-existing receipt-output path.

Output:

A self-digested `ccb_geant4_preexec_launch_v1` receipt with status `READY_TO_EXEC`, followed by descriptor-based `execve` of the already-opened target executable. `READY_TO_EXEC` is deliberately not an execution-success claim. A later runtime receipt must compose the same process identity and executable identity.

Units/state variables:

- executable byte count: bytes;
- executable content identity: SHA-256;
- process identity: `(pid, starttime_ticks)` from Linux procfs;
- cwd object identity: device major/minor, inode, mode;
- environment/argv byte identities: byte counts and SHA-256 digests;
- credentials observed before exec: uid/euid/gid/egid;
- no physical detector observable or physics unit is produced by this atom.

## Invariants

Let the final-build executable identity be

`I_F = (n_F, H_F)`.

Let the same opened executable descriptor be measured initially and immediately before exec as

`I_fd^0 = (n_0, H_0)` and `I_fd^1 = (n_1, H_1)`.

Require

`I_fd^0 = I_F = I_fd^1`.

This removes pathname-rebinding ambiguity. It does **not** prevent an in-place mutation of the opened inode after the final measurement; immutable consumption remains a child atom.

For environment mapping `E = {name_bytes -> value_bytes}`, require unique nonempty names containing neither `=` nor NUL and values containing no NUL. Define a deterministic audit projection by bytewise name sort:

`D_E = SHA256(concat_i(name_i || '=' || value_i || NUL))`.

The exact same mapping object is passed to `os.execve`. All `LD_*` entries and `GLIBC_TUNABLES` are separately exposed with value byte count/SHA-256/base64/UTF-8-for-display; unrelated environment values are not dumped into the receipt. The canonical sorted digest is evidence of the complete mapping, not a claim about raw `envp` array ordering inside Python/libc.

For argument bytes:

`D_A = SHA256(concat_i(argv_i || NUL))`,

with per-index byte count/SHA-256/base64/UTF-8 projection retained.

For the cwd descriptor, require the opened directory object's `(dev,ino,mode)` to remain stable, call `fchdir(cwd_fd)`, and recheck the same descriptor immediately before exec.

A future runtime-composition child must require

`(pid_preexec,starttime_preexec) = (pid_runtime,starttime_runtime)`

and exact target executable identity. Since `execve` replaces the process image without creating a new process, this is the intended cross-boundary composition key for a controlled direct launch.

## Competing mechanisms

### H1 — post-start procfs environment is sufficient

Rejected as a complete launch-authority mechanism. `/proc/<pid>/environ` is useful evidence about the initial exec environment, but observing it later is not equivalent to controlling the exact launch operation together with cwd, argv and executable identity. Loader secure-mode processing and future procfs/memory-state complications remain independent concerns.

### H2 — pathname launch after hashing is sufficient

Rejected. The pathname can be rebound after hashing. The implementation keeps the validated executable descriptor open and invokes `os.execve(fd, ...)` so the execution target is the opened object rather than a later path lookup.

### H3 — descriptor execution necessarily destroys `$ORIGIN` behavior

Not supported by the bounded local falsifier. A locally compiled ELF with `RUNPATH=$ORIGIN/lib` and a versioned shared library returned the same value (`42`) under normal pathname execution and descriptor-based `os.execve(fd, ...)` on the tested Debian/glibc/kernel environment. This is a local systems-control result, not a universal loader guarantee and not a HIBEAM test.

### H4 — receipt publication proves exec succeeded

Rejected. The receipt is written immediately before the exec call and is labelled `READY_TO_EXEC`; exec failure can occur after publication. A later runtime receipt with identical process/executable ancestry is mandatory.

### H5 — opened-fd execution makes executable bytes immutable

Rejected. Authoritative Linux `fexecve` documentation explicitly notes that checksum-then-exec through an fd still cannot prevent another process from modifying the file contents between those operations. The tool re-hashes the same descriptor immediately before publication/exec to narrow the window and records the residual blocker.

## Implementation

Clean transport branch after #1210 squash merge: `audit/geant4-preexec-launch-v2`, based exactly on `main@d6dc5ab29fc0ae6ac9d921a50c08b4554d14902d`.

Commits:

- `9a9da2a9f5c96620dbfe08f1896f0adca8adcfd2` — pre-exec launch attestor;
- `a224dfbb678d1a4a716ee2a6b351e1c0be23d2c2` — hostile/real descriptor-exec tests;
- `7f30377a8f2ab01dfc868112392ba9edc514e521` — curated MC-validation ruff inclusion.

Current branch content identities:

- `tools/audit/geant4_preexec_launch_attestation.py` Git blob `c0b4d12c3b148f3f5951ba90ba5339273621cd36`;
- `tests/test_geant4_preexec_launch_attestation.py` Git blob `9c5cac580a7161a2e52e0c1f9150179665e1e0d9`.

A precursor stacked branch used the exact same tests and an earlier tool blob `afb59e20a75395b4342ac8776369a2cc47f2f7e1`; exact GitHub-blob reconstruction there returned `14 passed in 1.10 s` and `py_compile` passed under Python 3.13/Linux/no RNG. The clean-v2 transport has a different tool blob after publication, so that precursor local result is **not** being reused as exact-byte validation for v2. The v2 branch must obtain exact-head curated ruff + full repository pytest before merge. This distinction preserves the repository-content-transfer contract introduced by #1209.

Hostile/positive tests include:

- complete environment-map digest and separate loader controls;
- invalid environment names, NULs and empty environment rejection;
- exact argv-byte/index preservation, including non-UTF-8 bytes;
- no-overwrite receipt publication;
- empty argv0 rejection;
- tampered final receipt;
- wrong final executable hash;
- non-ELF executable rejection;
- symlink cwd rejection;
- real Linux descriptor-exec integration using the exact Python interpreter ELF, requiring PID/start-time continuity across exec, exact cwd, exact environment digest and loader-control value, and target executable hash;
- self-digesting `READY_TO_EXEC` receipt with explicit runtime-child limitation.

## External authoritative facts used

Primary/authoritative documentation reviewed:

- Python `os.execve` documentation: on supported platforms `path` may be an open file descriptor;
- Linux `fexecve(3)`: descriptor execution is useful for checksum-then-execute and prevents the pathname from selecting a different file, but does not prevent modification of that file's contents in the interval;
- Linux `execveat(2)`: `AT_EMPTY_PATH` permits execution by file descriptor;
- GNU libc source/documentation for descriptor execution and dynamic-loader/tunable behavior;
- Linux `proc_pid_environ(5)` for the semantics and limitations of `/proc/<pid>/environ`.

These software facts do not constitute detector or generator validation.

## Four sequential AI review passes

### A. Domain/runtime physics lead

Evidence inspected: #1210 secure-state contract and CI, build-binding receipt, runtime dependency/link receipts, historical `geant4/setup_and_run.sh`, new pre-exec tool/tests, Linux/Python exec semantics.

Strongest counter-hypothesis: the existing post-start runtime receipt already contains enough environment information, so a controlled launcher adds no information.

Attempted falsifier: direct descriptor-exec integration verifies that the launcher can bind the exact executable object, argv, cwd and complete environment map while preserving `(pid,starttime_ticks)` into the target. This demonstrates a stronger causal launch contract than a later environment-only observation.

Residual uncertainty: real HIBEAM launch has not been executed; exact loader/interpreter/libc and loader-cache/config/token resolution are not yet bound; fd-table/signals/rlimits/namespaces and immutable consumption remain open.

Vote: **ACCEPT bounded pre-exec mechanism / REVISE end-to-end runtime integration**.

### B. Adversarial systems/mechanism reviewer

Evidence inspected: pathname-versus-fd mechanisms, no-overwrite publication, hostile fixtures, `$ORIGIN` local compiled control, documented fexecve mutation caveat.

Strongest counter-hypothesis: descriptor execution either introduces materially different loader semantics or fully solves executable identity.

Attempted falsifier: local `RUNPATH=$ORIGIN/lib` compiled control gave the same `42` result under pathname and fd execution, falsifying the simple claim that fd execution necessarily breaks `$ORIGIN` on the tested platform. The documented in-place-mutation caveat falsifies the stronger claim that fd execution makes bytes immutable.

Residual uncertainty: HIBEAM-specific loader behavior, exact interpreter/libc identity, in-place mutation window, envp ordering beyond mapping semantics, cache/config/hwcaps/preload/audit decisions.

Vote: **ACCEPT path-rebinding defense / BLOCK immutable-consumption or complete-loader authorisation**.

### C. Independent statistics/validation reviewer

Evidence inspected: deterministic fixture suite and real descriptor-exec integration; exact content-transfer distinction between precursor and v2 blobs.

Strongest counter-hypothesis: a locally green precursor authoring copy authorizes the clean-v2 branch.

Attempted falsifier: content identity differs for the v2 tool blob, so precursor local execution is deliberately not attributed to v2. Exact-head repository CI is required.

Residual uncertainty: exact-v2 ruff/full pytest pending; no statistical or physics population was sampled.

Vote: **ACCEPT deterministic oracle design / BLOCK merge pending exact-head CI / BLOCK physics inference**.

### D. Claims/provenance reviewer

Evidence inspected: CL-021 validation document, #1182, source/runtime provenance graph, current claim governance.

Strongest counter-hypothesis: a controlled launch receipt validates the historical MV3 scattering result.

Attempted falsifier: no production HIBEAM event, source sample, detector response, event weight, beam-data comparison or current-model B2/B8 result participates in this atom; numerous independent source and detector gates remain open.

Residual uncertainty: full generator/runtime manifest, source/stopping compiled controls, weights, detector-response chain, held-out data/MC validation and systematic envelope.

Vote: **ACCEPT provenance child / BLOCK CL-021 promotion**.

## Cross-scale propagation

Micro: exact bytes/object/environment/argv/cwd identities are bounded at the launch boundary.

Meso: a future runtime receipt can compose the same PID/start-time and target executable to show that the READY_TO_EXEC process became the observed process image.

Event: not yet reached; RNG engine/state, thread/run-manager mode, event count and runtime input consumption remain independent children.

Study/claim: no detector observable or CL-021 state changes. This atom only strengthens provenance for future campaigns.

## Child atoms spawned / retained

1. `ARU-MC-G4-PREEXEC-RUNTIME-COMPOSITION-001` — compose `READY_TO_EXEC` to runtime dependency/link/secure-state receipts by exact process and executable identity and prove the target actually started.
2. `ARU-MC-G4-LOADER-INTERPRETER-IDENTITY-001` — exact `PT_INTERP` dynamic loader + libc identity at launch/runtime.
3. `ARU-MC-G4-LOADER-CACHE-CONFIG-001` — bind loader cache/configuration inputs.
4. `ARU-MC-G4-LOADER-TOKEN-HWCAPS-001` — `$ORIGIN`/`$LIB`/`$PLATFORM`, hwcaps and direct/transitive search semantics.
5. `ARU-MC-G4-PRELOAD-AUDIT-001` — preload/audit inputs and actual mappings.
6. `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001` — close in-place executable/input mutation windows.
7. Existing linker-command/static-archive, late-dlopen, relocation/GOT/PLT, wrapper/descendant, runtime-manifest, compiled source/stopping, weight and detector-response atoms remain open.

## Claim/wiki consequences

No wiki/public physics wording is promoted. `docs/validation/CL-021_scattering_model.md` remains OPEN/GATED. #1182 remains open. No measured-data, simulation-performance or detector-performance claim is changed by this atom.

## Blockers

- exact-head v2 CI not yet run;
- no immutable real HIBEAM executable/runtime receipt in this session;
- no full production Geant4 campaign or beam ROOT access in this atom;
- complete dynamic-loader search decision and immutable consumption remain unresolved.

## Next highest-value atom

First consume exact-head CI for this bounded launcher. If green, merge normally. Then implement `ARU-MC-G4-PREEXEC-RUNTIME-COMPOSITION-001` so the pre-exec receipt is not an orphaned readiness record; after that, bind exact loader/interpreter/libc and loader search/cache/token state before attempting any production generator claim.
