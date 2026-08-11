# Latest Handoff

## Merged bounded cwd primitive; next atom is exec-boundary cwd #1214

Protected `main` is now `859903ada4a856c998b2bc79298cd4a26c2cb447`, the squash merge of #1215. The merged tree contains `ccb_geant4_loader_cwd_attestation_v1`, its hostile fixtures, curated MC Validation coverage, the parent ARU archive, and the validation-readiness continuation. The bounded current-cwd primitive is repository-validated; the broader initial-cwd universe remains **PARTIAL** because #1214 is unresolved. CL-021 remains gated.

### What #1215 established

The run front door uses:

`./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root`

For a relative path `p`, path resolution depends on more than argv; a useful dependency abstraction is `Resolved_t(p) = Resolve(CWD_t, Root_t, MountNS_t, p)`.

The merged cwd receipt verifies exact PASS/digests of runtime and argv predecessors, requires the same `(pid,starttime_ticks,exe_link)`, reads `/proc/<pid>/cwd` twice, independently opens that directory object twice and requires equal `(st_dev,st_ino,st_mode)`, then rechecks process identity. Its scientific scope is deliberately only `STABLE_CURRENT_WORKING_DIRECTORY_OBJECT_OBSERVATION_ONLY`.

A live negative control proves why that scope matters: a Python child launched with `cwd=initial` can call `chdir(later)` after exec, after which procfs and the attestor observe `later`. A later current cwd therefore cannot be promoted to historical launch/exec cwd simply because `execve` itself preserves cwd.

### Validation child that was found before merge

A later independent local rerun of the first published live fixture produced `1 failed, 8 passed in 11.92 s`. The child remained in its inherited cwd beyond a three-second polling deadline; that failure showed the fixture had not proved that user code reached `chdir`. It did not falsify the production attestor.

`ARU-MC-G4-LOADER-CWD-TEST-READY-001` repaired the test at commit `198cd5062982947d12410b9371d43ddaa596c4f0`: the child emits an absolute test-owned marker only after successful `chdir`, the parent waits for that state signal while requiring child liveness, and only then invokes the unchanged attestor. A longer fixed sleep was rejected as non-discriminating.

Local repaired evidence: Python 3.13.5 / Linux 6.18.35 x86_64 / no RNG; six consecutive focused runs each returned `9 passed` (1.01–1.14 s), and `py_compile` passed. Local ruff was unavailable.

Final exact PR head `5f251aa10aabaddfadcee7f7f9e77b021ce98998` then received two independent required `test` contexts:

- push-triggered MC Validation run `31489962787`: **success**; curated ruff, full unit tests, diagnostics upload and enforcement all succeeded;
- pull-request-triggered MC Validation run `31489967793`: **success**; the same stages all succeeded.

Base freshness immediately before merge was exact: base/merge-base `c485d96583df91e90669e402670a3fa102643495`, `behind_by=0`. #1215 was marked ready and squash-merged with expected-head protection to `main@859903ada4a856c998b2bc79298cd4a26c2cb447`.

Exact source identities retained on main:

- tool: 10,190 bytes, SHA-256 `02ed0bb6cd4f53a7e72e59f0147e06eee72e7a7518c0d8de11aa62b856f5e1be`, Git blob `bb71a692732c3f6730b52704bd51ec9506cff7ac`;
- repaired tests: 10,169 bytes, SHA-256 `a4e8b6e4cabc114034d8ade82103951c91f01d77998b898c604fdefde50446a1`, Git blob `aaf14ee43544fe388ef22692c9f2a5daab4f4ac1`.

### Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT bounded current-state primitive / BLOCK initial-cwd provenance.** Evidence: merged runtime+argv composition, synchronized live post-exec `chdir` falsifier, exact-head CI. Counter-hypothesis: later procfs cwd equals launch cwd. Falsified by the live transition. Residual: no real HIBEAM exec-boundary observation.
- **Adversarial Linux/filesystem reviewer — ACCEPT state-discriminating current-cwd evidence / BLOCK complete pathname resolution.** Evidence: two link/object observations and process identity rechecks. Counter-hypothesis: stable cwd is sufficient for relative input identity. Falsified by root/mount namespace/symlink dependencies and actual file-open timing. Residual: ABA cwd, namespaces, wrapper chain.
- **Independent validation reviewer — ACCEPT repository software oracle / BLOCK physics inference.** Evidence: one exposed fixture failure, explicit repair, six local repaired passes, two green exact-head full-CI contexts. Counter-hypothesis: fixture closure validates HIBEAM. Rejected because no Geant4 event, detector response, weights or beam data participate.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Evidence: current CL-021 validation document remains explicitly GATED; exec-time cwd, exact input consumption and other runtime/physics children remain open.

### Next highest-value atom: #1214

Issue #1214 is `ARU-MC-G4-LOADER-INITIAL-CWD-EXEC-BOUNDARY-001`. It must bind the cwd directory object at the actual exec transition, not a later current state. Candidate mechanisms are a minimal direct-exec launcher that opens/records `.` immediately before exec, a kernel tracing mechanism that captures cwd at exec, or an equivalently strong process-identifiable proof.

Required discriminators include: wrapper `chdir` before final exec, target `chdir` and `fchdir` after exec, PID/starttime reuse, executable/dynamic-loader mismatch, directory rename/unlink, and namespace/root mismatch. A parent-shell cwd, fixed delay, or delayed `/proc/<pid>/cwd` observation is non-authorising.

After #1214, continue with `ARU-MC-G4-LOADER-FS-NAMESPACE-001`, `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001`, and `ARU-MC-G4-OUTPUT-PATH-CREATION-001`. The broader loader cache/config, token/hwcaps, preload/audit, linker/static-input, late-`dlopen`, wrapper/descendant, immutable-consumption, runtime-manifest, compiled source/stopping, event-weight and detector-response children also remain.

No production HIBEAM/Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no B2/B8, PID, timing, calibration, pile-up, ESS, p-value, rate, angular distribution or detector-performance result was regenerated or promoted.
