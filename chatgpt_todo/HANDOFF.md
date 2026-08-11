# Latest Handoff

## Filesystem namespace atom separates pre-exec lookup state from actual input consumption

Protected `main` at selection is `8a064b37245a03dd0258ec20ae73bbc6adc25e2e`, the squash merge of #1220. PR #1220 exact head `43fd82d2fe70d90cea829a28a1e808b2fbf16098` passed MC Validation run `31505415590` and is merged. #1057 remains open/PARTIAL, governance child #1218 remains open, and CL-021 remains gated.

The active atom is `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, tracked as #1221 on branch `audit/geant4-loader-fs-namespace`. Draft PR #1222 targets exact base `main@8a064b...`. Parent #1214 is closed for the bounded exec-cwd primitive; this child does not reopen it.

The repository run front door still invokes `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root` with relative config, macro and output spellings. The bounded pre-exec lookup state is now modeled as

`F_exec = (CWD_obj, Root_obj, MntNS_{st_dev,st_ino}, MountInfo_bytes)`

with exact mountinfo bytes and SHA-256 retained. Runtime composition requires `(PID_pre,starttime_pre)==(PID_runtime,starttime_runtime)` and, for the controlled direct-command route, intended-target path/content equality with the independently content-bound runtime executable.

### Why namespace identity alone is insufficient

The mount namespace object and the mount table are separate state variables. The implementation records `/proc/PID/ns/mnt` link text plus the opened namespace handle `(st_dev,st_ino,st_mode)`, and separately records the exact `/proc/PID/mountinfo` bytes, byte count, line count and SHA-256. Mountinfo is read twice and namespace/root/cwd/process/executable state is re-observed; simple drift during the userspace snapshot fails closed. ABA/shared mutation outside that window remains explicitly unresolved.

### Strongest falsifier: pre-exec state is not input-open state

A real deterministic post-exec `chroot` control changed the process root from pre-exec `(st_dev=65024,st_ino=2)` to later `(st_dev=65024,st_ino=1835628)`. Therefore even a correct pre-exec cwd/root/namespace/mount-table snapshot does not prove the filesystem state when HIBEAM later opens `krakow.config`, `run_krakow.mac`, or auxiliary inputs. That surviving obligation is `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001` and should observe the real open boundary plus the opened bytes rather than infer them from path spellings.

A second real control executed a Python launcher directly into `/bin/sleep`: PID/starttime stayed fixed, launcher `/opt/pyvenv/bin/python` changed to runtime `/usr/bin/sleep`, target size was 43432 bytes with SHA-256 `0637e6d47579929cb72efa46f361861b319d62c62fe8a9d10731fd7655eb5936`, mount namespace was `mnt:[4026532185]`, mountinfo SHA-256 was `32176980937a12ebdf9780930025f473f4594b99248e4a6681cb0d1d08221bff`, and the bounded composition returned PASS. `kernel_execve_event_observed=false` remains explicit.

### Repository work

Branch commits through the draft-PR handoff:

- `07f966fadd056c6368e83ee60c81f05b9165f3c7` — add `tools/audit/geant4_loader_exec_boundary_fs_attestation.py`;
- `6f2d912875cf49ad79bc3fefc4595774e7ca9c08` — add hostile focused tests;
- `dbca8873edad0080e7d37339660a54f0a87a2f61` — add tool/test to curated ruff;
- `8bdb1f6e7439bceba8cf997fd631b108a189830b` — immutable atom archive;
- `257a817a60ca4ac351deebcb6cbda9f57450afb7` and `e7a81d456840bf09e002106dc337a210de4dd3df` — initial coordination;
- `1e9566ddf783e81c80c27cd086be2477613611c4` — record draft PR/final-head gate in ACTIVE_TASK.

Observed GitHub blobs: tool `f173720831c693cf417c1a876626f26da9fc0eca`; focused test `c3777148928cff7fcc9549f1d4dae2e3bd6a6bab`.

Local deterministic authoring-copy validation used Python 3.13.5 with no RNG: `python -m py_compile` passed and focused pytest returned `8 passed in 1.52s`. Local `ruff` is unavailable, so no local lint PASS is claimed. The initially authored source bytes were not byte-identical to the published tool blob because a small annotation refinement occurred during publication; therefore the local focused PASS cannot authorize the exact committed tool. Exact-head GitHub CI is mandatory.

A real `unshare -m true` mount-namespace switch control could not run because the environment returned `Operation not permitted`; do not claim such a control passed.

Immutable record: `chatgpt_todo/archive/2026-08-11T153700Z_ARU-MC-G4-LOADER-FS-NAMESPACE-001.md`. Tracking issue: #1221. Draft PR: #1222.

### Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT bounded filesystem-state decomposition / REVISE production provenance.** Evidence: #1214/#1220, run front door, direct-exec and chroot controls. Strongest counter-hypothesis `F_exec==F_open` was falsified by post-exec root mutation. No provenance-bound HIBEAM process was run.
- **Adversarial Linux/filesystem reviewer — ACCEPT namespace+mountinfo separation / BLOCK input-consumption equivalence.** Namespace inode alone cannot represent a mutable mount table. Residual risks: ABA/shared mount mutation, unavailable real unshare/setns control, kernel exec-event gap and target TOCTOU.
- **Independent validation reviewer — ACCEPT local deterministic falsifiers / BLOCK repository validation pending exact-head CI.** Eight focused authoring-copy tests and py_compile pass with no RNG, but exact published source needs repository CI and local ruff is unavailable.
- **Claims/provenance reviewer — ACCEPT bounded provenance refinement / BLOCK CL-021 and detector inference.** No beam data, production MC, event, reconstruction result or detector observable participates.

### Stable concerns and surviving children

`C-FSNS-001` HIGH: namespace identity alone is insufficient; exact mount-table state is separately required. `C-FSNS-002` HIGH: pre-exec lookup state is not exact input-open state; require open/openat/openat2 or equivalently strong opened-file-byte evidence. `C-FSNS-003` MEDIUM-HIGH: double-read stability does not exclude ABA/shared mutation. `C-FSNS-004` MEDIUM-HIGH: userspace intent is not a kernel exec-event log and target-path TOCTOU remains.

Surviving children are `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, `ARU-MC-G4-OUTPUT-PATH-CREATION-001`, `ARU-MC-G4-LOADER-EXEC-KERNEL-EVENT-001`, and `ARU-MC-G4-LOADER-EXEC-TARGET-TOCTOU-001`. #1057 independently still requires the compiled source-phi and accepted-observable children.

### Immediate gate and next work

PR #1222 must remain draft until the **final branch head after this HANDOFF commit** is current with main and every required MC Validation context passes curated ruff, full non-integration pytest, diagnostics and enforcement. A queued run on the earlier pre-finalization head `e7a81d456840bf09e002106dc337a210de4dd3df` is superseded once coordination advances the branch and must not authorize merge. If a final-head failure appears, repair only the demonstrated defect and rerun.

After this bounded leaf, the next highest-value atom is `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`: bind actual HIBEAM config/macro/auxiliary open state and exact opened bytes for the same runtime process. No production Geant4 campaign, beam/production-MC ROOT bytes, event-weight result, accepted rate, B2/B8, PID, timing, calibration, pile-up, ESS, p-value, or detector-performance quantity was produced or promoted here.
