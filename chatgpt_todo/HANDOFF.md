# Latest Handoff

## Active atom: Linux process-visible argv region, exact-head CI race repaired

Protected source of truth is `main@69678659797d9112a92f911b3011a4411393c1eb` via merged #1212. Current work remains on draft PR #1213, branch `audit/geant4-loader-argv`. #1182 and CL-021 remain gated.

### Parent scientific contract

`ARU-MC-G4-LOADER-ARGV-001` treats `/proc/<pid>/cmdline` only as a process-visible argument-region observation at a stable attestation boundary. It composes a PASS runtime dependency receipt, verifies exact parent digest and `(pid,starttime_ticks,exe_link)`, reads cmdline twice, requires byte equality, preserves all NUL-delimited slots including empty/non-UTF8 bytes, rereads process identity, and self-digests the result. Linux post-exec argv rewriting and `PR_SET_MM_ARG_START/END` prevent promotion to immutable historical `execve(argv)`. `argv[0]` remains non-authoritative for executable identity.

Repository `geant4/setup_and_run.sh` invokes `./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root`, so initial cwd is the next high-information scientific child.

### Exact CI falsifier discovered

At exact PR head `efa67b0ea2849ffc3d041e97487f74953e96f340`, the pull-request-triggered MC Validation run `31485819366` completed successfully. A concurrent push-triggered run `31485815692` on the same head failed despite ruff success because full pytest contained one failure: `test_real_linux_child_observation_is_stable`. Its final count was `1 failed, 1604 passed, 1 skipped, 8 xfailed, 1 xpassed`.

The failing fixture called `subprocess.Popen(['/bin/sleep','5'])`, then treated existence of `/proc/<pid>/cmdline` as readiness. That procfs path existed while the first cmdline read was still `b''`; the production attestor correctly rejected the empty region. The protected branch then correctly refused merge because a failing exact-head `test` check coexisted with the successful one. PR #1213 was returned to draft.

### Repair

`ARU-MC-G4-LOADER-ARGV-TEST-EXEC-RACE-001` is archived at `chatgpt_todo/archive/2026-08-11T112300Z_ARU-MC-G4-LOADER-ARGV-TEST-EXEC-RACE-001.md`.

Commit `52c0496396343613f1833b42e92fa3d0b7f4daec` replaces the path-existence precondition in the two live-process tests with `_wait_for_exec_observation(...)`. The helper polls within a bounded timeout and authorizes the fixture only when:

- the child is alive;
- `/proc/<pid>/cmdline` is nonempty;
- `/proc/<pid>/exe` resolves to the exact intended image;
- starttime is readable for that PID.

A fixed sleep was rejected because elapsed time does not identify process-image readiness. Weakening the production attestor to accept empty cmdline was also rejected because that would destroy the parent data contract. The production attestor is unchanged. The updated test file is Git blob `d312d54cab63166c5f4b5b958f59c6da015fb4e2`.

### Four sequential AI reviews

- **Runtime/physics lead — ACCEPT repair / BLOCK physics inference.** The failure is a real test-harness state-transition race; accepting empty cmdline would be a scientific-contract regression. Real HIBEAM runtime remains unavailable.
- **Adversarial Linux reviewer — ACCEPT state-based wait / REJECT timing-only workaround.** Path existence and arbitrary delay are not equivalent to intended exec-image readiness. A future timeout must remain visible rather than being hidden by retries without state predicates.
- **Independent validation reviewer — REVISE until every fresh exact-head workflow context passes.** One green run did not authorize the earlier head because another exact-head check failed. Fresh repaired-head push and pull-request runs are required.
- **Claims/provenance reviewer — ACCEPT fixture-provenance correction / BLOCK CL-021 promotion.** No beam data, production MC, Geant4 event, detector response or statistical estimator changed.

### Next gate

Keep PR #1213 draft until its final head retains exact `main@696786...` ancestry and every exact-head MC Validation `test` context is successful, including push and pull-request triggers. Require curated ruff, full non-integration pytest, diagnostics upload and enforcement. Only then mark ready and merge with expected-head protection.

After #1213 closes, the next highest-value scientific universe is `ARU-MC-G4-LOADER-INITIAL-CWD-001`, because the historical run front door uses relative executable/config/macro/output paths. The following children remain argv-region mutation, executable redirection, HIBEAM argument semantics, loader cache/config, token/hwcaps, preload/audit, linker/static inputs, late `dlopen`, wrapper/descendant identity, immutable consumption, runtime manifest, compiled source/stopping controls, event weights and detector response.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no detector-performance claim was regenerated or promoted.

---

## Base-freshness gate

Before authorizing a PR, require `base_is_ancestor_of_head AND behind_by == 0 AND merge_base_sha == base_sha` using `tools/audit/validate_pr_base_freshness.py`, and separately inspect GitHub status/check APIs. A current Git graph does not override a failed exact-head required check.
