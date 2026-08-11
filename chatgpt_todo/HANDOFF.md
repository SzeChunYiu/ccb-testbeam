# Latest Handoff

## Filesystem namespace atom: implementation survives pytest, CI exposed a bounded lint defect

Protected `main` at selection is `8a064b37245a03dd0258ec20ae73bbc6adc25e2e`, squash merge of #1220. #1057 remains open/PARTIAL, governance child #1218 remains open, and CL-021 remains gated.

The active atom is `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, tracked as #1221 on branch `audit/geant4-loader-fs-namespace` and draft PR #1222. Parent #1214 is closed only for the bounded exec-cwd primitive.

The repository front door still invokes `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root` with relative config, macro and output spellings. The bounded pre-exec state is

`F_exec = (CWD_obj, Root_obj, MntNS_{st_dev,st_ino}, MountInfo_bytes)`

with exact mountinfo content and SHA-256. Runtime composition requires `(PID_pre,starttime_pre)==(PID_runtime,starttime_runtime)` plus intended-target path/content equality on the controlled direct-exec route. Mount-namespace identity and mount-table bytes remain separate observables.

A real post-exec `chroot` control changed the process root from pre-exec `(st_dev=65024,st_ino=2)` to later `(st_dev=65024,st_ino=1835628)`, so `F_exec` does not prove the state at later HIBEAM input-open time. This leaves `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001` as the mandatory child for exact config/macro/auxiliary bytes. A real Python -> `/bin/sleep` direct-exec control preserved PID/starttime while the executable image changed and the intended target content composed successfully; this is software/provenance evidence only.

## Exact-head CI result and repair

PR #1222 head `167bae0853bea35ee634125f44e11e302e0cbe55` ran MC Validation `31508268931`. Full non-integration pytest succeeded with `1642 passed, 2 skipped, 8 xfailed, 1 xpassed, 7 warnings in 124.84s`, but enforcement failed because curated ruff returned five `E501` findings: two lines in `tests/test_geant4_loader_exec_boundary_fs_attestation.py` and three in `tools/audit/geant4_loader_exec_boundary_fs_attestation.py`.

The failure was repaired without weakening the lint gate:

- `e90a613ff4d7ddd103786f455e0a891f777bd078` wraps the two test lines;
- `bd8c2b7293aff60772117b8f19a93c1f508917dc` wraps the three production provenance literals using adjacent Python string literals, preserving the exact previous string values;
- `ebcdc3ae080764b54ccaa2afee64e13d3c3d77fd` updates `ACTIVE_TASK.md` with the failure and repair.

The diff of the two repair commits is formatting-only: no receipt field name, contract equation, filesystem-state predicate, test assertion, or scientific interpretation was intentionally changed. The previous local authoring-copy focused suite (`8 passed in 1.52s`, Python 3.13.5, no RNG) remains non-authorizing because it did not execute the final committed blobs. Local ruff was unavailable. `unshare -m true` previously failed `Operation not permitted`, so no real mount-namespace-switch PASS exists.

## Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT bounded filesystem-state decomposition / REVISE repository validation.** Evidence: run front door, direct-exec/chroot controls, exact-head pytest pass. Strongest counter-hypothesis is that pre-exec state equals open-time state; chroot falsifies it. Residual uncertainty is actual HIBEAM post-exec behavior.
- **Adversarial Linux/filesystem reviewer — ACCEPT namespace+mountinfo separation and formatting-only repair / BLOCK input-consumption equivalence.** Strongest counter-hypothesis is namespace identity alone suffices; mutable mount-table semantics reject it. Residual risks are ABA/shared mutation, target TOCTOU and the unobserved kernel exec event.
- **Independent validation reviewer — BLOCK merge pending exact-head green CI.** The failed run demonstrates that pytest success alone is insufficient because the protected workflow separately enforces ruff. A fresh final-head run must pass curated ruff, full pytest, diagnostics and enforcement.
- **Claims/provenance reviewer — ACCEPT bounded provenance refinement / BLOCK CL-021 and detector inference.** No beam data, production MC, Geant4 event, reconstruction result or detector observable participates.

## Stable concerns and children

`C-FSNS-001` HIGH: namespace identity alone is insufficient. `C-FSNS-002` HIGH: pre-exec lookup state is not exact input-open state. `C-FSNS-003` MEDIUM-HIGH: repeated equal snapshots do not exclude ABA/shared mutation. `C-FSNS-004` MEDIUM-HIGH: userspace direct-exec intent is not a kernel exec-event log and target-path TOCTOU remains.

Surviving children are `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, `ARU-MC-G4-OUTPUT-PATH-CREATION-001`, `ARU-MC-G4-LOADER-EXEC-KERNEL-EVENT-001`, and `ARU-MC-G4-LOADER-EXEC-TARGET-TOCTOU-001`. #1057 independently still requires compiled source-phi and accepted-observable closure.

## Immediate next action

This HANDOFF update advances the branch again, so any run on `bd8c2b...` is now superseded for merge authorization. Keep PR #1222 draft until every required MC Validation context passes on the exact final head after this commit. If green, mark ready and merge with an expected-head guard only if protected main ancestry is still current. If CI fails, repair only the demonstrated defect.

After #1222 is bounded and merged, the next highest-information atom is `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`: observe the actual open boundary and content-bind the opened HIBEAM config/macro/auxiliary file descriptions rather than inferring them from pre-exec pathname state. No production Geant4 campaign, beam/production-MC ROOT bytes, event-weight result, accepted rate, PID, timing, calibration, pile-up, ESS, p-value, or detector-performance quantity was produced or promoted in this handoff.
