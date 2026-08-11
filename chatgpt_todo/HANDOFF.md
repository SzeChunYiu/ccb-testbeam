# Latest Handoff

## Exec-boundary cwd review exposed an executable-image composition defect

Protected `main` is `5c1e2ecafa792e07f785781a55f25ffdf3180eb9`, the validated squash merge of coordination PR #1219. #1057 remains open/PARTIAL, governance child #1218 remains open, and CL-021 remains gated.

The active implementation is draft PR #1220 under parent issue #1214. The initial design correctly recognized that a later `/proc/<pid>/cwd` cannot by itself prove the cwd at exec, but it incorrectly treated `(pid,starttime,exe_link)` as unchanged across direct exec. That collapses the pre-exec launcher image with the post-exec HIBEAM image.

A real deterministic Linux falsifier established the correct transition: a Python launcher recorded its process state and then `execv('/bin/sleep', ...)`; PID and `/proc/<pid>/stat` starttime stayed fixed while `/proc/<pid>/exe` changed from the Python executable to `/usr/bin/sleep`. Therefore the executable link is not part of the invariant that composes the two observations.

The repaired bounded contract is:

`(PID_pre, starttime_pre) == (PID_post, starttime_post)`

while launcher and runtime executable identities remain distinct state variables. For the repository's direct `record --command ...` route, the pre-exec record now includes the intended target path and exact `(bytes,SHA-256)`; the attestor requires those target bytes/path to equal the independently content-bound runtime executable. The result explicitly records `kernel_execve_event_observed=false`: userspace launcher intent is not silently promoted to a kernel event log.

### Exact repository evidence

The earlier #1220 exact-head run `31501093188` on `cbc8a97002f9cc0bbd46c86c302be11ec635556b` had curated ruff PASS but full pytest `1 failed, 1632 passed, 1 skipped, 8 xfailed, 1 xpassed`. The only failure, `test_cli_record_creates_file`, exposed a separate argparse defect: `--command` reused the same `dest='command'` as the subparser selector. Commit `b196482c321c819105ebb8d47fb7d9c838a18ac7` fixed that namespace collision.

This session then committed the scientific/provenance repair on the same PR: `677497e3f841dda1f7f80493fcfc05a06b0b3ba2` separates launcher and intended-target state; `67113fdbc24dadb12c911772de187d5da4f39b7c` preserves the legacy fixture surface while keeping real exec transitions explicit; `7c8ba682e35aac53a6a6df4625c955784d34d4d6` adds a real Python→`/bin/sleep` direct-exec regression plus target-content mismatch control; `71bb6775963af8c2b5c399de8655100773b2c97f` adds the tool and both focused tests to curated ruff.

Authoring-copy validation, no RNG: `python -m py_compile` succeeded; a real CLI transition observed PID `550`, starttime `193606`, launcher `/opt/pyvenv/bin/python`, runtime `/usr/bin/sleep`, composed status `PASS`; `python -m pytest -q /tmp/test_exec_transition.py` returned `2 passed in 0.48s`. These results do not substitute for exact committed CI or HIBEAM execution.

Immutable atom record: `chatgpt_todo/archive/2026-08-11T151000Z_ARU-MC-G4-LOADER-EXEC-IMAGE-TRANSITION-001.md`.

### Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT image-replacement model / REVISE parent completion.** The real exec control falsifies pre/post executable equality. No provenance-bound HIBEAM process was run.
- **Adversarial Linux/process reviewer — ACCEPT bounded intent/runtime composition / BLOCK kernel-event equivalence.** The original post-exec fixture manually assigned the post-exec executable to the pre-exec record and skipped the transition under test. Target-path TOCTOU and intermediate exec chains survive.
- **Independent validation reviewer — ACCEPT defect and deterministic local falsifier / BLOCK merge pending exact-head repository CI.** No statistical estimator or event weight applies to this atom.
- **Claims/provenance reviewer — ACCEPT bounded process-state repair / BLOCK #1214 completion and CL-021 promotion.** Namespace, exact relative-input consumption, output path creation, RNG/thread/event/output identity, compiled source controls and detector response remain independent gates.

### Surviving children

`ARU-MC-G4-LOADER-EXEC-KERNEL-EVENT-001` must bind the actual kernel exec event, or establish an equivalently strong single-transition contract, before launcher intent is described as kernel-observed history. `ARU-MC-G4-LOADER-EXEC-TARGET-TOCTOU-001` must close the replacement window between pre-exec target hashing and path-based `execv`. Existing #1214 children `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, and `ARU-MC-G4-OUTPUT-PATH-CREATION-001` remain open.

### Immediate gate and next scientific work

PR #1220 is draft. Require the final committed head to be based on current main and require every required MC Validation context to pass curated ruff, full non-integration pytest, diagnostics and enforcement. If a final-head failure appears, repair only the demonstrated failure and rerun. Do not merge based on the local controls or a superseded green context.

After this bounded leaf, the highest-value ready provenance step is filesystem namespace plus exact relative-input consumption. Independently, #1057 still requires `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001` once a provenance-bound external HIBEAM build/run environment is available; current Python/static CI must not be treated as compiled Geant4 evidence.

No production Geant4 campaign, beam or production-MC ROOT bytes, event-weight result, accepted rate, B2/B8, PID, timing, calibration, pile-up, ESS, p-value, or detector-performance quantity was produced or promoted in this run.
