# ARU-MC-G4-LOADER-EXEC-IMAGE-TRANSITION-001

Status: PARTIAL — mechanism repaired on draft PR #1220; exact-head full pytest still required before merge.

## Parent and atom contract

Parent: #1214 `ARU-MC-G4-LOADER-INITIAL-CWD-EXEC-BOUNDARY-001`.

Selected atom: distinguish the pre-exec launcher image from the post-exec HIBEAM image while composing an exec-boundary cwd record with the runtime dependency receipt.

Inputs are a digest-bound pre-exec cwd record and a digest-bound runtime dependency receipt. The local measurand is process/provenance state, not a detector observable. No physical unit applies to PID/inode identities; cwd is an opened directory object `(st_dev, st_ino, st_mode)`. File payload identity is byte count plus SHA-256.

Required process invariant across an exec image replacement is

`(PID_pre, starttime_pre) == (PID_post, starttime_post)`.

The executable image is *not* an invariant. A successful launcher-to-target exec normally has

`exe_pre != exe_post`.

For the bounded direct-`os.execv` route implemented in #1220, the launcher records an exec intent containing exact argv strings plus a pre-exec target-file path/content identity. Composition requires runtime executable `(bytes, sha256)` and resolved path to equal that intended target while PID/starttime remain equal. The receipt explicitly records `kernel_execve_event_observed=false`; a userspace intent is not promoted to a kernel event log.

## Competing mechanisms and eliminated descriptions

H1: “same process” implies identical `/proc/<pid>/exe` before and after exec. **Eliminated.** A real Linux Python→`/bin/sleep` exec retained PID/starttime while `/proc/<pid>/exe` changed.

H2: pre/post executable-link equality is a valid positive-path composition check. **Eliminated for a launcher that itself is replaced.** It makes the intended Python→HIBEAM route impossible to attest.

H3: compare only PID/starttime and ignore the target image. **Rejected as underconstrained.** It could compose a cwd record with an unintended later image.

H4: bind PID/starttime plus launcher-declared target path/content to the independently content-bound post-exec runtime executable. **Survives as the strongest currently implementable bounded mechanism.** It still does not prove a single kernel exec event or eliminate target-path TOCTOU between pre-hash and `execv`.

H5: kernel exec-event tracing with cwd/fd state. **Survives as stronger evidence** and is a child atom rather than being silently equated with H4.

## Authoritative semantics inspected

Python 3.11 `os.exec*` documentation states that the new executable replaces the current process and uses the same PID. Linux `chdir(2)` documents that exec leaves the working directory unchanged. Python `argparse` documentation states that subparser selection and options store into their configured `dest` attributes; this explains the independent CLI namespace collision caught by CI.

## Executed falsifiers and exact evidence

1. Pre-repair Linux transition falsifier, no RNG: a Python launcher recorded `/proc/self/stat` starttime and `/proc/self/exe`, then `execv('/bin/sleep', ...)`. Observed PID `461` and starttime `163842` unchanged while executable changed from `/opt/pyvenv/bin/python` to `/usr/bin/sleep`. This falsified pre/post `exe_link` equality.

2. Authoring-copy positive control after the image-transition repair, no RNG: `python -m py_compile /tmp/geant4_loader_exec_boundary_cwd_attestation.py` succeeded. A real CLI launch of the authoring copy executed `/bin/sleep`; observed PID `550`, starttime `193606`, launcher `/opt/pyvenv/bin/python`, runtime `/usr/bin/sleep`, composed status `PASS`, `exec_intent_bound=True`.

3. Authoring-copy focused pytest: `python -m pytest -q /tmp/test_exec_transition.py` -> `2 passed in 0.48s`. The tests exercise a real Python→sleep image replacement and a target-content mismatch negative control. These are local authoring-copy software tests only, not repository CI and not HIBEAM/Geant4 evidence.

4. Prior exact-head repository failure on #1220 head `cbc8a97002f9cc0bbd46c86c302be11ec635556b`: MC Validation run `31501093188` had ruff PASS but full pytest `1 failed, 1632 passed, 1 skipped, 8 xfailed, 1 xpassed`; failure was `test_cli_record_creates_file` because the `--command` option reused the subparser `dest='command'`. Commit `b196482c321c819105ebb8d47fb7d9c838a18ac7` repaired that independent CLI defect.

5. This session then revised the committed mechanism on PR #1220: `677497e3f841dda1f7f80493fcfc05a06b0b3ba2` separated launcher and intended target state; `67113fdbc24dadb12c911772de187d5da4f39b7c` retained backwards-compatible fixture semantics without reintroducing image conflation; `7c8ba682e35aac53a6a6df4625c955784d34d4d6` added a real direct-exec regression; `71bb6775963af8c2b5c399de8655100773b2c97f` added the tool and both focused tests to curated ruff. Exact-head ruff on run `31505059986` passed; full pytest was still running when this archive entry was written, so no exact-head repository PASS is claimed here.

## Four sequential AI review passes

### A. Runtime/physics integration lead
Evidence: #1214 contract, #1220 implementation, runtime dependency receipt, real Python→sleep transition. Strongest counter-hypothesis: executable identity should be stable because PID is stable. Falsifier: same PID/starttime with replaced executable image. Residual uncertainty: no provenance-bound HIBEAM process was executed. Vote: **ACCEPT image-replacement model / REVISE parent completion**.

### B. Adversarial Linux/process reviewer
Evidence: original synthetic post-exec fixture, real exec control, intended-target binding. Strongest counter-hypothesis: the original fixture sufficiently modeled exec. Falsifier: it manually gave the pre-exec record the post-exec executable and therefore skipped the transition under test. Residual uncertainty: userspace pre-hash plus `execv` leaves a target-path TOCTOU window and does not prove a unique kernel exec event. Vote: **ACCEPT bounded intent/runtime composition / BLOCK kernel-event equivalence**.

### C. Independent validation/statistics reviewer
Evidence: failed exact-head CI, deterministic authoring-copy controls, current exact-head ruff PASS. Strongest counter-hypothesis: local PASS authorizes merge. Rejected because exact committed full pytest is still pending. No statistical estimator, event weight or RNG is involved. Vote: **ACCEPT defect and local falsifier / BLOCK merge pending exact-head CI**.

### D. Claims/provenance reviewer
Evidence: source code, tests, #1214, runtime-receipt scope. Strongest counter-hypothesis: cwd provenance now validates MC production. Rejected: namespace/root state, exact relative-input consumption, target TOCTOU/kernel event, RNG/thread/event/output identity, compiled source controls and detector chain remain open. Vote: **ACCEPT bounded provenance repair / BLOCK #1214 completion and CL-021 promotion**.

## Child atoms spawned / surviving dependencies

- `ARU-MC-G4-LOADER-EXEC-KERNEL-EVENT-001`: bind the actual kernel exec event or prove an equivalently strong single-transition contract; do not equate launcher intent with a kernel log.
- `ARU-MC-G4-LOADER-EXEC-TARGET-TOCTOU-001`: eliminate or quantify the path/content replacement window between target hashing and `execv` (for example via an fd-based exec mechanism where platform/runtime support is explicitly bound).
- Existing #1214 children remain: `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, `ARU-MC-G4-OUTPUT-PATH-CREATION-001`.
- A receipt-durability child is material only if crash/power-loss persistence, rather than ordinary post-exec readback, becomes an authorization requirement.

## Cross-scale and claim propagation

This atom repairs a micro-scale process-state composition defect. It cannot by itself authorize relative config/macro bytes, production event identity, source physics, transport, weights, accepted observables, or detector claims. #1057 remains open/PARTIAL and CL-021 remains gated. No wiki/public detector statement should be promoted from this result.

## Handoff

Keep PR #1220 draft until the exact current head is based on current protected main and every required CI context is successful. If CI fails, repair only the demonstrated failure. After this bounded leaf, the highest-value scientific dependency is exact relative-input namespace/consumption or the source-phi compiled closure if a provenance-bound external HIBEAM environment becomes available; static Python CI must not be treated as Geant4 execution.
