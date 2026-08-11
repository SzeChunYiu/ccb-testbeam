# ARU-MC-G4-RUNTIME-MAPS-001 — live executable mapping identity

Status: `PARTIAL / IMPLEMENTED_ON_PR / LOCAL_FALSIFIERS_PASS / EXACT_HEAD_CI_PENDING / REAL_HIBEAM_RUNTIME_NOT_AVAILABLE`

Parent: #1182 (`ARU-MC-CS-WORKER-INIT-001`), with validated provenance predecessors #1198/#1199/#1201/#1202. This atom does not close #1182, #1178, #1179, #1058, #1053/#880, or CL-021.

## Expert group and sequential review roles

1. **Build/runtime physics lead** — Linux/ELF and Geant4 deployment provenance; owns the exact executable/runtime-object contract and separation of configured package labels from actually mapped code.
2. **Adversarial systems reviewer** — process identity, pathname/inode races, in-place mutation, deleted/replaced mappings, anonymous executable memory, loader environment, and same-soname mechanisms.
3. **Independent validation/statistics reviewer** — deterministic oracle design, equivalence-class collapse, negative controls, and the boundary between provenance closure and scientific inference.
4. **Claims/provenance reviewer** — source-to-claim traceability, evidence class, downstream CL-021 consequences, and explicit non-promotion of simulation/detector results.

These are AI review roles, not independent human collaborators.

## Exact atom contract

### Inputs

- one validated `ccb_geant4_build_binding_final_v1` receipt;
- one positive live Linux PID;
- one or more discriminating required-object patterns, e.g. a future HIBEAM run may require explicit Geant4/VGM/ROOT families once their exact mapped names are observed;
- Linux `/proc/<pid>/{stat,exe,maps,environ}` at one observation boundary.

### Outputs

A self-digested `ccb_geant4_runtime_dependency_attestation_v1` receipt containing:

- parent final-build receipt digest;
- PID and `/proc/<pid>/stat` start-time ticks;
- exact bytes/hash/device/inode/mode of the process executable opened through `/proc/<pid>/exe`;
- all regular file-backed objects with at least one executable mapping, collapsed by `(device-major, device-minor, inode)` and retaining every observed path and executable segment;
- exact SHA-256 and byte count of each collapsed mapped object;
- required-pattern → mapped-object index matches;
- selected initial dynamic-loader environment variables, stored as exact base64/byte-count/SHA-256 and UTF-8 only when valid;
- SHA-256 of the initial maps text and a pre/post executable-mapping projection stability gate.

### State variables and scientific meaning

For process `P`, let `E(P)` be the open executable object and let `M_x(P,t)` be the set of executable mappings at time `t`. A file-backed executable mapping is represented by

`m = (start,end,perms,offset,dev_major,dev_minor,inode,path)`.

Mappings with the same `(dev_major,dev_minor,inode)` are one backing-file identity even if represented by multiple VM segments or hardlink-equivalent path spellings. The receipt collapses those observationally equivalent parameterizations before assigning a SHA-256.

The required bounded invariant is

`H(E(P)) == H(E_parent)` and `|E(P)| == |E_parent|`,

with the live executable path also equal to the parent build path because relocation can alter `$ORIGIN`-dependent loader semantics, plus

`M_x(P,t_pre) == M_x(P,t_post)`

for the executable-mapping projection during collection. For every regular file-backed executable object `j`, the pathname opened during attestation must satisfy

`major(st_dev_j) == major_j`, `minor(st_dev_j) == minor_j`, `st_ino_j == inode_j`,

and the opened object must remain stable while hashed. The post-hash path recheck additionally requires the observed device, inode, size, `mtime_ns`, and `ctime_ns` to remain equal to the hashed file-description record. This closes the local same-inode/same-size post-hash mutation mechanism found during adversarial review.

There are no physical units in this atom. The measurand is software/runtime identity, not an energy, cross section, efficiency, angle, or detector response.

## Authoritative external mechanism evidence

Linux `proc_pid_maps(5)` defines `/proc/<pid>/maps` as the process's current mapped memory regions with address, permissions, offset, device, inode, and pathname; it also documents the ambiguous `" (deleted)"` pathname suffix. Linux kernel/man-pages documentation also exposes `/proc/<pid>/map_files`, but opening those mapped-file links requires elevated capabilities on modern Linux. Therefore this implementation does **not** pretend that `map_files` is universally available; it validates the maps-reported device/inode against a stable opened pathname and fails closed when the mapped file has been deleted/replaced or cannot be hashed.

The glibc dynamic-loader documentation states that dependency resolution can depend on `DT_RPATH`, `LD_LIBRARY_PATH`, `DT_RUNPATH`, the loader cache, and default directories, with additional controls such as `LD_PRELOAD`. This atom records selected loader-environment state and actual mapped code objects; it deliberately leaves `DT_NEEDED/RPATH/RUNPATH`, linker command identity, cache resolution, and late `dlopen` to separate child atoms.

Primary/authoritative references:

- https://man7.org/linux/man-pages/man5/proc_pid_maps.5.html
- https://www.kernel.org/doc/html/latest/filesystems/proc.html
- https://man7.org/linux/man-pages/man5/proc_pid_map_files.5.html
- https://man7.org/linux/man-pages/man8/ld.so.8.html

## Competing mechanisms and collapse/elimination

### H1 — configured package roots/version strings identify runtime libraries

Rejected. #1201/#1202 bind configured tools and their probe entrypoints, but a runtime loader can resolve different shared objects through environment, RPATH/RUNPATH, cache/default directories, or later loading.

### H2 — `ldd`/loader simulation is equivalent to actual mapped-object identity

Rejected as the primary runtime observable. A resolver prediction is not the same object as the process's actual current mappings. Link/resolution metadata remains useful as a separate cross-check child.

### H3 — pathname/soname alone identifies the mapped code

Rejected. A same-name path can be atomically replaced after a process maps an older inode. The synthetic falsifier preserves the pathname while replacing the file and is rejected because maps device/inode no longer match the current pathname target.

### H4 — path + version string is enough

Rejected. Version labels are declarations and can remain unchanged when bytes differ. Exact content hash is required.

### H5 — hash the current pathname without using maps device/inode

Rejected. That can hash a replacement object that is not the one represented by the process mapping.

### H6 — device/inode/size after hashing is sufficient against in-place mutation

Rejected by adversarial review. An in-place write can retain pathname, inode, and size while changing bytes. The hardened contract includes open-file `mtime_ns`/`ctime_ns` and requires final path metadata to retain those values; an injected same-size `library-A` → `library-B` transition now fails closed.

### H7 — every `/proc/<pid>/maps` row is an independent dependency

Collapsed. Multiple executable VM segments backed by the same `(device,inode)` are one backing-file universe; segment metadata are retained but the backing object is hashed once.

### H8 — kernel synthetic mappings and arbitrary anonymous executable mappings are equivalent

Rejected. `[vdso]`/`[vsyscall]` are explicitly recognized kernel pseudo-mappings. Any other anonymous executable mapping is unresolved executable code and blocks this attestation by default.

### H9 — stable actual file-backed executable mapping set + exact hashes + executable identity is a valid bounded runtime provenance primitive

Survives locally. It does **not** establish in-memory page bytes, link-time command identity, wrapper descendants, later `dlopen`, runtime RNG/thread/event state, or physics correctness.

## Executed experiments and falsifiers

Local deterministic reconstruction used the new module and focused tests under the available Python runtime. No RNG was used. Command:

`python -m pytest -q tests/test_geant4_runtime_dependency_attestation.py`

Result after adversarial hardening: `9 passed in 0.07s`.

The fixture matrix covers:

1. nominal executable + Geant4-like + ROOT-like mapped files with exact loader-environment capture;
2. live process executable bytes differing from the final-build receipt → reject;
3. required runtime-object family absent → reject;
4. same pathname/soname atomically replaced after the maps snapshot → device/inode mismatch → reject;
5. same inode and same size modified after its opened bytes are hashed → post-hash metadata mismatch → reject;
6. executable mapped object carrying the procfs ` (deleted)` suffix → reject rather than guess;
7. unattributed anonymous executable mapping → reject;
8. changed `LD_LIBRARY_PATH` with unchanged mappings → receipt identity changes because loader provenance changed;
9. real Linux `/proc` round trip against a sleeping Python child process → PASS, binding the child executable and live executable mappings.

The first eight-test implementation was not frozen as final: the adversarial reviewer found mechanism 5, code was revised, and the ninth negative control was added. This focused result is a software/provenance test only. Fresh exact-head repository CI is still required for the final hardened branch.

## Micro → meso → event → study → claim propagation

- **micro:** exact process executable object, executable mapping rows, device/inode/path, backing-object bytes/metadata, loader-control environment;
- **meso:** one content-bound runtime dependency receipt for the process at a stable observation boundary;
- **event:** not yet bound — no proof that a particular Geant4 event was generated while this mapping set held;
- **study:** not yet bound — no production campaign manifest links event population/output bytes to this receipt;
- **claim:** CL-021 and all detector/Data↔MC claims remain gated.

Cross-atom compatibility requirement: a future authorising run must compose #1199 executable identity, #1201/#1202 configured tool identity, this live mapping receipt, immutable input consumption, link metadata, run-manager/thread/RNG/event state, hostile compiled source/stopping controls, output ROOT identity/schema, event-weight contract, and the downstream detector-response chain. Individually plausible receipts must not be assumed to compose.

## Child atoms spawned

- `ARU-MC-G4-LINK-METADATA-001`: bind `DT_NEEDED`, `DT_RPATH`, `DT_RUNPATH`, loader/interpreter identity, linker/build-system evidence, and compare predicted direct dependencies with observed runtime mappings.
- `ARU-MC-G4-MAPPED-PAGE-CONTENT-001`: decide whether backing-file identity is sufficient or whether an authorising threat model requires in-memory executable page hashing; current receipt explicitly does not make that stronger claim.
- `ARU-MC-G4-LATE-DLOPEN-001`: bracket the event-generation interval with mapping receipts or another mechanism so libraries loaded/unloaded after the current snapshot cannot escape provenance.
- `ARU-MC-G4-WRAPPER-CHAIN-001`: bind wrapper/launcher/descendant process identities.
- Existing children remain `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001` and `ARU-MC-G4-RUNTIME-MANIFEST-001`.

## Four sequential review passes

### (a) Build/runtime physics lead — **ACCEPT bounded runtime-file identity / REVISE run provenance**

Evidence inspected: #1199/#1201/#1202 contracts, `geant4/setup_and_run.sh`, Linux procfs/loader documentation, new implementation and fixtures. Strongest counter-hypothesis: configured Geant4/VGM/ROOT roots already determine what ran. Attempted falsifier: environment-dependent resolution plus same-path replacement mechanism. Result: configured roots are insufficient. Residual uncertainty: no real HIBEAM PID/build receipt was available. Vote: **ACCEPT local atom; REVISE parent**.

### (b) Adversarial systems reviewer — **REVISE first implementation; ACCEPT hardened bounded mechanism / BLOCK stronger byte-execution claim**

Evidence inspected: device/inode semantics, deleted-path ambiguity, anonymous executable mappings, pre/post mapping projection, atomic replacement and same-inode/same-size in-place mutation controls. Strongest counter-hypothesis: hashing the current pathname and rechecking only device/inode/size is enough. Attempted falsifier: mutate the already-hashed mapped pathname in place without changing inode or size. Result: first implementation had a gap; hardened metadata recheck rejects it. Residual uncertainty: backing-file bytes are not a hash of already-faulted in-memory pages; late `dlopen` can occur after the snapshot; timestamp metadata are an observation guard, not a cryptographic memory-page proof. Vote: **ACCEPT hardened bounded mechanism / BLOCK in-memory-or-interval claim**.

### (c) Independent validation/statistics reviewer — **ACCEPT deterministic oracle / BLOCK physics inference**

Evidence inspected: nine deterministic fixtures, including one real `/proc` child-process round trip. Strongest counter-hypothesis: synthetic proc fixtures merely test the parser, not Linux behavior. Attempted falsifier: live Python process. Result: real procfs path parses and binds successfully. Residual uncertainty: no Geant4 executable or event population exercised. Vote: **ACCEPT software validation / BLOCK simulation inference**.

### (d) Claims/provenance reviewer — **ACCEPT provenance refinement / BLOCK CL-021 promotion**

Evidence inspected: #1182 acceptance requirements, setup script loader environment, previous claim demotion, current source/runtime dependency chain. Strongest counter-hypothesis: exact runtime library hashes complete generator validation. Attempted falsifier: enumerate missing event-level and detector-response dependencies. Result: source/run-manager/RNG/event count/input/output/weights/response/held-out validation remain open. Vote: **BLOCK claim promotion**.

## Claim/wiki consequences

No public detector or generator-performance statement becomes `VALIDATED`. CL-021 remains gated. Historical run descriptions that identify Geant4/ROOT/VGM only by nominal versions or mutable installation paths remain nonauthorising unless an exact runtime mapping receipt or equivalent immutable evidence is recovered.

## Handoff

If the hardened branch receives fresh exact-head CI and current-base ancestry remains valid, merge only this bounded runtime mapping primitive. Then move to `ARU-MC-G4-LINK-METADATA-001`: bind the ELF interpreter and dynamic section (`DT_NEEDED`, RPATH/RUNPATH) from exact executable bytes with a content-bound parser/tool identity, compare those declared direct dependencies against the actual runtime object receipt, and explicitly model loader search order/cache/environment. Do not run production physics or promote CL-021 until the full #1182 dependency chain passes.
