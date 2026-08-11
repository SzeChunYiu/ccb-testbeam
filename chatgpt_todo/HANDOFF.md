# Latest Handoff

## Filesystem namespace atom: same-head duplicate CI exposed a live-process startup race

Protected `main` at selection remains `8a064b37245a03dd0258ec20ae73bbc6adc25e2e`, squash merge of #1220. #1057 remains open/PARTIAL, governance child #1218 remains open, and CL-021 remains gated.

The active parent is `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, tracked as #1221 on branch `audit/geant4-loader-fs-namespace` and PR #1222. Parent #1214 is closed only for the bounded exec-cwd primitive. The repository front door still invokes `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root` with relative config, macro and output spellings.

The bounded pre-exec state is `F_exec=(CWD_obj,Root_obj,MntNS_{st_dev,st_ino},MountInfo_bytes)`, with exact mountinfo content/SHA-256. Runtime composition requires `(PID_pre,starttime_pre)==(PID_runtime,starttime_runtime)` plus intended-target path/content equality on the controlled direct-exec route. A real post-exec `chroot` control changed the root object, so this does not prove HIBEAM input-open state; `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001` remains mandatory.

## CI chronology

An earlier head `167bae0853bea35ee634125f44e11e302e0cbe55` failed only curated ruff with five E501 findings while full pytest passed. Formatting-only commits `e90a613ff4d7ddd103786f455e0a891f777bd078` and `bd8c2b7293aff60772117b8f19a93c1f508917dc` repaired those findings without weakening the gate.

The next exact head `d264153a943af9d4d486ce4404d05e74569b0d0f` then produced two contradictory required workflow results:

- pull-request run `31509591783`: PASS; curated ruff `All checks passed!`; pytest `1642 passed, 2 skipped, 8 xfailed, 1 xpassed, 7 warnings in 142.59s`; diagnostics and enforcement succeeded;
- push run `31509587074`: FAIL; ruff passed, but `test_real_procfs_python_process_round_trip` alone raised `ValueError: executable mapping set changed during runtime attestation`; totals `1 failed, 1641 passed, 2 skipped, 8 xfailed, 1 xpassed, 7 warnings in 107.40s`; enforcement failed because `PYTEST_STATUS=1`.

A merge was attempted only after the pull-request run appeared green, but branch protection rejected it with `Required status check "test" is failing.` The second run was then inspected and the PR was returned to draft. This is preserved as evidence that one green duplicate context is not merge authorization.

## Validation child and solve-first repair

The new child is `ARU-MC-G4-RUNTIME-MAPS-TEST-STARTUP-RACE-001`, archived at `chatgpt_todo/archive/2026-08-11T160400Z_ARU-MC-G4-RUNTIME-MAPS-TEST-STARTUP-RACE-001.md`. No duplicate issue was found; because the bounded repair is implemented in the current PR, #1221 remains the coordination parent rather than opening a new issue.

The production runtime attestor intentionally requires `M_exec(t_before)==M_exec(t_after)` and remains unchanged. The failing live regression spawned Python and immediately entered the attestor with no target-code readiness boundary. The strongest current hypothesis is therefore startup/readiness timing; a later legitimate mapping mutation remains a surviving counter-hypothesis.

Commit `33669aa324b148f9408b2785be785f8fca02db00` changes only the live Python fixture. The child now emits `READY` from its `python -c` target code using a flushed stdout pipe, and the parent begins attestation only after receiving that token. This is a state discriminator, not a fixed-delay workaround. Retrying the production attestor until it happens to see a stable mapping set is explicitly rejected because it would erase evidence of real mutation during an authoritative receipt.

## Four sequential AI reviews

- **Runtime/provenance integration lead — ACCEPT filesystem decomposition / REVISE fixture validation.** Evidence: same-head green/fail pair and exact failure location. Strongest counter-hypothesis is an over-strict production predicate; it survives only if mapping drift recurs after explicit target-code readiness. Residual uncertainty: later lazy mapping activity.
- **Adversarial Linux/process reviewer — ACCEPT target-code readiness discriminator / BLOCK retry-until-pass and input-consumption equivalence.** A fixed sleep does not identify process state. READY is stronger but does not guarantee future mapping immutability.
- **Independent validation reviewer — BLOCK merge pending every duplicate exact-final-head context.** The same SHA generated opposite workflow outcomes, and branch protection correctly refused merge. One repaired green run is not enough if another required context fails.
- **Claims/provenance reviewer — ACCEPT bounded software-provenance repair / BLOCK CL-021 and detector inference.** No HIBEAM executable, Geant4 event, beam data, detector response, event weight, or public detector estimator participates.

## Stable concerns and children

`C-FSNS-001` HIGH: namespace identity alone insufficient. `C-FSNS-002` HIGH: pre-exec lookup state is not exact input-open state. `C-FSNS-003` MEDIUM-HIGH: equal repeated snapshots do not exclude ABA/shared mutation. `C-FSNS-004` MEDIUM-HIGH: kernel exec event and target TOCTOU remain unresolved. `C-MAPS-RACE-001` MEDIUM-HIGH: even target-code readiness may precede later executable mapping changes; recurrence must spawn `ARU-MC-G4-RUNTIME-MAPS-POSTREADY-MUTATION-001` rather than trigger retries.

Parent children remain `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, `ARU-MC-G4-OUTPUT-PATH-CREATION-001`, `ARU-MC-G4-LOADER-EXEC-KERNEL-EVENT-001`, and `ARU-MC-G4-LOADER-EXEC-TARGET-TOCTOU-001`. #1057 independently still requires compiled source-phi and accepted-observable closure.

## Immediate next action

This handoff update creates another final branch head. Keep #1222 draft until both push and pull-request MC Validation contexts on that exact final head pass curated ruff, full non-integration pytest, diagnostics and enforcement. If the READY fixture still produces mapping drift, do not retry to green; investigate post-readiness mapping mechanisms. If both contexts are green and protected main ancestry remains current, mark ready and merge with an expected-head guard.

After the bounded PR lands, the highest-information scientific child is `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`: observe actual file-open state and content-bind the opened HIBEAM config/macro/auxiliary file descriptions rather than inferring them from pre-exec pathname state. No production Geant4 campaign, beam/production-MC ROOT bytes, event-weight result, accepted rate, PID, timing, calibration, pile-up, ESS, p-value, or detector-performance quantity was produced or promoted here.
