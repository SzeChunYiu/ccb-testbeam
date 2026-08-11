# Latest Handoff

## Upstream SiPM core main contains unresolved merge markers; bounded repair is open

Selected atom: `ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001`.

### Live state

Protected root `ccb-testbeam/main` was inspected at exact `5a020b61cbdea6cfda0aeba7a1f6d92442a369e9`; required status context remains `test`. The root's SiPM gitlink lineage remains on the earlier conflict-free `cf12c6b...` core family, so the upstream incident described below has **not** yet contaminated the root runtime dependency.

Live `ccb-sipm-core/main` is `0fc78af6679c421f7a01a85f421170bbb92cce82`, the merge of core PR #15. That commit is not a valid executable source state: exact reads of `src/Config.cc`, `src/ResponseSimulator.cc`, and `tests/test_core.cc` show literal unresolved `<<<<<<<`, `=======`, and `>>>>>>>` merge delimiters. PR #15's own automated review had explicitly warned that those conflicts remained before merge.

### Atomic contract and mechanism result

For a calibrated sampled impulse `(t_i,a_i)`, the preserved parent implementation requires a nonzero norm and positive trapezoidal integral under the current polarity convention,

`max |a_i| > 0`,

`Q = Σ 0.5(a_i+a_{i-1})(t_i-t_{i-1}) > 0`,

plus overlap with the history-complete runtime grid

`N_kernel = N_output + ceil(max(0, window_start-history_start)/dt)`.

The conflict-side implementation is not merely a textual alternative. It duplicates the integral accumulation in `Config.cc`, shortens measured-impulse support validation to the output window, and conflicts with the already-reviewed provenance state: one side keeps arbitrary sampled vectors `CUSTOM_UNVALIDATED` and hashes the exact cached history-complete runtime kernel, while the incoming side labels them `MEASURED` and manufactures `LEN-*` placeholders.

The strongest repair candidates were compared. Keeping broken main is impossible. Favoring the incoming side is rejected as a semantic/provenance regression. Reverting all of PR #15 is unnecessarily broad. The surviving bounded repair is to restore only the three contaminated executable/test blobs from immediate parent `cf12c6b8955c48590bda858477f8dc4ebd67251b`, because that parent already contains the substantive fail-closed measured-impulse behavior claimed by #15.

### Work performed

Upstream branch `audit/repair-main-conflict-markers` was created from exact bad main. A three-file tree was constructed with:

- `src/Config.cc` -> `7e4d84ec684d3b11eb3a7e1c6012fe22edfb53ba`;
- `src/ResponseSimulator.cc` -> `51d5e74863d8075235fa27d4ad93f19c9a7565a7`;
- `tests/test_core.cc` -> `3df1ea0d20bf93fbd10245791fb216ba1581f7ec`.

Tree: `23beb8a7e1df3fc5d2bebc1e1c21e54c29d4ae2d`.
Repair commit: `98be281d3b48d4fe2fc2e00f985ec62374f07766`.

Draft upstream PR #16, `fix(core): remove unresolved conflict markers from main after #15`, has exact base `0fc78af...`, exact head `98be281d...`, and exactly three changed files. Core CI run `31544391525`, job `93953654545`, was still queued at last inspection. Do **not** mark it ready or merge until exact-head configure/build/CTest succeeds.

The post-merge Core CI run for broken main, `31544089787`, was also only queued when inspected. Core main is currently unprotected; a bad merge therefore became main without successful CI being a precondition.

### Preventive child and issue governance

No duplicate upstream branch-protection issue existed. Opened core issue #17, stable ID `ARU-CORE-MAIN-PROTECTION-001`, requiring exact-head Core CI plus a deterministic conflict-marker scanner and verified branch/ruleset protection. PR #15 is the historical failure fixture; PR #16 is the immediate repair control.

Root #1066 was found incorrectly `closed/completed` despite its own unresolved acceptance criteria and an existing issue-thread correction saying to keep it OPEN/PARTIAL. It was reopened and a completion-state repair comment was added. The integrated trigger/gain selector refactor is unchanged; two-pulse calibration, correlated-noise coupling, operating-point/source provenance and high-occupancy model-form uncertainty remain open.

Root #1067 remains OPEN/reopened. A PR title saying `fixes #1067` cannot establish its scientific acceptance: source/calibration authorization, resampling closure and historical measured-output audit remain unresolved.

### Four sequential AI review votes

**Build/reproducibility lead — ACCEPT targeted repair / BLOCK merge until exact-head Core CI succeeds.** Raw conflict delimiters occur in compiled/test source, not comments or dedicated fixtures.

**Adversarial mechanism/provenance reviewer — REJECT incoming conflict side / ACCEPT parent-blob restoration.** Immediate parent already contains the desired fail-closed numerical checks; incoming conflict text weakens history support and provenance semantics.

**Independent validation reviewer — ACCEPT deterministic source diagnosis / BLOCK VALIDATED until Core CI / BLOCK detector inference.** The exact repair has not yet compiled in CI; repository inspection is not a substitute for executable closure.

**Claims/provenance reviewer — ACCEPT quarantine/repair / BLOCK #1067 COMPLETE and measured-electronics promotion.** Root has not integrated the bad core SHA, and no calibration object or detector data participates here.

### Next work

Immediate: recheck Core CI run `31544391525`. If and only if it succeeds on exact `98be281d...`, mark #16 ready and merge with an expected-head guard; then require the resulting core-main push CI and record the final upstream main SHA. Do not point root to `0fc78af...`.

Once upstream integrity is restored, the next highest-value scientific atom remains `ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`: make prompt/delayed/afterpulse parent-generation recovery semantics explicit and serializable, preserve raw-`r` as a named legacy hypothesis, add discriminating alternatives/controls, and do not choose detector truth without source-bound two-pulse calibration.

Immutable record: `chatgpt_todo/archive/2026-08-11T225800Z_ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001.md`.

No beam data, production Geant4 population, measured electronics impulse, SiPM two-pulse calibration, waveform closure, pile-up/saturation efficiency, timing/PID metric, event weights, ESS, p-value, rate, or detector-performance result was generated or promoted.
