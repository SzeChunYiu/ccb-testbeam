# ARU-SIPM-CORE-MERGE-CONFLICT-CLOSURE-001

Status: **ACTIVE / REPAIR PR OPEN / CI PENDING**

## Selected atom

A repository-integrity atom at the boundary between `ccb-testbeam` and its live upstream dependency `SzeChunYiu/ccb-sipm-core`: can a merged upstream commit be treated as an executable/provenance-valid simulator state when tracked C++ sources still contain literal unresolved Git conflict delimiters?

### Parent / dependencies

- Root electronics provenance parent: #1067 (`ARU-ELEC-IMPULSE-FAILCLOSED-001`).
- Root recovery parent: #1066 (`ARU-SIPM-RECOVERY-LAW-001`) and correlated-noise child #1071.
- Governance child spawned here: upstream `ccb-sipm-core` issue #17 (`ARU-CORE-MAIN-PROTECTION-001`).
- Root `ccb-testbeam` main inspected at `5a020b61cbdea6cfda0aeba7a1f6d92442a369e9`.
- Upstream core main inspected at `0fc78af6679c421f7a01a85f421170bbb92cce82`, parent `cf12c6b8955c48590bda858477f8dc4ebd67251b`.

## Exact input/output contract

**Input state:** exact tracked Git blobs in the upstream simulator tree, together with their merge provenance and CI state.

**Required output state:** a deterministic C++17 source tree in which:

1. no compiled source/test/config file contains unresolved merge delimiters;
2. the fail-closed measured-impulse semantics already validated on the pre-#15 lineage are preserved;
3. arbitrary sampled impulse vectors are not promoted to authoritative `MEASURED` electronics provenance without source/calibration authorization;
4. the effective-kernel digest refers to the exact history-complete runtime kernel consumed by waveform convolution;
5. the exact candidate head passes Core CI configure/build/CTest before it is eligible for merge.

No physical units enter the merge-marker predicate. Electronics quantities retained by the preserved implementation use ns for time, PE for avalanche/waveform amplitude, and the existing canonical digest schema for runtime-kernel identity.

Scientific meaning: this atom is a prerequisite for treating the upstream simulator as an executable scientific dependency. It does **not** establish a detector response or calibration.

## Observed contradiction

Merged upstream PR #15 produced `ccb-sipm-core/main@0fc78af...` while literal conflict markers remained in:

- `src/Config.cc`;
- `src/ResponseSimulator.cc`;
- `tests/test_core.cc`.

PR #15's own automated review had explicitly warned that unresolved merge conflicts remained and that the incoming side conflicted with the existing `CUSTOM_UNVALIDATED` / canonical effective-kernel provenance contract.

The broken `src/Config.cc` also duplicates `max_abs` and trapezoidal-integral accumulation in the measured-impulse loop and contains mutually exclusive support definitions (history-complete runtime grid versus output-window-only grid). `src/ResponseSimulator.cc` contains mutually exclusive `run_metadata()` implementations: the preserved side fails closed to `CUSTOM_UNVALIDATED` and hashes the exact cached history-complete kernel, while the incoming side advertises `MEASURED` and creates non-cryptographic `LEN-*` placeholders. `tests/test_core.cc` contains mutually exclusive expected states.

## Equations / invariants

For the measured impulse source `(t_i,a_i)`, the already-preserved fail-closed checks include

`max_i |a_i| > 0`

and positive trapezoidal charge under the current declared polarity convention,

`Q_trap = Σ_i 0.5 (a_i + a_{i-1})(t_i-t_{i-1}) > 0`.

Runtime support is history-complete:

`N_kernel = N_output + ceil(max(0, window_start-history_start)/dt)`.

A supplied impulse must overlap that exact relative-time grid. The conflict-side output-window-only support would be a semantic regression for pre-window avalanche tails.

Provenance authorization invariant:

`authoritative_MEASURED => source_identity ∧ source_content_digest ∧ calibration/resampling_validation ∧ exact_effective_runtime_kernel_identity`.

A vector being finite/nondegenerate is necessary numerical validity, not sufficient calibration authority.

Repository merge invariant:

`MERGE(h) => conflict_marker_scan(h)=PASS ∧ CoreCI(h)=SUCCESS`.

## Competing repair mechanisms

### H1 — leave merged main unchanged

Eliminated. Literal `<<<<<<<`, `=======`, and `>>>>>>>` tokens in compiled `.cc` files violate the source contract and are expected to stop compilation/preprocessing.

### H2 — resolve in favor of PR #15 incoming side

Rejected. The incoming side duplicates the integral calculation in `Config.cc`, changes history-complete support to the shorter output-only grid, advertises arbitrary sampled vectors as `MEASURED`, and emits `LEN-*` pseudo-hashes. Those changes regress already-established provenance and history-support contracts.

### H3 — restore the pre-#15 blobs for only the three contaminated files

Survives. The immediate parent `cf12c6b...` already contains the substantive fail-closed behavior claimed by #15: >=2 matched samples, finite values, strict time ordering, nonzero peak, positive integral, history-complete support overlap, explicit ideal-delta authorization, hard failure for degenerate kernels, `CUSTOM_UNVALIDATED` measured-vector provenance, and canonical exact runtime-kernel hashing.

### H4 — revert the entire #15 merge

Observationally equivalent to H3 for the contaminated executable semantics but unnecessarily discards unrelated/comment-only changes. Collapsed into H3 as the smaller bounded repair.

## Solve-first implementation executed

Created upstream branch `audit/repair-main-conflict-markers` from exact broken `0fc78af6679c421f7a01a85f421170bbb92cce82`.

Constructed a tree replacing exactly three files with their immediately-preceding verified blobs:

- `src/Config.cc` -> `7e4d84ec684d3b11eb3a7e1c6012fe22edfb53ba`;
- `src/ResponseSimulator.cc` -> `51d5e74863d8075235fa27d4ad93f19c9a7565a7`;
- `tests/test_core.cc` -> `3df1ea0d20bf93fbd10245791fb216ba1581f7ec`.

New tree: `23beb8a7e1df3fc5d2bebc1e1c21e54c29d4ae2d`.

Repair commit: `98be281d3b48d4fe2fc2e00f985ec62374f07766`, message `fix(core): restore conflict-free impulse implementation after #15`.

Opened draft upstream PR #16, `fix(core): remove unresolved conflict markers from main after #15`, exact base `0fc78af...`, exact head `98be281d...`, exactly three changed files. No force-push was used.

Core CI run `31544391525` was triggered on exact head `98be281d...`; at the last inspection its `build-test` job `93953654545` remained **queued**, so no CI PASS and no merge are claimed.

The post-merge Core CI for broken main `0fc78af...`, run `31544089787`, was likewise queued at inspection. Because core main is currently unprotected, that CI had not been a precondition for the bad merge.

## Root-integration impact

The protected root repository has **not** yet integrated the broken upstream main. Its current SiPM gitlink lineage remains on the earlier conflict-free `cf12c6b...` family rather than `0fc78af...`. Therefore this run identifies an upstream-main integrity incident and future-pinning hazard, not evidence that existing root-main detector outputs were produced from the conflict-marked commit.

Do not update the root gitlink to `0fc78af...`. Any future advance must use a conflict-free exact core commit with successful Core CI and then pass root protected integration CI.

## Child issue / preventive control

Searched upstream open issues and found no existing branch-protection/conflict-marker leaf. Opened `ccb-sipm-core` issue #17, stable ID `ARU-CORE-MAIN-PROTECTION-001`, requiring:

- exact-head Core CI before merge;
- deterministic conflict-marker scanning with narrow fixture exceptions;
- live branch/ruleset protection verification;
- regression use of #15 as the historical failure witness and #16 as repair control.

## Cross-atom governance repair

Root #1066 was found `closed/completed` even though its own acceptance checkboxes and the latest existing issue-thread correction explicitly require OPEN/PARTIAL state. Reopened #1066 and added a completion-state repair comment. This state repair does not modify the integrated trigger/gain selector code and does not produce new SiPM calibration evidence.

Root #1067 remains open/reopened. PR #15's title/merge message cannot close #1067 because source/calibration promotion, resampling closure, and historical measured-output audit remain material acceptance leaves.

## Four sequential AI reviews

### 1. Build/reproducibility lead — C++17, CMake, dependency integration

**Evidence inspected:** core main/parent trees, current source blobs, PR #15 warning, CI workflow, repair tree/commit/PR.

**Strongest counter-hypothesis:** conflict markers might be harmless comments or unreachable text.

**Attempted falsifier:** inspected exact marker locations in compiled `.cc` and test source; markers are raw source delimiters, not comments or fixture strings.

**Residual uncertainty:** exact repair-head compiler/CTest execution is still queued.

**Vote:** `ACCEPT targeted repair / BLOCK merge until exact-head Core CI succeeds`.

### 2. Adversarial mechanism/provenance reviewer — state machines, serialization, fault injection

**Evidence inspected:** both sides of the merge conflicts, parent semantics, provenance/digest paths.

**Strongest counter-hypothesis:** resolving in favor of PR #15 preserves useful new fail-closed behavior lost by restoring the parent.

**Attempted falsifier:** compared parent implementation. The parent already has the substantive degeneracy/support/ideal-delta checks; incoming code instead introduces duplicate integration, narrower support and weaker provenance labels.

**Residual uncertainty:** none for the three-file semantic choice; future calibration promotion remains separate.

**Vote:** `REJECT incoming conflict side / ACCEPT exact parent-blob restoration`.

### 3. Independent validation/statistics reviewer — reproducible testing and negative controls

**Evidence inspected:** exact SHAs/blobs, CMake test inventory, CI trigger contract, queued exact-head run.

**Strongest counter-hypothesis:** repository inspection alone proves the repair complete.

**Attempted falsifier:** completion requires actual configure/build/CTest on `98be281d...`; that execution has not completed.

**Residual uncertainty:** compiler/toolchain outcome until CI runs; no stochastic or detector estimator participates.

**Vote:** `ACCEPT deterministic source diagnosis / BLOCK VALIDATED until Core CI / BLOCK detector inference`.

### 4. Claims/provenance reviewer — calibration authority and public-claim governance

**Evidence inspected:** #1067 acceptance contract, upstream provenance conflict, root gitlink separation, #1066 closure contradiction.

**Strongest counter-hypothesis:** a merged PR named `fixes #1067` authorizes measured-electronics provenance.

**Attempted falsifier:** live #1067 remains open and requires exact source/effective digests, calibration/resampling validation and historical audit. Root does not even pin the bad upstream commit.

**Residual uncertainty:** future measured impulse source/calibration object and historical output inventory.

**Vote:** `ACCEPT quarantine/repair / BLOCK #1067 COMPLETE and measured-electronics claim promotion`.

## Claim/wiki consequences

No public detector claim is promoted. Any documentation or ledger entry that equates upstream PR #15 merge with validated measured-electronics response must remain gated. #1066 is OPEN/PARTIAL again. #1067 stays OPEN.

## Blockers

1. Core PR #16 exact-head CI run `31544391525` is queued; do not merge before successful configure/build/CTest.
2. Upstream core main lacks branch protection/required checks; issue #17 tracks preventive closure.
3. Physical electronics source/calibration authorization under root #1067 remains unresolved.

## Next highest-value atom

First, finish this atom only if PR #16 exact-head Core CI succeeds, then merge with an expected-head guard and verify the resulting core-main push CI. After upstream integrity is restored, return to `ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`: expose prompt/delayed/afterpulse parent-generation recovery semantics as named serializable hypotheses, preserve raw-`r` as legacy, add discriminating controls, and do not select detector truth without two-pulse calibration.

## Scientific boundary

No beam bytes, production Geant4 population, SiPM two-pulse calibration, measured front-end impulse, detector waveform closure, pile-up/saturation efficiency, timing/PID metric, event weight, ESS, p-value, rate, or detector-performance result was generated or promoted in this atom.
