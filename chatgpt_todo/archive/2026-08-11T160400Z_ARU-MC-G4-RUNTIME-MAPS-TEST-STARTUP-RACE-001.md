# ARU-MC-G4-RUNTIME-MAPS-TEST-STARTUP-RACE-001

Status: PARTIAL — bounded fixture repair implemented; exact-final-head duplicate CI contexts required before acceptance.
Parent: `ARU-MC-G4-LOADER-FS-NAMESPACE-001` / #1221 / PR #1222. This child was exposed by branch-protection validation of the parent PR; it does not modify the filesystem-namespace production primitive.

## Atom definition and contract

The affected regression spawns a known Python executable and immediately invokes `attest_runtime_dependencies(...)` on its live `/proc/<pid>` state. The production attestor intentionally requires the executable mapping projection to be unchanged across its two observations:

`M_exec(t_before) == M_exec(t_after)`

or the receipt is BLOCKED. This is a data-integrity condition, not a retry hint.

The test harness had a weaker readiness contract:

`Popen returned => runtime mapping state is ready for stable attestation`.

The exact-head push run falsified that implication. The repaired fixture requires an explicit target-code handshake first:

`child emitted READY from Python -c target code => begin runtime attestation`.

The child command is now `import time; print("READY", flush=True); time.sleep(5)`. The parent blocks on that line before reading `/proc/<pid>` through the production attestor. No arbitrary fixed startup sleep was introduced and the production attestor was not weakened.

## Evidence inspected

- PR #1222 exact head `d264153a943af9d4d486ce4404d05e74569b0d0f` had two MC Validation contexts on the same branch bytes.
- Pull-request run `31509591783` passed: curated ruff `All checks passed!`; full non-integration pytest `1642 passed, 2 skipped, 8 xfailed, 1 xpassed, 7 warnings in 142.59s`; diagnostics and enforcement succeeded.
- Push run `31509587074` failed with exactly one test failure: `tests/test_geant4_runtime_dependency_attestation.py::test_real_procfs_python_process_round_trip`. The production attestor raised `ValueError: executable mapping set changed during runtime attestation`; totals were `1 failed, 1641 passed, 2 skipped, 8 xfailed, 1 xpassed, 7 warnings in 107.40s`. Ruff passed and enforcement failed only because `PYTEST_STATUS=1`.
- Branch protection rejected an attempted squash merge with `Required status check "test" is failing.` PR #1222 was returned to draft.
- The failing test source called `Popen([python, -c, import time; time.sleep(5)])` and immediately entered the production attestor with no target-code readiness handshake.
- No matching existing issue was found by repository issue search for the mapping-startup race; because the bounded repair is being attempted immediately inside #1222, no duplicate standalone issue is opened at this stage.

## Competing mechanisms

H1 — production attestor incorrectly rejects a stable runtime. Survives only if the failure reproduces after explicit target-code readiness; the successful duplicate run is already evidence against a deterministic production defect.

H2 — fixture begins observation while the Python process is still completing interpreter/startup mapping activity. Preferred current hypothesis because the test had no child-code readiness boundary and the failure was exactly a mapping-projection transition.

H3 — the supposedly idle Python target performs later legitimate executable mapping changes even after target code starts. Survives until repaired duplicate exact-head CI is stable; if observed, READY is insufficient and a different state contract is required.

H4 — simply retry the production attestor until one attempt happens to see equality. Rejected: retries would erase evidence of an actual mapping mutation during the authoritative observation window and would weaken a fail-closed provenance contract.

H5 — accept one green duplicate check and ignore the other failed check. Rejected by the repository protection policy itself and by the validation contract that every required exact-head context must pass.

## Eliminated / surviving hypotheses

Eliminated: merge authorization from the green pull-request run alone; weakening `M_exec(t_before)==M_exec(t_after)`; arbitrary sleep as the only readiness predicate.

Surviving: startup/readiness race (H2, preferred); post-readiness lazy mapping mutation (H3, material residual); a deeper production bug only if H1 survives the repaired exact-head runs.

Nuisance/dependency variables include runner load, Python build/runtime initialization sequence, mapped extension/library set, scheduler interleaving between `/proc` reads, child lifetime, and workflow trigger context. None is a detector or physics nuisance parameter.

## Discriminating experiment and negative controls

Implementation commit `33669aa324b148f9408b2785be785f8fca02db00` changes only the live Python regression fixture: child stdout is a pipe, the child emits `READY` after entering target code, and attestation starts only after the parent receives that token. The production attestor remains unchanged and continues to BLOCK on any mapping projection change during its own snapshot.

Acceptance requires both push and pull-request MC Validation contexts on the exact final PR head to pass curated ruff, full non-integration pytest, diagnostics upload, and enforcement. A single green duplicate context is insufficient. Any recurrence of the mapping-set exception after READY rejects H2 as sufficient and requires a new child rather than retries.

## Four sequential AI review passes

### A. Runtime/provenance integration lead
Evidence: same-head green PR run, failed push run, failing test source, unchanged production attestor. Strongest counter-hypothesis: production stability predicate is intrinsically too strict. Falsifier attempted: compare duplicate contexts and isolate the only failure to a live-process fixture with no readiness boundary. Residual uncertainty: target-code readiness may still precede a later lazy mapping. Vote: REVISE fixture / ACCEPT production fail-closed predicate pending repaired CI.

### B. Adversarial Linux/process reviewer
Evidence: exact exception location after second maps observation, immediate Popen-to-attestation transition, branch-protection rejection. Strongest counter-hypothesis: a fixed delay is equivalent to readiness. Falsifier: elapsed time does not identify whether target code has started and is therefore not a state contract. Residual uncertainty: READY itself does not mathematically guarantee future mapping immutability. Vote: ACCEPT handshake as stronger discriminator / BLOCK retry-until-pass semantics.

### C. Independent statistics/validation reviewer
Evidence: identical head produced one green and one failed workflow, so the observed binary check outcome is trigger/run dependent. Strongest counter-hypothesis: the green run demonstrates acceptable reliability. Falsifier: branch protection rejected merge because another required context on the same head failed. Residual uncertainty: one repaired duplicate pair does not estimate long-run flake probability. Vote: BLOCK merge until every exact-final-head required context is green; future repeated flake warrants a separate reliability study.

### D. Claims/provenance reviewer
Evidence: this child concerns a Python/procfs validation fixture only. Strongest counter-hypothesis: successful repair advances Geant4 or detector validity. Falsifier: no HIBEAM executable, Geant4 event, beam data, detector response, event weight, or claim estimator participates. Residual uncertainty: none relevant to physics claims because those remain upstream/downstream gated. Vote: ACCEPT bounded software-provenance repair / BLOCK CL-021 or detector promotion.

## Cross-scale propagation and children

A validated repair would restore confidence that the runtime-dependency test is evaluating a post-startup target process rather than an initialization transient. It does not establish HIBEAM runtime dependency closure, filesystem input consumption, source physics, detector response, or claim validity.

If the READY repair still produces mapping drift, spawn `ARU-MC-G4-RUNTIME-MAPS-POSTREADY-MUTATION-001` to distinguish later `dlopen`/extension activity from scheduler/observation artifacts. The parent filesystem atom retains `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, `ARU-MC-G4-OUTPUT-PATH-CREATION-001`, `ARU-MC-G4-LOADER-EXEC-KERNEL-EVENT-001`, and `ARU-MC-G4-LOADER-EXEC-TARGET-TOCTOU-001`.

## Claim/wiki consequences

No public scientific claim changes. #1057 remains PARTIAL and CL-021 remains gated. No wiki statement should imply that the repository has observed actual HIBEAM config/macro open events or produced a validated Geant4 detector result.
