# Latest Handoff

## Upstream SiPM core conflict-marker repair merged; post-merge CI still pending

Selected atom: `ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001`.

### Live state

Protected root `ccb-testbeam/main` was inspected at exact `5a020b61cbdea6cfda0aeba7a1f6d92442a369e9`; required status context remains `test`. The root SiPM gitlink lineage remains on the earlier conflict-free `cf12c6b...` core family, so the bad upstream commit was not integrated into root main.

Upstream `ccb-sipm-core/main@0fc78af6679c421f7a01a85f421170bbb92cce82` was confirmed to contain literal unresolved Git conflict markers after merged core PR #15 in `src/Config.cc`, `src/ResponseSimulator.cc`, and `tests/test_core.cc`. PR #15's own automated review had warned of the unresolved conflicts before merge.

A bounded three-file repair was implemented on exact head `98be281d3b48d4fe2fc2e00f985ec62374f07766`, restoring the immediate-parent blobs while retaining the already-existing fail-closed measured-impulse semantics, history-complete runtime-kernel support, `CUSTOM_UNVALIDATED` provenance state, and canonical exact effective-kernel hashing.

### Validation and integration

Core CI run `31544391525`, job `93953654545`, completed successfully on exact repair head `98be281d...`; checkout, configure, build and Test/CTest steps all succeeded. Only after that exact-head result was PR #16 marked ready.

PR #16 was squash-merged with expected-head guard as new upstream core main

`caf6bdc592a05b55ae6bc343b4532a9934eb8344`

with exact tree `23beb8a7e1df3fc5d2bebc1e1c21e54c29d4ae2d`.

Independent main-push Core CI run `31544689778` was **queued** at last inspection. Therefore the pre-merge repair head has executable closure, the repair is present on remote core main, but a post-merge-main PASS is not yet claimed.

### Atomic contract and mechanism result

For a sampled measured impulse `(t_i,a_i)`, the preserved implementation requires finite ordered samples, `max |a_i| > 0`, positive trapezoidal integral under the current polarity convention, and support overlap with the history-complete kernel grid

`N_kernel = N_output + ceil(max(0, window_start-history_start)/dt)`.

The rejected PR #15 conflict side was not equivalent: it duplicated measured-impulse integral accumulation, shortened support validation to output-window-only, advertised arbitrary sampled vectors as `MEASURED`, and created non-cryptographic `LEN-*` placeholders. Since the immediate parent already contained the substantive degeneracy/support/ideal-delta checks, the smallest scientifically safe repair was exact restoration of only the three contaminated executable/test files.

### Preventive child and issue governance

Opened upstream core issue #17, stable ID `ARU-CORE-MAIN-PROTECTION-001`, because core main remains unprotected. It requires exact-head Core CI, deterministic conflict-marker scanning with narrow fixture exceptions, and live branch/ruleset verification. PR #15 is the historical failure witness; PR #16 is the repair control.

Root #1066 was found `closed/completed` despite its own unresolved acceptance criteria and an existing thread correction saying to keep it OPEN/PARTIAL. It was reopened and a completion-state repair comment was added. No recovery calibration result changed.

Root #1067 remains OPEN/reopened. Added an incident/quarantine comment recording core #16 and the exact CI boundary. The wording `fixes #1067` on upstream PR #15 is not scientific-completion evidence; source/calibration authorization, resampling closure and historical measured-output audit remain open.

### Four sequential AI review votes

**Build/reproducibility lead — ACCEPT repair-head executable closure / REVISE until post-merge Core CI.** Exact candidate configured, built and passed CTest before merge; independent main-push run remains pending.

**Adversarial mechanism/provenance reviewer — REJECT incoming conflict side / ACCEPT parent-blob restoration.** Immediate parent already had the desired fail-closed checks; incoming conflict content weakened support/provenance semantics and duplicated numerical work.

**Independent validation reviewer — ACCEPT exact-head Core CI / BLOCK detector inference.** This validates software repair behavior only; no detector data or stochastic calibration participates.

**Claims/provenance reviewer — ACCEPT quarantine/repair / BLOCK #1067 COMPLETE and measured-electronics promotion.** Root never pinned the broken core SHA, and no measured impulse calibration object has been authorized.

### Next work

First recheck Core CI run `31544689778` on exact remote main `caf6bdc...`. If successful, record post-merge closure in an execution addendum and keep upstream #17 open until branch/ruleset protection is actually installed and tested.

Then return to the next scientific atom `ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`: expose prompt/delayed/afterpulse parent-generation recovery semantics as named, serializable hypotheses; preserve raw-`r` as legacy; add discriminating controls; and do not choose detector truth without source-bound two-pulse calibration.

Archive checkpoint: `chatgpt_todo/archive/2026-08-11T225800Z_ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001.md`.

No beam data, production Geant4 population, measured electronics impulse, SiPM two-pulse calibration, waveform closure, pile-up/saturation efficiency, timing/PID metric, event weights, ESS, p-value, rate, or detector-performance result was generated or promoted.
