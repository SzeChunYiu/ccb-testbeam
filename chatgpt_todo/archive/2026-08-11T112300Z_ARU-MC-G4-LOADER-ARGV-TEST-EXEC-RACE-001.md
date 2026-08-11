# ARU-MC-G4-LOADER-ARGV-TEST-EXEC-RACE-001

Status: `PARTIAL / REPAIRED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED`

Parent: `ARU-MC-G4-LOADER-ARGV-001` on PR #1213.

## Atom definition and contract

The atom is the test-harness transition from `subprocess.Popen(...)` return to an authoritative live `/proc/<pid>` observation of the intended exec image. Inputs are a child PID and intended executable. Outputs are the proc directory, Linux process `starttime_ticks`, and `/proc/<pid>/exe` link used to construct the parent runtime fixture. Scientific meaning is limited to test-fixture readiness; this atom does not alter the argv attestor's fail-closed rule for an empty command-line region.

Required precondition before invoking the real-procfs attestor in a test:

1. the child is still alive;
2. `/proc/<pid>/cmdline` is nonempty;
3. `/proc/<pid>/exe`, resolved at observation time, identifies the intended executable image;
4. process `starttime_ticks` is readable from the same PID;
5. otherwise retry only within a bounded timeout and fail the test if the intended exec state is never observed.

Path existence alone is not a readiness signal.

## Evidence inspected

Exact head `efa67b0ea2849ffc3d041e97487f74953e96f340` produced two MC Validation checks with the same `test` context. Pull-request run `31485819366` passed. Push run `31485815692` failed even though ruff passed; its full pytest step reported `1 failed, 1604 passed, 1 skipped, 8 xfailed, 1 xpassed` and enforcement correctly failed.

The sole failure was `test_real_linux_child_observation_is_stable`: after `Popen(['/bin/sleep','5'])`, the fixture waited only for `/proc/<pid>/cmdline` *path existence*. That path existed, but the first read returned `b''`, and the production attestor correctly rejected the empty region. This is a fixture synchronization race, not evidence that the attestor should accept empty cmdline.

The initially attempted merge was rejected by protected-branch status because the failed push `test` check coexisted with the successful PR check on the same head. PR #1213 was returned to draft.

## Mechanisms

- H1: `Popen` return + procfs path existence implies the intended executable's procfs argument region is ready. **Eliminated** by run `31485815692`.
- H2: weaken the attestor so empty cmdline is accepted. **Rejected**: that would destroy the parent's explicit fail-closed data contract and conflate fixture startup with valid observation.
- H3: sleep for a fixed arbitrary delay. **Rejected** as timing-only and not state-discriminating.
- H4: poll boundedly until the child is alive, cmdline is nonempty, and `/proc/<pid>/exe` resolves to the intended image, then measure starttime and proceed. **Survives and implemented**.

Equivalent retry loops that check only path existence or only elapsed time are collapsed into H1/H3 because neither proves image readiness.

## Implementation

Commit `52c0496396343613f1833b42e92fa3d0b7f4daec` updates `tests/test_geant4_loader_argv_attestation.py` with `_wait_for_exec_observation(...)`. Both real Linux process tests now require nonempty cmdline plus exact expected executable identity before constructing the runtime fixture. The new test blob is `d312d54cab63166c5f4b5b958f59c6da015fb4e2`.

The production attestor `tools/audit/geant4_loader_argv_attestation.py` is unchanged.

## Negative controls and acceptance criteria

The failed CI run itself is the injected scheduling/race falsifier. Acceptance requires both fresh push-triggered and pull-request-triggered exact-head MC Validation contexts to succeed at the repaired head, with curated ruff, full pytest, diagnostics upload, and enforcement all green. A single green duplicate context is insufficient while another exact-head `test` check fails.

No RNG is introduced by the repair. The timeout is a fixture liveness bound, not a scientific parameter.

## Four sequential AI reviews

### (a) Runtime/physics lead — `ACCEPT repair / BLOCK physics inference`
Evidence: failed exact-head CI plus unchanged production attestor contract. Strongest counter-hypothesis: empty procfs cmdline is a valid stable argv observation. Falsifier: the intended test claims `/bin/sleep` argv slots and therefore requires the intended exec image first. Residual uncertainty: real HIBEAM runtime remains unavailable.

### (b) Adversarial mechanism reviewer — `ACCEPT state-based wait / REJECT timing-only workaround`
Evidence: path-existence wait failed nondeterministically while PR-run scheduling happened to pass. Strongest counter-hypothesis: add a sleep. Rejected because elapsed time does not identify the observed executable image. Residual: extremely overloaded runners may hit the bounded timeout, which should remain a visible test failure rather than silently weakening the contract.

### (c) Independent validation reviewer — `REVISE until exact-head duplicate checks both pass`
Evidence: one exact-head run passed and one failed before repair; deterministic fixtures elsewhere passed. Strongest counter-hypothesis: one green PR run authorizes merge. Protected branch correctly disproved that operationally. Residual: fresh repaired-head CI pending.

### (d) Claims/provenance reviewer — `ACCEPT fixture-provenance correction / BLOCK CL-021 promotion`
Evidence: no beam data, Geant4 event, source law, detector response, or statistical estimator participates. Strongest counter-hypothesis: fixing CI race increases physics evidence. It does not. Residual: all generator/runtime/detector children remain.

## Cross-scale and claim consequences

The local repair preserves the parent's scientific meaning: an empty `/proc/<pid>/cmdline` remains non-authorising. It only prevents the test harness from observing before its own intended child exec state is established. No public detector or MC claim changes status.

## Child atoms

No new physics child is introduced. Operationally, duplicate workflow contexts on the same head must all be green before merge; if state-based synchronization still flakes, inspect the exact failing state rather than adding retries without a measured predicate.
