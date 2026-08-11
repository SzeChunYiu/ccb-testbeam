# ARU-MC-G4-MAPPED-PAGE-CONTENT-001 — live executable bytes versus attested file backing

Status: `ACTIVE / IMPLEMENTED_ON_BRANCH / LOCAL_FIXTURES_PASS_9 / REAL_CHILD_PROCESS_SMOKE_PASS / EXACT_HEAD_CI_PENDING / REAL_HIBEAM_RUNTIME_BLOCKED / PHYSICS_INFERENCE_BLOCKED`

Parent: #1182. Validated predecessors: #1204 runtime file-backing receipt and #1206 ELF link-declaration closure. Protected main at selection: `081ee04b7236d538e5f0a17bca49e4c01ee7f631`.

## Atom contract and scientific meaning

Input is one validated `ccb_geant4_runtime_dependency_attestation_v1` receipt plus the same still-live Linux process. The predecessor proves the bytes of files backing executable mappings, but explicitly does not prove that the executable virtual-address bytes equal those backing bytes. This atom measures that missing equality.

For every file-backed executable mapping segment `s` with virtual interval `[a_s,b_s)`, file offset `o_s`, attested backing size `L`, process-memory bytes `M_s`, and current bytes `F[o_s:o_s+n_s]` of the same attested dev/inode object,

`n_s = min(b_s-a_s, L-o_s)`

and the acceptance invariant is

`M_s = F[o_s:o_s+n_s] || 0^(b_s-a_s-n_s)`.

The zero suffix implements the Linux `mmap(2)` partial-final-page rule only when the mapping reaches the backing-file EOF. Mapping offsets at or beyond EOF are blocked. The process start-time and complete file-backed executable mapping projection must match the predecessor receipt before comparison and remain unchanged afterward. The backing file is fully SHA-256 revalidated against the predecessor receipt before segment comparison and rehashed after comparison.

Units: virtual/file addresses and byte counts are bytes. Observable/measurand: exact executable-memory byte equality, not a Geant4 physics observable.

## Competing mechanisms

- H1: mapped executable bytes equal the attested file backing. Survives and is the nominal provenance hypothesis.
- H2: private text relocation, runtime patching/instrumentation, self-modifying code, debugger/injector mutation, or another mechanism changes executable bytes after mapping. Distinct microscopic mechanisms collapse observationally here to the same local state `M_s != backing projection`; this atom detects but does not identify the mechanism.
- H3: path replacement causes a later pathname to name different bytes while the process still maps the old inode. Eliminated by requiring the current opened path to match predecessor dev/inode plus full byte hash before memory comparison.
- H4: PID reuse or a changed mapping set is mistaken for the predecessor process. Eliminated by exact start-time plus complete executable mapping projection closure.
- H5: partial final mapping page differs only because file bytes do not fill the last page. Linux documents zero-fill for the remainder of that page; a zero tail survives, a nonzero tail is a real mismatch under this contract.

## Authoritative external facts

Linux man-pages 6.18 `proc_pid_mem(5)` states that `/proc/<pid>/mem` exposes process memory through open/read/lseek and is governed by `PTRACE_MODE_ATTACH_FSCREDS` access. Linux `mmap(2)` documents page-sized file mappings and zero filling of the partial page beyond EOF. Linux `/proc/<pid>/maps` documents current mapped regions, permissions, offsets, device/inode and pathname. Source pages:

- https://man7.org/linux/man-pages/man5/proc_pid_mem.5.html
- https://man7.org/linux/man-pages/man2/mmap.2.html
- https://man7.org/linux/man-pages/man5/proc_pid_maps.5.html

A stronger same-mapped-object route via `/proc/<pid>/map_files/<start>-<end>` was tested locally. The links were enumerable/readlink-able for the current process but `open()` returned `EPERM`. Linux `proc_pid_map_files(5)` documents the capability restrictions. Therefore map-files-FD co-observation is a dependency blocker in this environment rather than a silently assumed capability.

## Implemented experiment

Branch: `audit/geant4-runtime-codepage-content`.

- `2fbf54d9a74dc87e1ba005a6404f0f2946d80856` — add `tools/audit/geant4_runtime_codepage_attestation.py`.
- `ed0fdc1b139f39cf0f141f20022577a99bbfbfeb` — add hostile deterministic fixtures.
- `87c17be896d66b81c0b227322b10c51d6ac3697f` — add tool/tests to curated MC Validation ruff surface.

Local deterministic fixture command, Python 3.13/Linux/no RNG:

`PYTHONPATH=/mnt/data python -m pytest -q /mnt/data/test_geant4_runtime_codepage_attestation.py`

Result: `9 passed in 0.06 s`.

Hostile controls: exact nominal equality; Linux partial-final-page zero fill; injected live-memory byte mutation; injected nonzero EOF-tail byte; backing-file mutation after predecessor receipt; process start-time mismatch; mapping projection mismatch; predecessor receipt digest tamper; duplicate runtime inode object.

A real Linux child-process smoke was also executed against `/bin/sleep`: a content-bound runtime-style receipt was constructed from the child process, then `/proc/<child>/mem` executable segments were compared with their exact backing files. Result: `PASS`, 7 mapped executable objects / 7 executable segments. This is an OS/provenance smoke only, not a HIBEAM or Geant4 run.

## Cross-atom propagation

If this atom passes on a real HIBEAM process, the chain becomes: final-build executable bytes -> runtime mapped backing identities (#1204) -> link declarations versus mapped objects (#1206) -> live executable memory equality (this atom). It still does not prove compiler/linker invocation, non-executable relocated GOT/PLT/data state, loader decision provenance, later `dlopen`/unload, wrapper/descendant identity, RNG/thread/event/input/output state, source/stopping runtime controls, or any detector response.

## Four sequential AI review passes

### (a) Linux/Geant4 runtime provenance lead — `ACCEPT local mechanism / BLOCK HIBEAM authorisation`
Evidence inspected: #1204/#1206 contracts, Linux proc/mmap documentation, local synthetic and real-child execution. Strongest counter-hypothesis: file-backing identity already equals runtime code identity. Falsifier: one-byte mutation of the live memory fixture causes a deterministic block. Residual uncertainty: no immutable HIBEAM PID/final/runtime receipt was available.

### (b) Adversarial systems mechanism reviewer — `ACCEPT fail-closed equality / REVISE same-object boundary`
Strongest counter-hypothesis: reopening a predecessor path is enough even if the mapped inode is old. Falsifier: current dev/inode plus full SHA-256 is required before comparing memory. A stronger `/proc/<pid>/map_files` FD would avoid pathname rebinding entirely, but open was `EPERM` here. Residual: text relocation/self-modification mechanism is not identified; post-attestation mutation remains possible.

### (c) Independent validation reviewer — `ACCEPT deterministic oracle / BLOCK physics inference`
Evidence: 9 hostile fixtures, real child smoke, no RNG. Strongest counter-hypothesis: a PASS demonstrates Geant4 generator correctness. Falsifier: no HIBEAM executable, event, source sample, detector transport or statistical estimator entered either test. Residual: real HIBEAM runtime and capability/access conditions.

### (d) Claims/provenance reviewer — `ACCEPT provenance refinement / BLOCK CL-021 promotion`
Evidence: #1182 acceptance contract and predecessor limitations. Strongest counter-hypothesis: exact runtime code bytes close the generator claim. Falsifier: linker/static inputs, loader state, RNG/thread/event/input/output manifest, compiled source/stopping hostile controls and detector chain remain unresolved. Residual: all those child atoms.

## Stable concerns

- `G4-MEM-001` P0 provenance: real HIBEAM `/proc/<pid>/mem` access and immutable predecessor receipts are not available; rebuttal requires an exact runtime execution with hashes, PID/start-time, command and receipt chain.
- `G4-MEM-002` P1 provenance: `map_files` same-object open is blocked by current capability policy; rebuttal requires a controlled runtime where the mapping entry can be opened or an equivalent stronger kernel-backed object handle.
- `G4-MEM-003` P1 scope: only file-backed executable segments are compared; non-executable relocated state is unresolved.
- `G4-MEM-004` P1 temporal: this is a stable observation interval, not proof against later `dlopen`, unload or runtime patching.

## Child atoms

- `ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001`: continue stronger same-boundary link/runtime observation when kernel capability permits; do not pretend the blocked map-files route succeeded.
- `ARU-MC-G4-NONEXEC-RELOCATION-001`: determine which non-executable loader-mutated state is scientifically relevant and how to attest it without incorrectly requiring equality with disk.
- `ARU-MC-G4-LINK-COMMAND-001`: linker command, response files, static archives and flags.
- `ARU-MC-G4-LOADER-SEARCH-001`: cwd, secure-execution state, loader cache/config, preload/audit and direct/transitive resolution semantics.
- Existing late-dlopen, wrapper-chain, immutable-consumption, runtime-manifest, source/stopping compiled controls, event-weight and detector-response children remain open.

## Claim/wiki consequences

No public detector/source claim is promoted. #1182 and CL-021 remain gated. A future PASS on real HIBEAM would validate only the bounded runtime-code equality primitive; it cannot validate B2/B8, PID, penetration, timing, calibration, pile-up, rates, ESS, p-values or DATA/MC performance.
