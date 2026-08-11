# Latest Handoff

## Active atom: current cwd observation versus historical exec-time cwd

Protected source of truth advanced to `main@c485d96583df91e90669e402670a3fa102643495` after #1213 was marked ready only once both exact-head `test` checks on `85894ad0123ee56dc18da6cc86e0340f9eabb312` were successful, then squash-merged with expected-head protection. The new work is on branch `audit/geant4-loader-cwd`. CL-021 remains gated.

### Selected scientific contract

`ARU-MC-G4-LOADER-INITIAL-CWD-001` addresses the relative-path dependency exposed by `geant4/setup_and_run.sh`:

`./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root`

For a relative pathname `p`, a useful local abstraction is `Resolved_t(p) = Resolve(CWD_t, Root_t, MountNS_t, p)`. This atom binds only `CWD_t` at one observation window. It does not yet bind the historical cwd at exec, process root, mount namespace, symlink chain, or exact bytes later consumed by HIBEAM.

The implemented `ccb_geant4_loader_cwd_attestation_v1` composes PASS/digest-valid runtime and argv receipts, requires the same `(pid,starttime_ticks,exe_link)`, observes `/proc/<pid>/cwd` twice, opens that cwd directory object twice and requires equal `(st_dev,st_ino,st_mode)`, then rechecks process starttime and executable link. The receipt means only `STABLE_CURRENT_WORKING_DIRECTORY_OBJECT_OBSERVATION_ONLY`.

### Discriminating evidence

The strongest counter-hypothesis was that because exec preserves cwd, a later procfs cwd can be treated as the launch/exec cwd. A real Linux child falsified that inference: it was launched with `cwd=initial`, executed Python, then called `chdir(later)`. The bounded attestor correctly observed `later`, not `initial`. Current cwd therefore cannot be promoted to immutable historical cwd without an exec-boundary proof.

Hostile tests also cover wrong parent receipts, PID/starttime mismatch, executable mismatch, cwd-link mutation, and opened-directory-object mutation.

### Exact implementation and validation

Branch commits:

- `475d0f886b0257b1cfd905e798254a07ec8a8dd8` — `tools/audit/geant4_loader_cwd_attestation.py`;
- `c0131e9cc7740303505554266b207fa42567bf70` — `tests/test_geant4_loader_cwd_attestation.py`;
- `7acb18fa686a2456093c61087491c2a7ec2a114d` — curated MC-validation ruff inclusion;
- `b8d66da03d194040d3bd44bc386aa83098841604` — immutable ARU record;
- `619fc7d0e192baa1142cc466ecd1c7091b117245` — active-task coordination.

Exact committed identities:

- tool: 10,190 bytes, SHA-256 `02ed0bb6cd4f53a7e72e59f0147e06eee72e7a7518c0d8de11aa62b856f5e1be`, Git blob `bb71a692732c3f6730b52704bd51ec9506cff7ac`;
- tests: 10,285 bytes, SHA-256 `5d77e26e8233d8693af19d93bbf4bff4b6fbe45a68f8f91d19e95ec6862ffa28`, Git blob `c1f9ffb43856aa17435e931194a94a1df68486c2`.

Local deterministic run, Python 3.13.5 / Linux 6.18.35 x86_64 / no RNG:

`python -m pytest -q tests/test_geant4_loader_cwd_attestation.py` -> `9 passed in 1.17 s`.

`python -m py_compile tools/audit/geant4_loader_cwd_attestation.py tests/test_geant4_loader_cwd_attestation.py` -> PASS.

Local ruff was unavailable. An install attempt failed because the package index could not be resolved, so no local ruff PASS is claimed; exact-head repository CI remains mandatory.

### Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT current-state primitive / BLOCK initial-cwd provenance.** The post-exec chdir control falsifies promotion of a later procfs observation to historical launch state. Real HIBEAM behavior remains unobserved.
- **Adversarial Linux/filesystem reviewer — ACCEPT fail-closed transition checks / BLOCK complete path resolution.** Stable cwd alone does not bind root, mount namespace, symlink resolution, or an ABA cwd transition.
- **Independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference.** Nine deterministic tests exercise software/OS provenance only; no Geant4 event or detector observable participates.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Cwd plus argv is still insufficient to bind the exact historical inputs consumed by a production run.

### Children and next gate

Material child leaves:

- `ARU-MC-G4-LOADER-INITIAL-CWD-EXEC-BOUNDARY-001` — prove cwd at the exec boundary rather than later current state;
- `ARU-MC-G4-LOADER-FS-NAMESPACE-001` — process root, mount namespace, relevant mount topology;
- `ARU-MC-G4-RELATIVE-INPUT-CONSUMPTION-001` — exact config/macro/support bytes actually opened/consumed;
- `ARU-MC-G4-OUTPUT-PATH-CREATION-001` — cwd/path state at output creation plus final output identity.

Open a draft PR for the current-cwd primitive, require fresh exact-final-head push and pull-request MC Validation, and require base freshness against current protected main. The next scientific atom after this bounded merge gate is the exec-boundary cwd leaf, followed by filesystem namespace and exact input-consumption closure.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no detector-performance or public physics claim was regenerated or promoted.
