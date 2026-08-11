# Latest Handoff

## Active atom: Linux procfs initial-environment semantics

Protected source-of-truth at selection was `main@d6dc5ab29fc0ae6ac9d921a50c08b4554d14902d`, the squash merge of PR #1210. Exact predecessor head `ae6e8506f7caa79c31f211f56c7bb31761007600` passed MC Validation run `31476519812` with curated ruff, full unit tests, diagnostics upload and enforcement all successful. #1182 and CL-021 remain gated.

Current branch is `audit/geant4-loader-proc-env`, implementing `ARU-MC-G4-LOADER-PROC-ENV-001` under #1182 / `ARU-MC-G4-LOADER-SEARCH-001`.

### Key correction

The predecessor handoff treated the environment captured by `geant4_runtime_dependency_attestation.py` as if it were simply the program's post-start `getenv` state. Linux procfs has a different contract: `/proc/<pid>/environ` exposes the initial environment region associated with the currently executing image, and ordinary later `setenv`/`putenv` changes are not reflected. This means the existing runtime provenance has more launch-region information than previously credited.

That does **not** turn procfs into an immutable `execve(envp)` trace. The target can overwrite the initial bytes and can relocate the procfs environment region with `PR_SET_MM_ENV_START`. Therefore the new attestor is deliberately one-sided: stable presence is observed evidence at the attestation boundary; absence is not proof of historical launch absence.

### Exact contract

Compose PASS `ccb_geant4_runtime_dependency_attestation_v1` and PASS child `ccb_geant4_loader_secure_state_attestation_v1`, require exact parent digest and identical `(pid,starttime_ticks)`, read `/proc/<pid>/environ` twice, require the two byte strings identical and process identity stable, and require every loader key already recorded by the runtime receipt to reproduce exactly from the procfs bytes. Duplicate tracked keys or any receipt/proc mismatch fail closed.

The output records total procfs environment bytes/SHA-256 and per-key semantics:

- present -> `OBSERVED_AT_ATTESTATION_BOUNDARY`;
- absent -> `ABSENT_AT_OBSERVATION_NOT_PROOF_OF_EXECVE_ABSENCE`.

`AT_SECURE=1` continues to block `LD_LIBRARY_PATH`/`LD_PRELOAD`/`LD_AUDIT` from loader-search authority. `AT_SECURE=0` remains unresolved for effective glibc secure behavior because `glibc.rtld.enable_secure=1` and exact libc/loader semantics are separate dependencies.

### Discriminating evidence executed

Authoritative references: Linux `proc_pid_environ(5)`, Linux `ld.so(8)`, GNU libc Dynamic Linking Tunables.

Local Linux/glibc negative control used GCC 14.2.0 and glibc 2.41. A tiny C process was launched with `GLIBC_TUNABLES=glibc.rtld.enable_secure=1`, loader-variable marker values and a benign control marker. Inside the program, `getenv` returned NULL for `GLIBC_TUNABLES`, `LD_LIBRARY_PATH`, `LD_PRELOAD`, and `LD_AUDIT`, while `/proc/<pid>/environ` simultaneously retained all exact launch strings. Procfs snapshot: 4584 bytes, SHA-256 `cd79ecfc3819a94132881036be26e4cfbcbd6def4e02224a3388411ee446f4fd`. This falsifies the hypothesis that loader sanitization necessarily erases those launch strings from procfs; it is not a production HIBEAM result.

Exact authoring-byte deterministic test run, Python 3.13.5/Linux/no RNG:

`PYTHONPATH=/tmp/ccb_new python3 -m pytest -q /tmp/ccb_new/tests/test_geant4_loader_initial_environment_attestation.py` -> `10 passed in 0.54s`; `py_compile` passed.

Hostile matrix: stable exact match, kernel-secure interpretation, absence semantics, proc/runtime mismatch, duplicate key, wrong parent receipt, process mismatch, malformed secure auxv record, mutation between procfs reads, and a real Linux child whose `os.environ` value changes after exec while procfs keeps the launch-region value.

Exact source identities now published on the branch:

- `tools/audit/geant4_loader_initial_environment_attestation.py`: 13024 bytes, SHA-256 `a1d3074fcf998c17abf5d99752f399d98aca491f184cad704224ea08111ab9b3`, Git blob `ab0f087fd2a138101bd269b97afc8b607ccb9036`;
- `tests/test_geant4_loader_initial_environment_attestation.py`: 9730 bytes, SHA-256 `9a81c81ea51ac27e94d925635b9ba800d6acc1742f9409ca57e3c161f7e41203`, Git blob `f3c79dbf80a064a28885046dcbed08940f2f174f`.

Local ruff is unavailable. The workflow has been extended so repository CI must supply that gate.

### Four sequential AI review passes

- **Runtime/physics integration lead — REVISE prior post-start characterization / ACCEPT bounded initial-region presence.** Strongest counter was that procfs only reflects the post-loader program environment. Post-exec mutation and secure-sanitization controls falsified that. Residual: earlier overwrite/remap and real HIBEAM runtime.
- **Adversarial Linux/loader reviewer — ACCEPT stable observation / BLOCK immutable execve claim.** Strongest counter was that “initial environment” means immutable syscall log. `PR_SET_MM_ENV_START` and in-place writes eliminate that stronger model. Residual: loader argv, cwd, cache/config, tokens/hwcaps, preloads/audits.
- **Independent validation reviewer — ACCEPT deterministic mechanism oracle / BLOCK HIBEAM and physics generalisation.** Ten local tests pass, but no production HIBEAM receipt or event exists.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** The entire generator→detector→DATA chain remains gated.

### Dependency refinement

`ARU-MC-G4-LOADER-PREEXEC-ENV-001` is narrowed rather than declared complete. Procfs presence is useful launch-region evidence, but an immutable pre-exec receipt is still needed to prove historical absence or rule out target overwrite/remap.

New children:

- `ARU-MC-G4-LOADER-ENV-REGION-MUTATION-001` — eliminate or bind post-exec overwrite/`PR_SET_MM_ENV_*` ambiguity;
- `ARU-MC-G4-LOADER-ARGV-001` — bind exact executable/dynamic-loader invocation and explicit loader options.

Existing children remain initial cwd, ld.so cache/config, `$ORIGIN/$LIB/$PLATFORM` and glibc hwcaps, preload/audit sources, linker/static inputs, late `dlopen`, relocation/GOT/PLT, wrapper/descendant identity, immutable consumption, runtime manifest, compiled source/stopping controls, event weights and detector response.

### Next gate

The branch already contains the new tool, hostile tests, curated ruff integration and immutable record `chatgpt_todo/archive/2026-08-11T094700Z_ARU-MC-G4-LOADER-PROC-ENV-001.md`. Open a focused PR and require fresh exact-final-head MC Validation. Merge only if curated ruff, full non-integration pytest, diagnostics/enforcement and current-main ancestry are all successful. Green CI validates the software/provenance primitive only.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance quantity was regenerated or promoted.
