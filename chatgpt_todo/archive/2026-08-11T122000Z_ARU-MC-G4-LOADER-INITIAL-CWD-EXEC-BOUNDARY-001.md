# ARU-MC-G4-LOADER-INITIAL-CWD-EXEC-BOUNDARY-001

Status: `PARTIAL / IMPLEMENTED_ON_BRANCH / LOCAL_COMMITTED_BYTES_VALIDATED / EXACT_HEAD_CI_REQUIRED / FRONTDOOR_ADOPTION_BLOCKED / FS_NAMESPACE_BLOCKED / PHYSICS_INFERENCE_BLOCKED`

Parent issue: #1214. Broader provenance parent: #1182. Protected base selected for this atom: `main@859903ada4a856c998b2bc79298cd4a26c2cb447` (merge of #1215). Branch: `audit/geant4-exec-cwd-boundary`.

## Atom contract

The historical HIBEAM front door invokes `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root` after `cd "$SRC/build_conda"`. The three scientific/runtime path spellings are relative. For a relative path `p`, use the dependency decomposition

`Resolved_t(p) = Resolve(CWD_t, Root_t, MountNS_t, p)`.

This atom binds only the directory object `CWD_exec` at the direct final ELF exec transition. It does **not** claim that cwd alone proves the bytes later opened for config, macro or output.

For parent-selected cwd object `D_parent`, helper pre-exec cwd object `D_pre`, parent-selected target object `X_parent`, helper-opened target `X_pre`, and post-exec `/proc/<pid>/exe` object `X_post`, the accepting invariants are

`D_parent == D_pre` by `(st_dev, st_ino)`,

`X_parent == X_pre == X_post` by `(device_major, device_minor, inode)`,

and

`PID_pre == PID_post` and `starttime_pre == starttime_post`.

The pre-exec record additionally binds exact target argv bytes and a SHA-256 of the canonical out-of-band target-environment transfer. A close-on-exec control pipe must reach EOF after the pre-exec frame; an exec error frame fails closed.

## Mechanism universe and eliminations

- H1: later `/proc/<pid>/cwd` is sufficient historical exec-cwd evidence. **Eliminated** by the merged current-cwd atom's real post-exec `chdir` control and repeated controls here.
- H2: parent shell/process cwd is sufficient. **Eliminated** by a positive test in which the attested child cwd is a distinct directory object from the parent cwd.
- H3: a wrapper/script route is observationally equivalent to direct HIBEAM exec. **Eliminated for this schema**: non-ELF script targets fail closed. Wrapper/interpreter chains require their own explicit process/exec contract.
- H4: a direct helper can record cwd immediately before final fd-based `execve` and bind the same PID/starttime/executable afterward. **Survives** for the bounded direct-ELF route.
- H5: passing the target environment through helper startup is harmless. **Rejected as an unnecessary dependency** because preload/audit constructors or other startup effects could contaminate the helper. The implemented helper starts under its own environment with `LD_PRELOAD`/`LD_AUDIT` removed, while the exact target environment is transferred via an inherited anonymous file descriptor and applied only to final `execve`.
- H6: cwd closure proves relative input bytes. **Rejected**; root/mount namespace, symlink/path resolution, actual open/consumption and output creation remain child atoms.

Equivalent post-exec `chdir(path)` and `fchdir(fd)` mechanisms collapse at the parent scientific question because both can make current cwd differ from exec cwd; both are retained as distinct negative controls.

## Authoritative external facts mapped to the contract

- Linux `chdir(2)` / `fchdir(2)`: relative pathnames start from cwd; cwd is left unchanged by `execve`; `fchdir` changes cwd using an open directory descriptor. https://man7.org/linux/man-pages/man2/chdir.2.html
- Linux `/proc/pid/cwd`: the procfs link denotes the process's **current** working directory. https://man7.org/linux/man-pages/man5/proc_pid_cwd.5.html
- Linux `execve(2)`: successful exec replaces the program image of the existing process; it does not create a new PID. https://man7.org/linux/man-pages/man2/execve.2.html
- Python `subprocess`: on POSIX, `cwd` changes the child working directory before executing the child, and `pass_fds` is the explicit descriptor-inheritance mechanism. https://docs.python.org/3/library/subprocess.html

These are software/kernel semantics, not detector measurements.

## Implemented bounded mechanism

`tools/audit/geant4_exec_cwd_attestation.py` adds schema `ccb_geant4_exec_cwd_attestation_v1` plus a runtime-composition schema `ccb_geant4_exec_cwd_runtime_binding_v1`.

The parent opens the requested cwd and direct ELF target and records their object identities. It then starts an isolated `python -I -S` helper with that cwd and only the control/environment-transfer descriptors intentionally passed. The helper:

1. reads and validates the exact target environment from the out-of-band descriptor;
2. opens `.` and the requested direct ELF target;
3. records PID, `/proc/self/stat` starttime, cwd object, target object and exact target argv;
4. marks the control fd close-on-exec;
5. calls fd-based `os.execve(target_fd, argv, target_environment)` without a cwd-changing call after the record.

The parent requires control-pipe EOF, the same PID/starttime, and the same target inode through `/proc/<pid>/exe`. It then compares the helper cwd/target objects to the parent-selected objects. `bind_exec_cwd_to_runtime()` composes the receipt with a digest-valid `ccb_geant4_runtime_dependency_attestation_v1` receipt by exact `(pid,starttime_ticks,exe_link)` plus executable object identity.

The helper's own loaded-source consumption is deliberately listed as a limitation of this receipt. Repository content-transfer governance plus exact-head CI is the repository evidence for committed code; a production launcher-code consumption receipt would be a separate child if required for campaign authorization.

## Discriminating experiments executed

Environment: Python 3.13.5, Linux 6.18.35 x86_64, glibc 2.41, GCC-built interpreter 14.2.0. No RNG, weights, events or detector data.

Focused hostile matrix:

- direct `/bin/sleep` ELF with explicit cwd and exact argv;
- parent cwd distinct from target exec cwd;
- real Python target that calls post-exec `chdir(later)` and signals a state marker;
- real Python target that calls post-exec `fchdir(fd)` and signals a state marker;
- script/shebang wrapper rejection;
- non-absolute launch-path rejection;
- valid composition with a synthetic digest-valid runtime receipt;
- starttime mismatch rejection;
- executable-inode mismatch rejection;
- tampered exec-cwd receipt rejection;
- parent-selected versus helper target-object mismatch rejection;
- JSON round-trip receipt digest check.

After the target-environment contamination concern was repaired, the authoring-copy focused suite passed six consecutive times: `10 passed` in 1.09 s, 1.17 s, 1.15 s, 1.14 s, 1.22 s and 1.18 s. `py_compile` passed. Local `ruff` is unavailable, so no local ruff PASS is claimed.

Repository publication was then independently checked against the content-transfer contract. The GitHub blobs equal the locally validated source/test bytes except for the intentionally observed missing final LF introduced by the file-write surface. Exact committed-byte copies (with that final LF removed) were reconstructed locally and the focused suite passed three further consecutive times: `10 passed` in 1.25 s, 1.15 s and 1.17 s; `py_compile` also passed.

Exact committed identities:

- tool: 32,497 bytes, SHA-256 `b278d4def1e2ba4ed07e46f9964d6a8c499e16c0b854968263fed06e3614f42c`, Git blob `7b12c5db3e616f0bc2c314ced864ce042c86aab5`;
- tests: 11,876 bytes, SHA-256 `b0ef626cc20045d9f2a022a24827510b2c0639681317e7b7`, Git blob `2ee73530c96d489791ab540acaec5e6c1531713d`.

The final-LF difference has no Python semantic effect and was itself measured rather than ignored. Exact-head repository CI is still mandatory because curated ruff and the complete non-integration test suite have not yet run on the final PR head.

## Four sequential AI reviews

### A. Runtime / physics integration lead

Evidence inspected: merged argv/current-cwd receipts, #1214, `geant4/setup_and_run.sh`, direct-ELF tool, real `chdir`/`fchdir` controls, Linux exec/cwd documentation.

Strongest counter-hypothesis: the later stable current cwd from #1215 can be promoted to HIBEAM launch cwd.

Attempted falsifier: target changes cwd only after final exec; the new exec-boundary receipt remains the initial directory object while `/proc/<pid>/cwd` becomes the later object.

Residual uncertainty: the historical production shell does not yet invoke this new launcher; no real HIBEAM executable/process was available in this run; root/mount namespace and actual file consumption are independent.

Vote: **ACCEPT bounded direct-exec cwd mechanism / BLOCK production provenance until front-door adoption and real HIBEAM composition**.

### B. Adversarial Linux / filesystem reviewer

Evidence inspected: process/object invariants, wrapper rejection, parent-child cwd discrimination, target-environment transfer path, PID/starttime/executable composition.

Strongest counter-hypothesis: helper startup or a wrapper can silently alter state after the claimed record.

Attempted falsifier: scripts are rejected; target env is no longer used to start the helper; helper is isolated with `-I -S`; post-exec cwd mutators do not rewrite the receipt; wrong target/starttime fail closed.

Residual uncertainty: helper source consumption is not separately content-attested at runtime; alternate explicit dynamic-loader/wrapper routes are outside this direct-ELF schema; namespace/root state remains unbound.

Vote: **ACCEPT fail-closed direct-ELF mechanism / REJECT wrapper substitution / BLOCK namespace and alternate-launch claims**.

### C. Independent statistics / validation reviewer

Evidence inspected: exact hostile fixtures, six repeated authoring-byte passes, three repeated exact-committed-byte passes, `py_compile`, exact source/test hashes.

Strongest counter-hypothesis: local repeated tests are enough to authorize repository integration.

Attempted falsifier: exact committed bytes were separately reconstructed from the measured blob identities and rerun, but local ruff is unavailable and full repository pytest has not run on the final head.

Residual uncertainty: exact-head CI and Linux runner behavior under Python 3.11.

Vote: **ACCEPT deterministic local oracle / REVISE until exact-head curated ruff + full pytest + enforcement pass**.

### D. Claims / provenance reviewer

Evidence inspected: #1214 acceptance boundary, current claim-governance chain, setup script, scope/limitations emitted by the new receipt.

Strongest counter-hypothesis: closing exec cwd is enough to validate historical MC or CL-021.

Attempted falsifier: relative path resolution still depends on root/mount namespace and actual opens; runtime RNG/thread/event/input/output and detector-response atoms remain unresolved.

Residual uncertainty: all downstream provenance/physics children.

Vote: **ACCEPT provenance refinement / BLOCK CL-021 and all detector-performance promotion**.

## Stable concerns

- `CWD-EXEC-001` P0: current procfs cwd is not historical exec cwd. Bounded mechanism implemented; exact-head CI pending.
- `CWD-EXEC-002` P0: production `setup_and_run.sh` does not yet adopt the launcher. Required falsifier: run the real HIBEAM front door through the launcher and compose with runtime receipt. **OPEN**.
- `CWD-EXEC-003` P1: process root/mount namespace is not bound. Child `ARU-MC-G4-LOADER-FS-NAMESPACE-001`. **OPEN**.
- `CWD-EXEC-004` P0: exact relative config/macro bytes at open/consumption are not bound. Child `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`. **OPEN**.
- `CWD-EXEC-005` P1: output path creation/identity is not bound. Child `ARU-MC-G4-OUTPUT-PATH-CREATION-001`. **OPEN**.
- `CWD-EXEC-006` P1: runtime helper source consumption is not separately content-attested. Existing repository content-transfer evidence covers committed code but not an immutable production interpreter consumption trace. **OPEN if production authorization requires it**.

## Cross-scale propagation and claim consequences

Micro: directory object at direct exec is now measurable for the controlled launcher.

Meso/runtime: it composes with the existing runtime dependency receipt only when PID/starttime/exe-link/executable object agree.

Event/study: no event is generated by the validation; no Geant4 source, transport, weight, reconstruction or detector observable is inferred.

Claim: CL-021 remains gated. No README/wiki/public detector statement is promoted. This atom only removes one possible ambiguity in the future production provenance chain.

## Next highest-value child

First, consume exact-head CI for this branch and fix only demonstrated failures. If green, retain the PR as bounded implementation evidence but do not claim production closure until `CWD-EXEC-002` adopts the launcher in the real HIBEAM front door and composes a real runtime receipt. Scientifically, the next independent dependency after adoption is `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, followed by exact relative-input consumption and output creation.