# Latest Handoff

## Active atom: Linux process-visible argv region

Protected source-of-truth at selection was `main@41a568a7296ac947e9ecb5baf540b0505c0edad1`, the squash merge of PR #1211. #1182 and CL-021 remain gated.

Current branch is `audit/geant4-loader-argv`, implementing `ARU-MC-G4-LOADER-ARGV-001` under #1182 / `ARU-MC-G4-LOADER-SEARCH-001`.

### Exact scientific boundary

`/proc/<pid>/cmdline` is treated only as a process-visible argument-region observation at one stable boundary. It is not promoted to an immutable historical `execve(argv)` trace. Linux permits a process to overwrite argv string bytes and to move the region exposed through procfs with `PR_SET_MM_ARG_START/END`. `argv[0]` is not executable identity; the parent runtime receipt's content-bound `/proc/<pid>/exe` measurement remains the separate executable-identity primitive.

### Exact contract

Compose a PASS `ccb_geant4_runtime_dependency_attestation_v1`; verify its self-digest; take parent `(pid,starttime_ticks,exe_link)`; require matching live starttime and executable link; read `/proc/<pid>/cmdline` twice; require exact byte equality; preserve every observed NUL-delimited slot without text normalization; reread starttime and executable link; serialize raw/per-slot byte counts, SHA-256, base64 and optional UTF-8; self-digest the result as `ccb_geant4_loader_argv_attestation_v1`.

The stable observation means `OBSERVED_STABLE_AT_ATTESTATION_BOUNDARY` only. Historical `execve(argv)` remains unresolved because the argument region is mutable.

### Mechanisms and discriminators

Competing mechanisms were direct target exec, arbitrary or rewritten argv0, explicit glibc dynamic-loader invocation, post-exec string mutation, `PR_SET_MM_ARG_START/END`, and separate `/proc/<pid>/exe` redirection through `PR_SET_MM_EXE_FILE`.

A local C process was launched with `alpha beta`, rewrote its argv0 bytes to `MUTATED_ARGV0`, then slept. `/proc/<pid>/exe` still named the program while `/proc/<pid>/cmdline` exposed `MUTATED_ARGV0\0alpha\0beta\0`. That falsifies immutable launch-argv semantics.

A second Linux control explicitly launched the glibc dynamic loader with `/bin/sleep 3`. `/proc/<pid>/exe` identified the loader and cmdline exposed loader+target+argument. This discriminates ordinary explicit-loader invocation from a parent runtime receipt that identifies the final HIBEAM executable, while leaving `PR_SET_MM_EXE_FILE` as its own unresolved child.

Repository `geant4/setup_and_run.sh` directly invokes `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root`. Because config, macro and output spellings are relative, initial cwd is immediately material to their scientific identity.

### Deterministic validation executed

Exact authoring-copy run, Python 3.13.5/Linux/no RNG:

`python3 -m pytest -q tests/test_geant4_loader_argv_attestation.py` -> `11 passed in 1.40s`.

`python3 -m py_compile tools/audit/geant4_loader_argv_attestation.py tests/test_geant4_loader_argv_attestation.py` -> PASS.

Local ruff is unavailable; no local ruff PASS is claimed.

Hostile matrix covers nominal HIBEAM-style args, empty/non-UTF8 slots, tampered parent receipt, process mismatch, executable-link mismatch, cmdline mutation between reads, process identity mutation after read, empty cmdline, a real `/bin/sleep` child, explicit glibc-loader launch, and CLI wrong-digest fail-closed behavior.

### Exact content publication

- `tools/audit/geant4_loader_argv_attestation.py`: 9263 bytes, SHA-256 `4d1a8a195b10d40303dfab9bf8aac9605969134e65f8c114ea54dddb870cfba3`, Git blob `80e51cfe45037f95cc86039506a7dcee648f4474`, first commit `927bcb2d067cc46acc4a77762d94bd715d9080de`.
- `tests/test_geant4_loader_argv_attestation.py`: 9259 bytes, SHA-256 `3de0b2d5d736f2e5cb38034a5fbe848ae2790be2382861ae454525c1b85546b0`, Git blob `6d2a962b329cf6df9c2b08f08d22473733dfea1d`, first commit `3aecf750fe492eb03622a914de990ded6e43f5ef`.
- curated MC-validation ruff inclusion: `3c2d589215621aa1f6747b66bd069f9cee92708c`.
- immutable ARU record: `chatgpt_todo/archive/2026-08-11T105100Z_ARU-MC-G4-LOADER-ARGV-001.md`.

### Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT bounded observation / REVISE historical invocation.** Strongest counter: stable procfs cmdline is exact launch argv. The argv-rewrite control falsified it. Residual: pre-exec argv, initial cwd, real HIBEAM runtime and exact input consumption.
- **Adversarial Linux/loader reviewer — ACCEPT discriminator / BLOCK historical direct-exec claim.** Strongest counter: argv0/cmdline first slot identifies the executed program. Explicit-loader and argv-rewrite controls falsified it. Residual: `PR_SET_MM_EXE_FILE`, argument-region relocation, wrappers/descendants and later exec boundaries.
- **Independent validation reviewer — ACCEPT deterministic oracle / BLOCK HIBEAM and physics inference.** Eleven deterministic tests pass; no Geant4 event or detector observable participates. Exact-head repository lint/full pytest remain required.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Relative input paths, cwd, input-byte consumption, RNG/thread/event state, output identity, compiled source/stopping controls, event weights and detector response remain open.

### Children and next scientific atom

New/refined children:

- `ARU-MC-G4-LOADER-INITIAL-CWD-001` — highest-value next child because the historical run front door uses relative config/macro/output paths;
- `ARU-MC-G4-LOADER-ARGV-REGION-MUTATION-001` — pre-exec/no-overwrite evidence for historical argv claims;
- `ARU-MC-G4-LOADER-EXE-REDIRECTION-001` — bind or eliminate `PR_SET_MM_EXE_FILE`;
- `ARU-MC-G4-RUNTIME-ARGUMENT-SEMANTICS-001` — versioned HIBEAM option parsing and exact config/macro/output consumption.

Existing cwd/cache/token-hwcaps/preload-audit and downstream linker/runtime/source/weight/detector gates remain open.

### Concurrent repository state

Open PR #1212 is unrelated to this atom. Its MC Validation run `31483436146` completed with full pytest passing (`1594 passed, 1 skipped, 8 xfailed, 1 xpassed`) but enforcement failed because newly exposed base-freshness tool/test contain two ruff `I001` import-order findings. Do not treat that run as authorization for this branch.

### Next gate

Open a focused draft PR for `audit/geant4-loader-argv` and require fresh exact-final-head MC Validation. Merge only if curated ruff, full non-integration pytest, diagnostics/enforcement, and current-main ancestry all pass. Green CI validates only the software/procfs primitive. No production HIBEAM process or event population was produced in this session.
