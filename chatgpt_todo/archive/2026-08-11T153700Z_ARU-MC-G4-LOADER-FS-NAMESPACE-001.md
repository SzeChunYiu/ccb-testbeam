# ARU-MC-G4-LOADER-FS-NAMESPACE-001 — exec-boundary filesystem lookup state

Status: `PARTIAL / IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_PENDING / INPUT_CONSUMPTION_CHILD_OPEN`

Protected parent main at selection: `8a064b37245a03dd0258ec20ae73bbc6adc25e2e`, squash merge of #1220. Parent #1214 is closed for its bounded exec-cwd primitive. Tracking issue for this child: #1221. Branch: `audit/geant4-loader-fs-namespace`.

## Atom contract

Repository front door `geant4/setup_and_run.sh` executes `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root`; config, macro and output are relative spellings. The bounded pre-exec lookup state is

`F_exec = (CWD_obj, Root_obj, MntNS_{st_dev,st_ino}, MountInfo_bytes)`

with exact `SHA256(MountInfo_bytes)` and the mountinfo bytes retained. Runtime composition requires

`(PID_pre,starttime_pre) = (PID_runtime,starttime_runtime)`.

For the controlled direct-command route, `(resolved_target_path, target_bytes, target_SHA256)` must equal the independently content-bound runtime executable. Directory/namespace values are provenance state, not detector observables or calibrated units.

The implementation reads mountinfo twice and repeats mount-namespace, root-object, cwd-object, process-starttime and launcher-executable observations. Simple drift fails closed. Equality of two reads does not exclude an ABA transition.

## Competing mechanisms and collapse

H1 cwd alone defines relative lookup: rejected.

H2 cwd + mount namespace identity defines the view: rejected because mount-table content can change within one namespace; namespace identity and mount-table state are not equivalent parameterizations.

H3 cwd + root + mount namespace identity + exact mountinfo describe the bounded pre-exec pathname view: survives locally.

H4 H3 also proves actual config/macro bytes later consumed: rejected by a real post-exec `chroot` falsifier.

H5 actual input consumption requires observing the file-open state and hashing the opened file description/bytes for the exact process: survives as child `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`.

`chdir`/`fchdir` are collapsed at this level because both alter the relative lookup start. `chroot`/`pivot_root` are collapsed as process-root mutations. Namespace identity and mountinfo are deliberately not collapsed.

## Evidence inspected

- `main@8a064b37245a03dd0258ec20ae73bbc6adc25e2e` and merged #1220; #1220 exact-head MC Validation run `31505415590` was successful.
- #1214 and its explicit namespace/input-consumption children.
- `geant4/setup_and_run.sh` relative HIBEAM arguments and staged inputs.
- merged cwd and exec-boundary cwd attestors and their explicit namespace/input limitations.
- authoritative Linux/kernel documentation for mount namespaces, `/proc/<pid>/ns/mnt`, `/proc/<pid>/mountinfo`, cwd/root inheritance across exec, `setns`, and pathname resolution.

## Implementation and exact repository writes

- `07f966fadd056c6368e83ee60c81f05b9165f3c7`: add `tools/audit/geant4_loader_exec_boundary_fs_attestation.py`.
- `6f2d912875cf49ad79bc3fefc4595774e7ca9c08`: add `tests/test_geant4_loader_exec_boundary_fs_attestation.py`.
- `dbca8873edad0080e7d37339660a54f0a87a2f61`: add tool/test to curated ruff paths.

GitHub blob identity observed after publication: source blob `f173720831c693cf417c1a876626f26da9fc0eca`; test blob `c3777148928cff7fcc9549f1d4dae2e3bd6a6bab`.

The source captures: thread-group-leader/task nuisance state; exact PID/starttime/launcher executable link; opened cwd/root directory identities; `/proc/PID/ns/mnt` link plus opened namespace handle `(st_dev,st_ino,st_mode)` with inode cross-check; exact mountinfo bytes/base64/SHA-256/counts; repeated stability checks; optional direct-exec target content identity; self-digest. It explicitly says `kernel_execve_event_observed=false` at composition and retains target-TOCTOU, post-exec FS mutation, exact input consumption and output creation as limitations.

## Executed local falsifiers

Environment: Linux, Python 3.13.5, pytest 9.0.2, no RNG. `python -m py_compile tools/audit/geant4_loader_exec_boundary_fs_attestation.py tests/test_geant4_loader_exec_boundary_fs_attestation.py` passed on the authoring copy. `pytest -q tests/test_geant4_loader_exec_boundary_fs_attestation.py` returned `8 passed in 1.52s` on the authoring copy. Local `ruff` was unavailable; no local ruff PASS is claimed.

Focused controls cover: real `/proc` positive snapshot and self-digest; same-process composition; tampered-record rejection; process-identity mismatch; injected mountinfo drift; injected mount-namespace drift; real Python launcher -> `/bin/sleep` direct exec; and real post-exec `chroot` root-state mutation.

Direct-exec control: PID `666`; starttime pre/post `156741`; launcher `/opt/pyvenv/bin/python`; runtime `/usr/bin/sleep`; target size `43432` bytes; target SHA-256 `0637e6d47579929cb72efa46f361861b319d62c62fe8a9d10731fd7655eb5936`; mount namespace `mnt:[4026532185]`; mountinfo SHA-256 `32176980937a12ebdf9780930025f473f4594b99248e4a6681cb0d1d08221bff`; bounded attestation `PASS`; kernel exec event not observed.

Post-exec chroot control: PID `632`; pre-exec root `(st_dev=65024, st_ino=2)`; later root `(st_dev=65024, st_ino=1835628)`; later `/proc/PID/root` pointed to the temporary new root. This directly falsifies `F_exec == F_open` as a general rule.

`unshare -m true` was attempted and failed `Operation not permitted`; no real mount-namespace-switch result is claimed.

Important provenance boundary: the local source authoring bytes were not byte-identical to the first committed source blob because a small type-annotation refinement occurred during publication. Therefore the local 8-test result is authoring-copy evidence only and does not authorize the committed blob. Exact-head GitHub CI is required.

## Stable concerns

`C-FSNS-001` HIGH — namespace inode alone is insufficient. Evidence: Linux mount-namespace semantics plus injected mountinfo drift. Requirement: retain exact mount table state or a stronger equivalent at the bounded observation.

`C-FSNS-002` HIGH — pre-exec state is not actual input-open state. Evidence: real post-exec chroot changes root after exec. Requirement: downstream open/openat/openat2 plus opened-file-byte binding for each material input.

`C-FSNS-003` MEDIUM-HIGH — double-read stability excludes simple drift, not ABA or mutation outside the snapshot window/shared namespace. Requirement: preserve limitation; stronger kernel/open co-observation if needed for production authorization.

`C-FSNS-004` MEDIUM-HIGH — userspace direct-exec intent is not a kernel exec-event record and target path TOCTOU remains. Requirement: retain the existing exec-event/TOCTOU children rather than upgrading wording.

## Four sequential AI reviews

### A. Runtime/physics integration lead
Evidence: #1214/#1220 contracts, repository run command, Linux lookup state, direct-exec and chroot controls. Strongest counter-hypothesis: pre-exec state equals later input-open state. Attempted falsifier: post-exec chroot; it changed the root object. Residual uncertainty: no provenance-bound HIBEAM process was run and HIBEAM post-exec filesystem behavior is not observed. Vote: `ACCEPT bounded filesystem-state decomposition / REVISE production provenance`.

### B. Adversarial Linux/filesystem reviewer
Evidence: namespace handle, exact mountinfo bytes, drift injections, task-state nuisance, target-content composition. Strongest counter-hypothesis: namespace inode is a complete mount-view identifier. Attempted falsifier: mountinfo mutation with unchanged conceptual namespace identity; the implementation rejects drift and Linux semantics permit mount-list changes within a namespace. Residual uncertainty: ABA/shared mount mutation, unavailable real unshare/setns control, kernel exec-event and target TOCTOU. Vote: `ACCEPT namespace+mountinfo separation / BLOCK input-consumption equivalence`.

### C. Independent statistics/validation reviewer
Evidence: deterministic focused suite, py_compile, exact branch/blob identities. No event weights/statistical estimator applies. Strongest counter-hypothesis: local authoring-copy tests validate the committed branch. Falsifier: published source blob differs from the local authoring-byte identity. Residual uncertainty: exact committed ruff/full pytest not yet known. Vote: `ACCEPT local deterministic falsifiers / BLOCK repository validation pending exact-head CI`.

### D. Claims/provenance reviewer
Evidence: no beam data, production MC, event, reconstruction or detector observable participates; claim gates under CL-021 and #1057 remain separate. Strongest counter-hypothesis: stronger OS provenance validates historical MC. Falsifier: exact relative inputs, output creation, runtime RNG/thread/event/output state and detector chain remain open. Residual uncertainty: all those children. Vote: `ACCEPT provenance refinement / BLOCK CL-021 and detector inference`.

## Children and cross-scale compatibility

Surviving children: `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, `ARU-MC-G4-OUTPUT-PATH-CREATION-001`, `ARU-MC-G4-LOADER-EXEC-KERNEL-EVENT-001`, and `ARU-MC-G4-LOADER-EXEC-TARGET-TOCTOU-001`. The parent atom must not be used to authorize historical/production HIBEAM provenance until its local state composes with actual input-open state and the broader runtime/source/detector chain.

No public claim/wiki promotion follows from this atom. CL-021 remains gated. #1057 remains open/PARTIAL for source-phi compiled/accepted-observable/polarization/provenance children.

## Immediate gate

Open a draft PR from `audit/geant4-loader-fs-namespace`, require exact final-head curated ruff + full non-integration pytest + diagnostics + enforcement, and merge only if every required context is successful and the base remains current. If CI fails, repair only the demonstrated defect. Next scientific atom after this bounded leaf: exact relative-input consumption at the real file-open boundary.
