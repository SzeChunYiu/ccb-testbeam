# Latest Handoff

## Active atom: current cwd observation; live post-exec falsifier synchronized

Protected source of truth is `main@c485d96583df91e90669e402670a3fa102643495`, the squash merge of #1213. That merge was authorized only after both exact-head `test` checks on `85894ad0123ee56dc18da6cc86e0340f9eabb312` were successful. Current work is draft PR #1215 on `audit/geant4-loader-cwd`; unresolved exec-boundary cwd leaf is #1214. CL-021 remains gated.

### Parent scientific contract

`ARU-MC-G4-LOADER-INITIAL-CWD-001` addresses the relative-path dependency exposed by:

`./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root`

For a relative pathname `p`, use `Resolved_t(p) = Resolve(CWD_t, Root_t, MountNS_t, p)` as the dependency model. This PR binds only `CWD_t` at a bounded observation window. It does not bind historical exec-time cwd, process root/mount topology, symlink resolution, or the exact bytes HIBEAM later consumes.

The new `ccb_geant4_loader_cwd_attestation_v1` composes PASS/digest-valid runtime and argv receipts, requires identical `(pid,starttime_ticks,exe_link)`, observes `/proc/<pid>/cwd` twice, independently opens the cwd directory object twice and requires equal `(st_dev,st_ino,st_mode)`, then rechecks starttime and executable link. Scope is `STABLE_CURRENT_WORKING_DIRECTORY_OBJECT_OBSERVATION_ONLY`.

### Scientific falsifier and validation-child correction

The main counter-hypothesis is that because exec preserves cwd, a later procfs cwd may be treated as launch/exec cwd. The live negative control starts a Python child with `cwd=initial`, then the child executes `chdir(later)`. Once successful post-chdir execution is established, the attestor observes `later`, not `initial`; current cwd is therefore not immutable historical cwd evidence.

An independent local rerun after the first publication exposed a fixture defect before merge: the superseded test source produced `1 failed, 8 passed in 11.92 s`. The child stayed alive in its inherited cwd longer than the fixture's three-second polling deadline, so the test had not established that user code reached `chdir`. The production attestor was not the failing mechanism.

`ARU-MC-G4-LOADER-CWD-TEST-READY-001` fixes only that precondition. Commit `198cd5062982947d12410b9371d43ddaa596c4f0` makes the child create an absolute test-owned marker **after** successful `chdir`; the parent waits for that state signal while checking child liveness, then constructs the runtime/argv receipts and runs the unchanged cwd attestor. A longer arbitrary sleep was rejected as non-discriminating.

### Executed validation and exact identities

Environment: Python 3.13.5 / Linux 6.18.35 x86_64 / no RNG.

After the repair, the focused suite passed six consecutive times:

- `9 passed in 1.07 s`
- `9 passed in 1.07 s`
- `9 passed in 1.14 s`
- `9 passed in 1.01 s`
- `9 passed in 1.12 s`
- `9 passed in 1.05 s`

`python -m py_compile tools/audit/geant4_loader_cwd_attestation.py tests/test_geant4_loader_cwd_attestation.py` passed. Local ruff is unavailable; no local ruff PASS is claimed.

Exact committed identities:

- tool: 10,190 bytes, SHA-256 `02ed0bb6cd4f53a7e72e59f0147e06eee72e7a7518c0d8de11aa62b856f5e1be`, Git blob `bb71a692732c3f6730b52704bd51ec9506cff7ac`;
- repaired tests: 10,169 bytes, SHA-256 `a4e8b6e4cabc114034d8ade82103951c91f01d77998b898c604fdefde50446a1`, Git blob `aaf14ee43544fe388ef22692c9f2a5daab4f4ac1`.

Key branch commits:

- `475d0f886b0257b1cfd905e798254a07ec8a8dd8` — cwd attestor;
- `c0131e9cc7740303505554266b207fa42567bf70` — initial hostile tests;
- `7acb18fa686a2456093c61087491c2a7ec2a114d` — curated MC-validation ruff inclusion;
- `b8d66da03d194040d3bd44bc386aa83098841604` — parent immutable ARU record;
- `198cd5062982947d12410b9371d43ddaa596c4f0` — explicit post-chdir test synchronization;
- `162fd90de7869e96934a5f884fbf2ae22ebdef93` — validation-child archive.

### Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT current-state primitive and fixture repair / BLOCK initial-cwd provenance.** The synchronized post-exec `chdir` control falsifies historical-cwd promotion; no real HIBEAM process is observed.
- **Adversarial Linux/filesystem reviewer — ACCEPT state predicate / REJECT timing-only repair / BLOCK complete path resolution.** Stable cwd still does not bind root/mount namespace, symlink chain, or ABA transitions.
- **Independent validation reviewer — ACCEPT repeated deterministic repair / REVISE until exact-head CI.** One demonstrated old failure plus six repaired passes is useful evidence, but repository ruff/full pytest on the final commit remains mandatory.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** No event, transport, detector response or beam estimator participates.

### Children and next gate

#1214 owns `ARU-MC-G4-LOADER-INITIAL-CWD-EXEC-BOUNDARY-001`: prove cwd at the actual exec transition. Other children remain `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, and `ARU-MC-G4-OUTPUT-PATH-CREATION-001`, followed by loader cache/config, token/hwcaps, preload/audit, linker/static inputs, late `dlopen`, wrapper/descendant identity, immutable consumption, runtime manifest, compiled source/stopping controls, event weights and detector response.

PR #1215 must remain draft until fresh push- and pull-request-triggered MC Validation on the final head after `198cd506...` and coordination commits both finish successfully. Any CI result attached only to superseded head `94c3ae9f5673f80bf1cb4339e3dd47866b39f80a` is non-authorising. Recheck base freshness against protected main immediately before ready/merge.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no detector-performance/public physics claim was regenerated or promoted.
