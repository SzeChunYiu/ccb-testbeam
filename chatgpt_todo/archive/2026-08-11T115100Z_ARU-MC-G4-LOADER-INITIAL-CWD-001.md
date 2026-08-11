# ARU-MC-G4-LOADER-INITIAL-CWD-001 — current cwd observation versus historical exec-time cwd

Status: **PARTIAL / CURRENT_CWD_ATTESTOR_IMPLEMENTED / INITIAL_EXEC_CWD_BLOCKED / PHYSICS_INFERENCE_BLOCKED**

Parent: `ARU-MC-G4-LOADER-SEARCH-001`, with merged argv predecessor #1213 and broader generator-provenance parentage under #1182 / CL-021.

Repository base selected for this atom: protected `main@c485d96583df91e90669e402670a3fa102643495`, the squash merge of #1213 after both exact-head `test` checks on `85894ad0123ee56dc18da6cc86e0340f9eabb312` completed successfully.

## 1. Exact contract, observables, provenance, and scientific meaning

Repository front door `geant4/setup_and_run.sh` ends with:

```text
./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root
```

The config, macro, and output spellings are relative. For a relative pathname `p`, the lookup state is not merely the bytes of `p`; at time `t` it depends on the process filesystem state. A useful abstraction is

`Resolved_t(p) = Resolve(CWD_t, Root_t, MountNS_t, p)`.

This atom measures only `CWD_t` at one bounded observation window. It does **not** yet bind `Root_t`, mount namespace, symlink target chain, the historical cwd at `execve`, or the bytes actually consumed by HIBEAM.

Inputs to the implemented primitive:

- PASS, digest-valid `ccb_geant4_runtime_dependency_attestation_v1`;
- PASS, digest-valid `ccb_geant4_loader_argv_attestation_v1` descending from that exact runtime receipt;
- Linux procfs for the same PID.

State variables and observables:

- process identity `(pid, starttime_ticks, exe_link)`;
- `/proc/<pid>/cwd` symlink text;
- two independently opened cwd directory-object observations represented by `st_dev`, `st_ino`, and `st_mode`;
- parent receipt SHA-256 values and self-digest.

No physical unit is involved. `starttime_ticks` is a kernel clock-tick counter used only as PID-reuse identity state, not a calibrated time observable.

The bounded acceptance invariant is:

`RuntimeIdentity == ArgvIdentity == LiveIdentity`

and

`readlink(cwd)_1 == readlink(cwd)_2`

and

`fstat(open(cwd))_1 == fstat(open(cwd))_2`.

The receipt meaning is deliberately limited to `STABLE_CURRENT_WORKING_DIRECTORY_OBJECT_OBSERVATION_ONLY`.

## 2. Competing microscopic mechanisms

H1 — **No post-exec cwd mutation.** The process inherits the launch cwd and retains it; a later procfs observation may equal the initial exec-time cwd.

H2 — **Post-exec `chdir(path)`.** The target changes cwd after `execve`; a later procfs observation is real current state but not initial state.

H3 — **Post-exec `fchdir(fd)`.** Same scientific consequence as H2 but without a pathname argument.

H4 — **Lexical aliasing.** Different shell/PWD or symlink spellings may reach the same directory object. For relative file lookup, these aliases are not independent hypotheses once the same directory object is reached.

H5 — **Directory rename/unlink or metadata change.** The process can retain a directory object while the pathname exposed through procfs or its metadata changes. This is nuisance state, not proof of a new physical mechanism.

H6 — **Different root or mount namespace.** The same relative spelling can encounter a different filesystem graph even if cwd text looks similar. This remains a child atom.

## 3. Authoritative external facts and source-to-claim map

Linux man-pages are used as the authoritative OS interface documentation:

- `proc_pid_cwd(5)`: `/proc/pid/cwd` is a symbolic link to the **current** working directory of the process: https://man7.org/linux/man-pages/man5/proc_pid_cwd.5.html
- `chdir(2)`: `chdir`/`fchdir` change the current working directory; cwd is the starting point for relative pathnames; a child inherits cwd and `execve` leaves it unchanged: https://man7.org/linux/man-pages/man2/chdir.2.html
- `path_resolution(7)`: relative path resolution starts at current cwd, while root and mount namespace also participate in pathname resolution: https://man7.org/linux/man-pages/man7/path_resolution.7.html

Source mapping:

- claim “procfs cwd is current, not intrinsically historical” → `proc_pid_cwd(5)`;
- claim “execve itself preserves cwd, but target code may later change cwd” → `chdir(2)`;
- claim “cwd alone is insufficient for a complete relative-path proof when root/mount namespace/symlinks matter” → `path_resolution(7)`.

## 4. Equivalent descriptions collapsed

- `chdir` and `fchdir` are distinct implementation mechanisms but observationally equivalent for this parent question once the later cwd object differs from launch state; they are not counted as independent support for an initial-cwd hypothesis.
- symlink/PWD lexical aliases that reach the same directory object collapse to one directory-object state for relative lookup.
- all mechanisms that produce the same current `(st_dev, st_ino, st_mode)` and link observation are locally indistinguishable to this attestor; the receipt does not infer which microscopic route produced the state.

## 5. Eliminated and surviving hypotheses

Eliminated for provenance authorization:

- **Current `/proc/<pid>/cwd` equals immutable historical launch/exec cwd.** Directly falsified by a real child process launched with `cwd=initial` that executes Python, calls `chdir(later)`, and is later observed by procfs in `later`.
- **A single cwd pathname string is enough.** Rejected because directory-object identity and filesystem namespace/root state are separate observables.
- **A fixed sleep makes a historical cwd inference safe.** Rejected: elapsed time does not establish whether or when `chdir` occurred.

Surviving:

- stable current-cwd observation as a bounded runtime provenance primitive;
- initial exec-time cwd as an unresolved historical state requiring an exec-boundary mechanism or equivalent proof;
- exact relative input-byte consumption as an unresolved child requiring file-opening/consumption provenance, not cwd alone.

## 6. Nuisance/dependency variables

- PID reuse and process starttime;
- `/proc/<pid>/exe` stability;
- cwd link rename/unlink behavior;
- cwd directory device/inode/mode state;
- process root directory;
- mount namespace and bind mounts;
- symlink chains and absolute symlink targets;
- post-exec `chdir`/`fchdir` timing;
- actual HIBEAM file-open timing and whether config/macro paths are canonicalized internally;
- output creation timing and replacement semantics.

## 7. Discriminating tests and negative controls

Implemented hostile matrix in `tests/test_geant4_loader_cwd_attestation.py`:

1. nominal fake-proc current cwd with exact directory identity;
2. tampered runtime receipt digest;
3. argv receipt descending from another runtime receipt;
4. process starttime mismatch;
5. executable-link mismatch;
6. cwd-link mutation between observations;
7. cwd-directory-object mutation between opens;
8. real Linux post-exec `chdir` child proving current cwd is not initial cwd;
9. CLI fail-closed behavior on wrong argv parent.

The live child is a mechanism falsifier only. It is not HIBEAM, Geant4, detector MC, or beam data.

## 8. Executed evidence and reproducibility

Local execution environment:

- Python `3.13.5`;
- Linux `6.18.35 x86_64`;
- RNG: none.

Commands executed on the exact authoring copies:

```text
python -m pytest -q tests/test_geant4_loader_cwd_attestation.py
python -m py_compile tools/audit/geant4_loader_cwd_attestation.py tests/test_geant4_loader_cwd_attestation.py
```

Result:

```text
9 passed in 1.19 s
py_compile: PASS
```

A later identical focused run after the `O_PATH` refinement returned `9 passed in 1.17 s`; the final post-line-wrap run returned `9 passed in 1.17 s` and `py_compile` PASS.

Local `ruff` was not available. An attempted `pip install ruff` failed because the execution container could not resolve the package index; therefore **no local ruff PASS is claimed** and repository CI remains required.

Exact final authoring identities before publication:

- `tools/audit/geant4_loader_cwd_attestation.py`: 10,190 bytes; SHA-256 `02ed0bb6cd4f53a7e72e59f0147e06eee72e7a7518c0d8de11aa62b856f5e1be`; expected/observed Git blob SHA-1 `bb71a692732c3f6730b52704bd51ec9506cff7ac`.
- `tests/test_geant4_loader_cwd_attestation.py`: 10,285 bytes; SHA-256 `5d77e26e8233d8693af19d93bbf4bff4b6fbe45a68f8f91d19e95ec6862ffa28`; expected/observed Git blob SHA-1 `c1f9ffb43856aa17435e931194a94a1df68486c2`.

Repository commits so far on branch `audit/geant4-loader-cwd`:

- `475d0f886b0257b1cfd905e798254a07ec8a8dd8` — cwd attestor;
- `c0131e9cc7740303505554266b207fa42567bf70` — hostile tests;
- `7acb18fa686a2456093c61087491c2a7ec2a114d` — curated ruff/CI inclusion.

No production Geant4 event count, seed, event weight, detector response, or beam sample exists for this atom.

## 9. Micro → meso → event → study → claim propagation

Micro: live process cwd state can now be observed with parent runtime/argv identity checks.

Meso: this can constrain the runtime path-resolution state for relative HIBEAM arguments at the observation boundary, but only after root/mount namespace compatibility is also established.

Event: no event-level input consumption is proven because the process may change cwd before opening a config/macro or may internally resolve/canonicalize paths differently.

Study: no historical production run is rehabilitated by a current-cwd receipt alone.

Claim: CL-021 remains gated. No detector-performance, source-distribution, PID, timing, energy, pile-up, rate, or DATA/MC statement changes status.

## 10. Child atoms spawned

- `ARU-MC-G4-LOADER-INITIAL-CWD-EXEC-BOUNDARY-001` — capture/prove cwd at the `execve` boundary rather than later current state.
- `ARU-MC-G4-LOADER-FS-NAMESPACE-001` — bind process root, mount namespace, and relevant mount topology for pathname resolution.
- `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001` — bind the exact config/macro/support bytes actually opened/consumed by HIBEAM.
- `ARU-MC-G4-OUTPUT-PATH-CREATION-001` — bind cwd/path state at output creation and final output identity.

Parent completion is blocked while the historical initial-cwd and exact input-consumption children remain unresolved.

## Four sequential AI review passes

### (a) Runtime/physics integration lead — **ACCEPT current-state primitive / REVISE initial-cwd claim**

Evidence inspected: merged argv contract, `geant4/setup_and_run.sh`, Linux cwd/path-resolution documentation, nine focused tests. Strongest counter-hypothesis: exec preserves cwd, so a later procfs cwd is effectively initial cwd. Attempted falsifier: real child launched in `initial` and then `chdir(later)`. Result: procfs and the attestor correctly observe `later`. Residual uncertainty: real HIBEAM code may or may not call `chdir`; exact historical launch cwd is absent. Vote: **ACCEPT bounded current-cwd observation; BLOCK initial-cwd provenance**.

### (b) Adversarial Linux/filesystem reviewer — **ACCEPT fail-closed transition checks / BLOCK complete path resolution**

Evidence inspected: cwd link, opened directory dev/inode/mode state, process identity rechecks, root/mount namespace semantics. Strongest counter-hypothesis: stable cwd object is sufficient to identify every relative input. Falsifier: pathname resolution can still depend on root/mount namespace and symlink targets. Residual uncertainty: ABA cwd changes and namespace state. Vote: **ACCEPT local discriminator; BLOCK complete relative-path authorization**.

### (c) Independent statistics/validation reviewer — **ACCEPT deterministic oracle / BLOCK physics inference**

Evidence inspected: nine deterministic tests, exact source/blob identity, no RNG, no Geant4 sample. Strongest counter-hypothesis: passing procfs fixtures validates the generator. Falsifier: the tests contain no event source, transport, detector response, weights, or study estimator. Residual uncertainty: repository ruff/full pytest and real HIBEAM runtime. Vote: **ACCEPT software/provenance tests; BLOCK detector or MC inference**.

### (d) Claims/provenance reviewer — **ACCEPT provenance refinement / BLOCK CL-021 promotion**

Evidence inspected: front-door relative paths, parent receipt boundaries, exact authoring/committed blob identities. Strongest counter-hypothesis: cwd plus argv closes historical run provenance. Falsifier: initial exec cwd, filesystem namespace, consumed input bytes, runtime manifest, seeds/threading, and output identity remain unbound. Residual uncertainty is material. Vote: **BLOCK claim promotion**.

## Claim/wiki consequence

No public wiki or claim-ledger physics statement is promoted. The only allowed documentation refinement is that Linux current-cwd provenance now has a tested bounded primitive, while historical initial cwd and relative input consumption remain explicitly blocked.
