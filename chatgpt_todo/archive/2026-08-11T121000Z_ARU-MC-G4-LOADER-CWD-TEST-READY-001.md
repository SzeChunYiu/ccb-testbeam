# ARU-MC-G4-LOADER-CWD-TEST-READY-001 — synchronize the real post-exec chdir falsifier

Status: **VALIDATED_LOCAL_FIX / EXACT_HEAD_CI_REQUIRED / PRODUCTION_ATTESTOR_UNCHANGED**

Parent: `ARU-MC-G4-LOADER-INITIAL-CWD-001` on draft PR #1215. This is a validation-harness child, not a new HIBEAM physics mechanism.

## Failure discovered

After publishing the first cwd fixture implementation, an independent local rerun of the exact old authoring copy produced:

```text
.......F.
1 failed, 8 passed in 11.92 s
```

The only failure was `test_post_exec_chdir_falsifies_initial_cwd_interpretation`. The child was launched with `cwd=initial`, but the test helper imposed a three-second polling deadline waiting for procfs cwd to become `later`. Under the observed container load, the Python child remained in its inherited cwd for longer than that deadline before user code reached `chdir`.

This did **not** falsify `ccb_geant4_loader_cwd_attestation_v1`: the production attestor was never invoked on a claimed post-chdir state. It falsified the test precondition that a short elapsed-time window was sufficient evidence that the child had executed the intended post-exec transition.

## Competing mechanisms

H1 — cwd primitive is wrong and still observes the initial directory after `chdir`.

H2 — test observes before child user code reaches `chdir`; startup/scheduling delay is the cause.

H3 — child executes `chdir` but procfs cwd publication is arbitrarily delayed.

H4 — fixed timeout merely needs to be lengthened.

The observed child remained alive and `/proc/<pid>/cwd` stayed at `initial` until the deadline. A separate direct reproduction showed the same Python image could remain in `initial` for several polling iterations and then transition synchronously to `later` once the child reached its code. That supports H2. H4 is rejected as the scientific fix because elapsed time does not identify execution of the transition.

## Preferred discriminator and contract

The test child now executes, in program order:

1. `os.chdir(TARGET_CWD)`;
2. create an absolute `READY_FILE` marker;
3. sleep so the process remains observable.

The parent waits for the explicit post-chdir marker while requiring the child to remain alive. Marker existence is therefore a test-owned state predicate that the child has returned successfully from `chdir`; only then does the parent construct the runtime/argv fixtures and invoke the production cwd attestor.

This is a validation-fixture synchronization mechanism. The marker is **not** part of the production cwd receipt and must never be generalized to HIBEAM provenance.

## Executed validation

Environment: Python 3.13.5, Linux 6.18.35 x86_64, no RNG.

After the repair:

```text
python -m pytest -q tests/test_geant4_loader_cwd_attestation.py
9 passed in 1.07 s
```

Five additional consecutive focused runs returned:

```text
9 passed in 1.07 s
9 passed in 1.14 s
9 passed in 1.01 s
9 passed in 1.12 s
9 passed in 1.05 s
```

`python -m py_compile tools/audit/geant4_loader_cwd_attestation.py tests/test_geant4_loader_cwd_attestation.py` also passed.

Updated test source identity:

- 10,169 bytes;
- SHA-256 `a4e8b6e4cabc114034d8ade82103951c91f01d77998b898c604fdefde50446a1`;
- Git blob SHA-1 `aaf14ee43544fe388ef22692c9f2a5daab4f4ac1`;
- repository commit `198cd5062982947d12410b9371d43ddaa596c4f0`.

Local ruff remains unavailable; repository exact-head CI is still required.

## Hypotheses eliminated / surviving

Eliminated for the fixture:

- fixed three-second elapsed time as proof that post-exec `chdir` occurred;
- increasing an arbitrary sleep/timeout as the primary discriminator;
- weakening the production attestor to accommodate a child that has not reached the intended state.

Surviving:

- explicit test-owned readiness after successful `chdir`;
- bounded timeout only as an outer failure limit for a missing readiness signal.

## Four sequential AI reviews

### Runtime/physics integration lead — **ACCEPT fixture repair / BLOCK physics inference**
Evidence: failed local rerun, direct child transition observation, unchanged production attestor. Strongest counter-hypothesis: production cwd semantics failed. Falsifier: the failing run never reached the post-chdir test precondition, while synchronized repeats pass. Residual: real HIBEAM runtime remains absent.

### Adversarial Linux reviewer — **ACCEPT state predicate / REJECT timing-only repair**
Evidence: inherited cwd before user code, explicit marker after successful `chdir`, child-liveness check. Strongest counter-hypothesis: a longer timeout is equivalent. It is not state-discriminating. Residual: marker is test-specific and must not be mistaken for production provenance.

### Independent validation reviewer — **ACCEPT repeated deterministic repair / REVISE until exact-head CI**
Evidence: one demonstrated old failure followed by six successful repaired runs and py_compile. Strongest counter-hypothesis: one local repair run is sufficient. Additional repeats reduce this exact scheduling concern but do not substitute for repository CI. Residual: GitHub Actions runner behavior and curated ruff.

### Claims/provenance reviewer — **ACCEPT correction / BLOCK CL-021 promotion**
Evidence: no HIBEAM event, detector transport, beam data, event weight or estimator participated. Strongest counter-hypothesis: fixing a live Linux fixture advances detector validation. Rejected. Residual: all production provenance children remain.

## Consequence

PR #1215 must be validated only at a head containing commit `198cd5062982947d12410b9371d43ddaa596c4f0` or later. Any workflow result from the superseded pre-fix head `94c3ae9f5673f80bf1cb4339e3dd47866b39f80a` is non-authorising for the repaired branch.
