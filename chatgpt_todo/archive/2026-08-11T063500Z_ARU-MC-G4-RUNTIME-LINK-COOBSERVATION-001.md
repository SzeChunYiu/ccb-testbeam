# ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001

Status: ACTIVE / IMPLEMENTED_ON_DRAFT_PR_1208 / EXACT_HEAD_CI_REQUIRED / REAL_HIBEAM_RUNTIME_BLOCKED / DETECTOR_INFERENCE_BLOCKED

## Parent and exact repository provenance

- Parent issue: #1182 (`ARU-MC-CS-WORKER-INIT-001` plus compiled/runtime-provenance descendants).
- Protected main selected for this atom: `a9b7184bce1b898a2b36143ed4bd7f725d5a0f8a`, the squash merge of validated PR #1207.
- #1207 exact pre-merge head: `2b699f89cdb4740bde9eb59d7fe19a74ca5567a7`.
- #1207 exact-head MC Validation run `31464431085`: curated ruff PASS and `1537 passed, 1 skipped, 8 xfailed, 1 xpassed`.
- Branch: `audit/geant4-runtime-link-coobservation`.
- Draft PR: #1208.
- Implementation commit: `1ebebdf3fa2a60642fdbeb84fd6e5c73abdd7ccd`.
- Hostile-test commit: `fc821619cf72972a81302609e8f8a560c8d48c52`.
- Curated-rufﬀ inclusion commit: `4f637fabe507c040ab5421f1fc63dcf191391abd`.

No HIBEAM executable, Geant4 event, beam ROOT byte, or production-MC ROOT byte was available to this session.

## Atom definition and scientific meaning

The selected atom tests one narrow provenance assumption introduced by the already-merged runtime/link validators: whether the content identity and ELF metadata attributed to a mapped executable object can be derived from the **same opened file description**, instead of trusting two independent pathname opens separated in time.

Inputs:

1. one validated `ccb_geant4_build_binding_final_v1` receipt;
2. one validated descendant `ccb_geant4_runtime_dependency_attestation_v1` receipt;
3. the still-live Linux process identified by `(pid,starttime_ticks)`;
4. its current `/proc/<pid>/maps` state and mapped object pathnames.

Outputs:

- `ccb_geant4_runtime_link_coobservation_v1` receipt;
- one content/ELF record per file-backed executable mapped object;
- direct `DT_NEEDED` -> runtime-object closure;
- `PT_INTERP` -> runtime-object closure;
- explicit unresolved loader/link/runtime limitations.

Units: byte counts and virtual/file offsets are bytes; hashes are SHA-256 digests; device/inode and PID/start-time are dimensionless OS identities. There is no detector measurand in this atom.

## Exact contracts and invariants

For runtime mapped object `j`, define its receipt identity

`K_j = (device_major_j, device_minor_j, inode_j)`.

For one path `p` that currently names this mapping and one opened descriptor `fd`:

`K_stat(p,t0) = K_fstat(fd,t0) = K_j = K_stat(p,t1)`.

The authoritative byte snapshot for this local atom is

`B_j = pread(fd, 0, L_j)`

under stable before/after `fstat`, and both

`H_j = SHA256(B_j)`

and

`E_j = parse_ELF(B_j)`

are derived from that same `B_j`. The snapshot must also satisfy the predecessor receipt `(L_j,H_j,K_j)`.

Process compatibility requires

`starttime(t0) = starttime_receipt = starttime(t1)`

and

`P_exec(t0) = P_exec(receipt) = P_exec(t1)`,

where `P_exec` is the complete file-backed executable mapping projection used by #1204/#1207.

For each unique non-path direct dependency name `d` in the process executable:

`#{j : SONAME(E_j) = d} = 1`.

For an absolute `DT_NEEDED` or `PT_INTERP` pathname `q`, the current resolved device/inode must match exactly one co-observed mapped object and remain stable over the observation. A slash-containing relative `DT_NEEDED` remains BLOCKED because process cwd provenance is not yet bound.

A byte string beginning with ELF magic is either parsed successfully under the bounded ELF64/little-endian/x86-64 contract or the atom fails closed. It is not silently relabelled non-ELF.

## Competing mechanisms and collapse

### H1 — independent later pathname reopen is equivalent to same-object observation

REJECT for this atom. A pathname can be replaced between observations. Even if a later file happens to have a plausible name, that does not prove the later parsed bytes were the mapped inode previously attested.

### H2 — same opened descriptor supplies identity, hash and ELF metadata

SURVIVES. Linux open-file-description semantics make an already-open descriptor refer to its opened object rather than retargeting because a pathname is later changed. Pre/post path resolution and full mapping/process stability checks detect observable namespace drift around the snapshot.

### H3 — `/proc/<pid>/map_files/<start>-<end>` must be opened and used as the only acceptable reference

STRONGER BUT BLOCKED/NOT REQUIRED for the current bounded claim. The predecessor session observed `EPERM` when trying to open this interface, and Linux documents access restrictions. This atom therefore does not pretend map-files-FD provenance exists.

### H4 — mapping basename/SONAME-family similarity is enough

REJECT. Non-path `DT_NEEDED` closure continues to require exact parsed `DT_SONAME` equality and unique mapped-object cardinality.

### H5 — malformed ELF-like content can be treated as an opaque non-ELF executable object

REJECT. If ELF magic is present, parse failure is a provenance failure, not evidence that the object is non-ELF.

Equivalent descriptions that differ only in whether the byte digest is computed before or after parsing collapse to H2 only when both operations consume the same immutable Python `bytes` snapshot returned from the same descriptor read.

## Authoritative external facts mapped to claims

- Linux `/proc/<pid>/maps` documents the address range, permissions, file offset, device, inode and pathname fields used to identify mapped file-backed objects: https://man7.org/linux/man-pages/man5/proc_pid_maps.5.html
- Linux `open(2)` documents that a successful `open()` creates an open file description and that the descriptor reference is unaffected if the pathname is later removed or changed: https://man7.org/linux/man-pages/man2/open.2.html
- Linux `/proc/<pid>/map_files` documents mapping-file entries and ptrace/capability access restrictions: https://man7.org/linux/man-pages/man5/proc_pid_map_files.5.html

These OS facts justify the software-provenance mechanism only. They say nothing about HIBEAM physics correctness.

## Discriminating experiments and negative controls

Committed hostile fixtures in `tests/test_geant4_runtime_link_coobservation.py` cover:

1. nominal versioned SONAME closure with a symlinked interpreter pathname resolving to the mapped loader inode;
2. absolute `DT_NEEDED` symlink resolution by stable device/inode identity;
3. relative slash-containing dependency blocked for absent cwd provenance;
4. duplicate runtime SONAME ambiguity;
5. malformed ELF-magic object fails closed rather than becoming non-ELF;
6. injected pathname replacement while the old mapped-object descriptor is already open, requiring post-resolution drift detection;
7. executable mapping projection mismatch;
8. runtime receipt attached to a different final-build receipt.

The local authoring container is Python 3.13.5, Linux 6.18.35 x86_64, Debian glibc 2.41. No RNG is used. `python -m py_compile` passed for the new tool and test module. A first attempt to run the focused pytest module from a deliberately partial `/mnt/data/coobs` tree failed during collection because the three imported predecessor audit modules had not been copied into that partial tree; this is an environment/fixture-assembly failure and is not represented as a test failure of the committed repository. `ruff` is not installed in the local container, so no local ruff PASS is claimed. Fresh exact-head GitHub MC Validation is the repository-level execution gate.

## Cross-atom compatibility

Micro: same-open-FD bytes `B_j` bind hash and ELF metadata for one mapped executable object.

Meso: unique `DT_NEEDED`/`PT_INTERP` closure composes the process executable with those object records.

Runtime: process start-time and the complete executable mapping projection must remain compatible with the predecessor receipt.

Build: the runtime receipt must descend from the exact final-build receipt; this atom does not infer the linker command or static inputs from the produced ELF.

Study/claim: no generator distribution, detector response or statistical estimator is touched. CL-021 remains gated even if this local receipt eventually validates on a real process.

Cross-atom incompatibilities explicitly preserved:

- #1207 executable-page equality does not bind non-executable relocated state;
- this atom does not prove the historical loader search choice that produced the mapping;
- a one-boundary mapping/ELF observation does not exclude later `dlopen`, unload or runtime patching;
- source readiness, source/support uncertainty, event weights, detector digitization and DATA/MC statistical compatibility remain separate universes.

## Four sequential AI review passes

### (a) Linux/Geant4 runtime-provenance lead — ACCEPT local decomposition / BLOCK HIBEAM authorisation

Evidence inspected: #1204 runtime receipt contract, merged #1206 ELF-link contract, merged #1207 executable-page contract, current #1182 parent, Linux proc/open semantics. Strongest counter-hypothesis: reopening a mapped pathname later is already equivalent because #1204 stores device/inode and SHA-256. Attempted falsifier: pathname replacement after descriptor open; the new contract detects changed path resolution while hash and ELF parse still remain tied to the old descriptor. Residual uncertainty: no immutable HIBEAM PID/runtime receipt was available; `/proc/<pid>/map_files` same-mapping handle remains capability-blocked. Vote: **ACCEPT bounded mechanism / BLOCK production authorisation**.

### (b) Adversarial systems/mechanism reviewer — REVISE path semantics / ACCEPT same-descriptor byte contract

Evidence inspected: path replacement, interpreter symlink, absolute/relative dependency semantics, duplicate SONAME, malformed ELF behavior. Strongest counter-hypothesis: requiring exact path spelling is safer. Falsifier: a legitimate symlinked `PT_INTERP` can resolve to the exact mapped loader inode even when `/proc/maps` records a different canonical spelling; path-string equality would overreject. Residual uncertainty: path resolution is rechecked but the historical loader decision and namespace/mount state at exec time are not bound. Vote: **ACCEPT inode-resolution contract / BLOCK historical-loader inference**.

### (c) Independent statistics/validation reviewer — ACCEPT deterministic oracle design / BLOCK validation until exact-head CI

Evidence inspected: eight deterministic hostile fixtures, py_compile result, local partial-tree collection failure, workflow inclusion. Strongest counter-hypothesis: syntax compilation plus reasoning is sufficient. Falsifier: full repository import and test compatibility is not exercised by the partial local tree; exact-head CI is required. Residual uncertainty: current branch has not yet completed exact-head pytest/ruff at the time of this record. Vote: **BLOCK merge pending exact-head CI; BLOCK physics inference regardless**.

### (d) Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion

Evidence inspected: `docs/validation/CL-021_scattering_model.md`, #1182 acceptance criteria, `MASTER_INDEX.md` runtime-provenance row and current claim gates. Strongest counter-hypothesis: source + mapped-code + ELF closure is enough to validate the source-model claim. Falsifier: linker/static inputs, loader decision state, runtime run-manager/thread/RNG/event/input/output identity, compiled hostile source/stopping controls, source UQ/support, event weights and detector response all remain open. Residual uncertainty is therefore material and cross-scale. Vote: **BLOCK CL-021 and detector claims**.

## Child atoms spawned or retained

- `ARU-MC-G4-LOADER-SEARCH-001`: cwd where relevant, secure-execution state, loader cache/config, token expansion, preload/audit and direct/transitive search semantics.
- `ARU-MC-G4-LINK-COMMAND-001`: actual linker invocation, response files, static archives, flags and immutable inputs.
- `ARU-MC-G4-LATE-DLOPEN-001`: event-interval executable mapping/load/unload stability.
- `ARU-MC-G4-NONEXEC-RELOCATION-001`: relevant non-executable relocation/GOT/PLT state.
- existing wrapper/descendant, immutable-consumption, runtime-manifest, source/stopping compiled-control, event-weight and detector-response children remain material.

## Acceptance / rejection

ACCEPT this bounded atom only when the exact final PR head passes curated ruff and the full non-integration pytest suite, the PR base remains current/compatible protected main, and no unresolved review concern contradicts the stated scope. Even then the result is a software-provenance primitive only.

REJECT/BLOCK if any object hash and ELF metadata can refer to different opened objects, if mapped/process projection drifts unnoticed, if ambiguous SONAME matches are accepted, if relative dependency paths are interpreted without cwd provenance, or if malformed ELF-like content is silently downgraded.

## Claim/wiki consequences

No public detector or source-performance claim is promoted. `CL-021`, #1182, #1178, #1179, #1058 and #1053/#880 remain gated. No B2/B8, PID, penetration, timing, calibration, pile-up, event-weight, ESS, p-value, rate or detector-performance result is regenerated by this atom.
