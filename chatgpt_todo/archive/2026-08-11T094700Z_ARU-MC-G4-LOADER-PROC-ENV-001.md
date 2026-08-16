# ARU-MC-G4-LOADER-PROC-ENV-001 — Linux procfs initial-environment semantics

Status: `ACTIVE / IMPLEMENTED_ON_BRANCH / LOCAL_FALSIFIERS_PASS / EXACT_HEAD_CI_REQUIRED / REAL_HIBEAM_RUNTIME_BLOCKED / PHYSICS_INFERENCE_BLOCKED`

Parent: issue #1182 / `ARU-MC-G4-LOADER-SEARCH-001`.

Protected source-of-truth inspected before work: `main@d6dc5ab29fc0ae6ac9d921a50c08b4554d14902d`, the validated squash merge of PR #1210. Exact predecessor PR head `ae6e8506f7caa79c31f211f56c7bb31761007600` passed MC Validation run `31476519812`; the merge commit explicitly leaves #1182 and CL-021 gated.

## Why this atom exists

PR #1210 correctly rejected the stronger statement that kernel `AT_SECURE=0` proves effective glibc non-secure loading. Its handoff, however, described the environment captured by `geant4_runtime_dependency_attestation.py` as a post-start environment observation that could have lost launch variables during dynamic-loader sanitization.

Linux procfs documentation gives a more specific contract: `/proc/<pid>/environ` exposes the initial environment region for the currently executing image, i.e. the environment set when that image was started by `execve`; ordinary later `putenv`/`setenv` changes are not reflected. The same documentation also states the target can relocate the region using `PR_SET_MM_ENV_START`, so this is not an immutable historical syscall trace. GNU libc documents that secure-execution handling can strip `LD_LIBRARY_PATH`, `LD_PRELOAD`, `LD_AUDIT`, and related variables from the environment seen by the program. GNU libc also documents `glibc.rtld.enable_secure=1`, which can enable secure behavior even when kernel `AT_SECURE` is zero.

This creates a distinct atomic question: what can the already-existing procfs observation prove, and what still requires a pre-exec capture?

## Exact input/output contract

Inputs:

- PASS `ccb_geant4_runtime_dependency_attestation_v1` receipt `R_runtime`;
- PASS child `ccb_geant4_loader_secure_state_attestation_v1` receipt `R_secure` whose parent digest is exactly `R_runtime.receipt_sha256`;
- exact live Linux process identity `S=(pid,starttime_ticks)` shared by both receipts;
- two reads of `/proc/<pid>/environ` around the attestation boundary.

Output schema: `ccb_geant4_loader_initial_environment_attestation_v1`.

Measurand: the exact byte string exposed by the kernel through the process's procfs initial-environment region at the bounded observation interval. It is **not** the program's current `getenv()` view and **not** an immutable trace of the historical `execve(envp)` syscall.

Let

`E0 = read(/proc/<pid>/environ)` and `E1 = reread(/proc/<pid>/environ)`.

The local acceptance invariants are:

1. receipt digests and parent ancestry verify;
2. `S_runtime = S_secure = S_proc_before = S_proc_after`;
3. `E0 = E1`;
4. `H(E0)=SHA256(E0)` and `|E0|` are serialized;
5. for every environment key already tracked by `R_runtime`, parsing `E0` yields exactly the same present/absent state and exact raw value bytes recorded by `R_runtime`;
6. duplicate tracked names fail closed;
7. `AT_SECURE` from `R_secure` remains one-sided: kernel-secure mode restricts/ignores loader environment inputs, whereas kernel zero does not by itself prove effective non-secure glibc behavior.

For a tracked key `k`, the evidence classes are intentionally asymmetric:

- key present in stable `E0/E1` -> `OBSERVED_AT_ATTESTATION_BOUNDARY` in the procfs initial-environment region;
- key absent -> `ABSENT_AT_OBSERVATION_NOT_PROOF_OF_EXECVE_ABSENCE`, because the target may have overwritten or relocated the environment region before observation.

## Competing mechanisms

### M1 — `/proc/<pid>/environ` is the current program environment

Prediction: if the dynamic loader strips a variable or the program later calls `setenv`, the procfs file should expose only the post-modification value/state.

Status: **eliminated** for ordinary environment-pointer changes. Linux procfs documentation specifies initial-environment semantics, and the local controls below directly falsify this mechanism.

### M2 — `/proc/<pid>/environ` is an immutable copy of exact historical `execve(envp)`

Prediction: every present/absent state is permanent historical evidence.

Status: **eliminated**. Linux documents that the target can change the memory region procfs uses via `PR_SET_MM_ENV_START`; the target can also overwrite initial environment bytes in place. Therefore neither presence nor absence is treated as an untouchable syscall log.

### M3 — `/proc/<pid>/environ` is a bounded observation of the initial environment region

Prediction: ordinary later environment-pointer changes need not alter it; dynamic-loader sanitization of the program-visible environment can coexist with launch strings remaining in procfs; the region nevertheless remains mutable/remappable by the process.

Status: **survives** and is the implemented model.

### M4 — launch environment alone reconstructs the dynamic-loader decision

Status: **eliminated**. Effective search also depends on `AT_SECURE`/libc behavior, direct loader invocation/options, executable and DSO `DT_RPATH`/`DT_RUNPATH`, initial cwd where relevant, `/etc/ld.so.cache` and configuration, `$ORIGIN/$LIB/$PLATFORM`, glibc hwcaps, preload/audit sources, and later `dlopen`/`dlmopen` activity.

## Authoritative external facts inspected

Primary/authoritative documentation used for the source-to-claim map:

- Linux man-pages `proc_pid_environ(5)`: `/proc/<pid>/environ` exposes the initial environment set when the program was started via `execve`; ordinary later environment modification is not reflected; the process may relocate the referred region with `PR_SET_MM_ENV_START`.
- Linux man-pages `ld.so(8)`: `LD_LIBRARY_PATH` participates in dependency search unless secure-execution mode applies; secure mode can strip loader-control variables from the environment visible to the program; `LD_PRELOAD` and `LD_AUDIT` have their own secure-mode restrictions; loader command-line preload and other search sources are independent mechanisms.
- GNU libc manual, Dynamic Linking Tunables: `glibc.rtld.enable_secure=1` runs a program as if it were setuid for loader behavior and is intended for verification testing; it can set, but not unset, the secure state.

No literature/source statement is promoted beyond those bounded operating-system/libc semantics.

## Executed discriminating experiments

### E1 — post-exec environment mutation control

Repository test `test_real_procfs_keeps_launch_region_when_program_changes_environ` launches a Python child with `CCB_LAUNCH_MARKER=ccb_launch_before`; the child changes `os.environ['CCB_LAUNCH_MARKER']` to `ccb_runtime_after` after exec and sleeps. The parent reads `/proc/<pid>/environ` and requires the launch value to remain while the runtime replacement is absent. This directly distinguishes the procfs region from the program's later environment pointer state.

### E2 — glibc secure-sanitization negative control

Local bounded host experiment, not a HIBEAM run:

- Linux `6.18.35` x86-64;
- Python `3.13.5`;
- GCC `14.2.0`;
- glibc `2.41-12+deb13u3`;
- probe source `/tmp/ccb_envprobe.c`: 357 bytes, SHA-256 `18d344819f14eb1a5af5182778cfa0e29c9bb516353945bd3cdd657cb4893a09`;
- compiled probe: 16240 bytes, SHA-256 `edd81d6aad7c600ccbd1ddbf0cbee00fb978ee775d9014a788e8fee4a2cc632f`;
- compile command: `gcc -O2 -Wall -Wextra /tmp/ccb_envprobe.c -o /tmp/ccb_envprobe`;
- launch environment included `GLIBC_TUNABLES=glibc.rtld.enable_secure=1`, `LD_LIBRARY_PATH=/tmp/ccb_loader_marker`, `LD_PRELOAD=/tmp/ccb_preload_marker.so`, `LD_AUDIT=/tmp/ccb_audit_marker.so`, and `CCB_ENV_MARKER=launch_marker`.

Observed inside the started program via `getenv`: `GLIBC_TUNABLES`, `LD_LIBRARY_PATH`, `LD_PRELOAD`, and `LD_AUDIT` were all `<NULL>`, while `CCB_ENV_MARKER=launch_marker` survived.

Observed simultaneously through `/proc/<pid>/environ`: all four loader/tunable launch strings remained present with their exact values, together with `CCB_ENV_MARKER`. The procfs snapshot measured 4584 bytes with SHA-256 `cd79ecfc3819a94132881036be26e4cfbcbd6def4e02224a3388411ee446f4fd`.

This is a platform-specific mechanism falsifier showing that program-visible sanitization is not equivalent to erasure from the procfs initial-environment region. It is **not** detector validation and is not generalized to an unmeasured HIBEAM runtime without a receipt.

### E3 — deterministic software hostile matrix

Exact authoring-byte local execution:

`PYTHONPATH=/tmp/ccb_new python3 -m pytest -q /tmp/ccb_new/tests/test_geant4_loader_initial_environment_attestation.py`

Result: `10 passed in 0.54s`, no RNG. `python3 -m py_compile` on tool and tests also passed.

Hostile cases cover exact stable match, kernel-secure interpretation, absence semantics, runtime/proc value mismatch, duplicate tracked key, wrong parent receipt, process mismatch, malformed secure auxv record, mutation between the two procfs reads, and a real Linux post-exec `os.environ` change.

Exact repository-byte binding after the final local run:

- tool: 13024 bytes; SHA-256 `a1d3074fcf998c17abf5d99752f399d98aca491f184cad704224ea08111ab9b3`; Git blob SHA-1 `ab0f087fd2a138101bd269b97afc8b607ccb9036`;
- tests: 9730 bytes; SHA-256 `9a81c81ea51ac27e94d925635b9ba800d6acc1742f9409ca57e3c161f7e41203`; Git blob SHA-1 `f3c79dbf80a064a28885046dcbed08940f2f174f`.

The connected GitHub Contents API reports those exact blob SHA-1 values on `audit/geant4-loader-proc-env`. Local `ruff` was unavailable; repository CI must supply the lint gate.

## Four sequential AI review passes

### 1. Runtime / detector-simulation integration lead

Background: Geant4 production/runtime provenance, detector-simulation dependency graphs, Linux process-boundary evidence.

Evidence inspected: #1210 merged implementation and CI status; current `geant4/setup_and_run.sh`; runtime-dependency and secure-state attestors; Linux procfs and loader documentation; E1/E2/E3.

Strongest counter-hypothesis: the environment in the existing runtime receipt is merely a post-loader `getenv` view and therefore cannot contribute launch evidence.

Attempted falsifier: E1 changes the child environment after exec; E2 asks glibc secure handling to remove loader variables from the program-visible environment. In both cases procfs preserves the launch-region strings.

Residual uncertainty: target-controlled overwrite/remap before observation, exact HIBEAM/libc build, explicit loader argv/options, cwd/cache/token/hwcaps/preload/audit dependencies.

Vote: **REVISE the earlier “post-start environment” characterization / ACCEPT bounded procfs initial-region presence evidence**.

### 2. Adversarial Linux / loader mechanism reviewer

Background: Linux procfs, `execve`, `prctl(PR_SET_MM_*)`, ELF dynamic-loader search and sanitization semantics.

Evidence inspected: same as above, with emphasis on procfs mutation caveats and secure-loader alternate mechanisms.

Strongest counter-hypothesis: once procfs is documented as “initial environment,” its contents are an immutable historical copy of `execve(envp)`.

Attempted falsifier: authoritative procfs documentation explicitly permits relocating the environment region; direct memory overwrite is also possible. Therefore immutable historical absence/presence cannot be inferred from a late snapshot alone.

Residual uncertainty: whether a production HIBEAM process altered/remapped the region before observation; explicit `ld-linux` invocation and options; loader configuration state.

Vote: **ACCEPT stable observation contract / BLOCK immutable-execve or complete loader-decision claims**.

### 3. Independent statistics / validation reviewer

Background: deterministic software validation, fault injection, evidence-unit separation.

Evidence inspected: 10 deterministic tests, real Linux mutation fixture, glibc 2.41 secure-sanitization control, exact source/blob identities.

Strongest counter-hypothesis: passing synthetic/local controls authorizes the production generator environment.

Attempted falsifier: no production HIBEAM PID, immutable runtime receipt, event, seed, weight, or output participates. The experiment measures one Linux/glibc host only.

Residual uncertainty: exact production runtime and any platform/version-specific behavior.

Vote: **ACCEPT deterministic mechanism oracle / BLOCK HIBEAM generalisation and all physics inference**.

### 4. Claims / provenance reviewer

Background: source-to-claim mapping, claim-ledger governance, simulation/data evidence separation.

Evidence inspected: #1182 acceptance contract, CL-021 gate state, current claim matrix and study ledger.

Strongest counter-hypothesis: recovering launch-region evidence closes compiled-generator provenance or validates historical MC.

Attempted falsifier: linker/static inputs, loader argv/cwd/cache/tokens, immutable consumption, RNG/thread/event/input/output manifests, compiled hostile source/stopping controls, event weights, detector response and DATA/MC closure all remain independent gates.

Residual uncertainty: the complete downstream chain.

Vote: **ACCEPT provenance refinement / BLOCK CL-021 or detector-performance promotion**.

## Cross-scale propagation

This atom changes only the provenance chain:

procfs byte region -> tracked loader-environment candidate -> loader-search reconstruction -> runtime executable provenance -> generator provenance -> study/claim eligibility.

It does not create a transport observable, response observable, detector efficiency, PID quantity, calibration, event weight, uncertainty interval, or DATA/MC comparison. Local plausibility is not assumed to compose upward; the loader-search parent remains incomplete.

## Child atoms / dependency refinement

The former `ARU-MC-G4-LOADER-PREEXEC-ENV-001` is **refined, not declared complete**. A stable procfs presence now carries stronger launch-region evidence than the old handoff credited, but a pre-exec boundary remains necessary when the research question requires immutable execve absence/presence or proof that the target did not rewrite/remap its environment region.

Spawn/retain:

- `ARU-MC-G4-LOADER-ENV-REGION-MUTATION-001`: bind or eliminate post-exec overwrite/`PR_SET_MM_ENV_*` ambiguity, or move the evidence boundary to a controlled pre-exec receipt;
- `ARU-MC-G4-LOADER-ARGV-001`: exact executable/dynamic-loader invocation and loader command-line options;
- `ARU-MC-G4-LOADER-INITIAL-CWD-001`;
- `ARU-MC-G4-LOADER-CACHE-CONFIG-001`;
- `ARU-MC-G4-LOADER-TOKEN-HWCAPS-001`;
- `ARU-MC-G4-PRELOAD-AUDIT-001`;
- existing linker-command/static-input, late-`dlopen`, non-executable relocation/GOT/PLT, wrapper/descendant, immutable-consumption, runtime-manifest, compiled source/stopping, event-weight and detector-response children.

## Claim/wiki consequence

No public physics wording should be strengthened. #1182 and CL-021 stay gated. The only governance correction is internal provenance wording: `/proc/<pid>/environ` is not simply the post-start `getenv` view; it is a bounded Linux initial-environment-region observation with explicit mutation/remap caveats.

## Current repository action and merge gate

Branch: `audit/geant4-loader-proc-env`, based exactly on `main@d6dc5ab29fc0ae6ac9d921a50c08b4554d14902d`.

Implemented files:

- `tools/audit/geant4_loader_initial_environment_attestation.py`;
- `tests/test_geant4_loader_initial_environment_attestation.py`;
- curated MC Validation ruff-list integration;
- this immutable atomic record and coordination handoff updates.

Do not merge until a final exact-head MC Validation run has successful curated ruff, full non-integration pytest, diagnostics publication and enforcement, and until current protected-main ancestry is rechecked. A green run validates this software/provenance primitive only.

No production Geant4 campaign, beam ROOT input, production MC ROOT output, detector response, event-weight distribution, B2/B8 quantity, PID, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance result was produced or promoted in this atom.
