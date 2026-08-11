# Latest Handoff

## Upstream SiPM core conflict-marker repair validated; branch-protection child remains open

Selected atom: `ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001`.

### Final live state

Protected root `ccb-testbeam/main` was inspected at exact `5a020b61cbdea6cfda0aeba7a1f6d92442a369e9`; required status context remains `test`. The root SiPM gitlink lineage remained on the earlier conflict-free `cf12c6b...` core family throughout this atom, so the broken upstream main commit was not integrated into root main.

Upstream `ccb-sipm-core/main@0fc78af6679c421f7a01a85f421170bbb92cce82` had literal unresolved Git conflict markers after merged core PR #15 in `src/Config.cc`, `src/ResponseSimulator.cc`, and `tests/test_core.cc`. PR #15's own automated review had warned of those conflicts before merge.

The bounded repair restored only the three contaminated files to their immediate-parent blobs while preserving the already-present fail-closed measured-impulse checks, history-complete runtime-kernel support, `CUSTOM_UNVALIDATED` provenance state, and canonical exact effective-kernel digest path.

### Exact execution and integration

Repair head: `98be281d3b48d4fe2fc2e00f985ec62374f07766`.
Repair tree: `23beb8a7e1df3fc5d2bebc1e1c21e54c29d4ae2d`.
Restored blobs: `Config.cc@7e4d84ec...`, `ResponseSimulator.cc@51d5e748...`, `test_core.cc@3df1ea0d...`.

Core PR #16 exact-head Core CI run `31544391525`, job `93953654545`, completed **SUCCESS**: checkout, configure, build and Test/CTest all succeeded. PR #16 was marked ready only after that result and squash-merged with expected-head guard.

Current remote upstream core main is exact

`caf6bdc592a05b55ae6bc343b4532a9934eb8344`

with the same repair tree `23beb8a7...`.

Independent post-merge main-push Core CI run `31544689778`, job `93954555539`, also completed **SUCCESS** with checkout, configure, build and Test/CTest all successful. The bounded upstream build/provenance repair is therefore validated and present on remote core main.

### Mechanism / invariant result

For a sampled measured impulse `(t_i,a_i)`, preserved fail-closed numerical validity requires ordered finite samples, `max |a_i| > 0`, positive trapezoidal integral under the current sign convention, and overlap with the history-complete runtime kernel grid

`N_kernel = N_output + ceil(max(0, window_start-history_start)/dt)`.

Those checks are necessary numerical validity only; authoritative measured-electronics provenance still requires source identity/content digest, calibration/resampling validation and exact effective-runtime-kernel identity.

The rejected PR #15 conflict side was not equivalent to the preserved implementation: it duplicated the measured-impulse integral calculation, shortened support to output-window-only, advertised arbitrary sampled vectors as `MEASURED`, and generated non-cryptographic `LEN-*` placeholders. Since the immediate parent already contained the substantive fail-closed behavior, exact three-file parent restoration was the smallest scientifically safe repair.

### Preventive child and issue governance

Upstream core #17 (`ARU-CORE-MAIN-PROTECTION-001`) remains OPEN. Core main is still unprotected; the child requires exact-head Core CI, deterministic conflict-marker scanning with narrow fixture exceptions, and live branch/ruleset enforcement. The current incident is repaired, but the mechanism that permitted it has not yet been removed.

Root #1066 was reopened after being found incorrectly `closed/completed` despite unresolved acceptance criteria and an existing thread correction requiring OPEN/PARTIAL. No recovery-calibration evidence changed.

Root #1067 remains OPEN/reopened and now has an incident/quarantine comment recording the exact core repair and CI boundary. Core PR #15's `fixes #1067` wording is not scientific-completion evidence; source/calibration authorization, resampling closure and historical measured-output audit remain unresolved.

### Four sequential AI review votes

**Build/reproducibility lead — ACCEPT bounded repair VALIDATED.** Exact repair head and exact merged core main both configured, built and passed CTest.

**Adversarial mechanism/provenance reviewer — ACCEPT parent-blob resolution / REJECT PR #15 incoming conflict side.** Parent already contained the desired fail-closed checks; incoming conflict content weakened history/provenance semantics and duplicated numerical work.

**Independent validation reviewer — ACCEPT software execution closure / BLOCK detector inference.** Build/test closure says nothing about real detector calibration, rates or response fidelity.

**Claims/provenance reviewer — ACCEPT upstream quarantine repair / BLOCK #1067 COMPLETE and measured-electronics promotion.** Root never pinned the broken core SHA and no source-bound measured impulse calibration was authorized.

### Next work

Next highest-value scientific atom: `ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`. Make prompt/delayed/afterpulse parent-generation recovery semantics explicit and serializable, preserve raw-`r` as a named legacy hypothesis, add discriminating gain-coupled/unsuppressed controls where appropriate, and do not select detector truth without source-bound two-pulse delay×amplitude calibration.

Governance child #17 proceeds independently and must not be marked complete until protection/ruleset enforcement is installed and exercised against the PR #15 regression witness.

Archives:
- `chatgpt_todo/archive/2026-08-11T225800Z_ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001.md` (checkpoint);
- `chatgpt_todo/archive/2026-08-11T230100Z_ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001_EXECUTION.md` (final execution state).

No beam data, production Geant4 population, measured electronics impulse, SiPM two-pulse calibration, waveform closure, pile-up/saturation efficiency, timing/PID metric, event weights, ESS, p-value, rate, or detector-performance result was generated or promoted.
