# Latest Handoff

## First-local-peak CFD selector is an explicit, non-authorising hypothesis

Selected atom: `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001`, child of #1059/#1063. Microscopic interpretation remains under #968/#1009/#1010.

### Live repository state

The clean branch `audit/cfd-selector-identifiability-v1` was created from exact protected `main@75b80839042a367e54743401cc2d11cfab6d4c3b`; the branch-protection contract requires `test`. Draft PR #1274 contains the new selector-identifiability work and, because current main still lacks it, the already-reviewed component-bound CFD crossing dependency from draft #1259.

#1259 remains open/draft/unmerged. Its exact head `458506cff29daa9fb8a80a7656ebd73bff180b53` did eventually receive successful pull-request and push MC Validation runs, but those checks cannot authorize #1274 because #1274 has a different base and additional code/tests.

### Atomic selector contract

For waveform `y`, let `A_g=max(y)` and default `alpha=0.05`. The existing first-local selector is exactly:

- interior `j` is eligible if `y[j]>=y[j-1]`, `y[j]>=y[j+1]`, and `y[j]>=alpha*A_g`;
- choose the smallest eligible `j`;
- if no eligible interior sample exists, fall back to `argmax(y)`.

This is frozen as hypothesis profile `first_local_peak_global_fraction_floor_v1`, state `HYPOTHESIS_UNVALIDATED_COMPONENT_IDENTITY`, with `authorising_component_identity=false`. The historical parameter name `min_prominence_frac` is retained for API compatibility but is now documented as a misnomer: no topographic-prominence calculation is performed.

For candidate amplitude `A_j`, the floor margin is

`m_j=A_j-alpha*A_g`.

With global-max identity fixed and bounded perturbations `|delta_j|<=eps_j`, `|delta_g|<=eps_g`, a sufficient floor-stability condition is

`|m_j| > eps_j + alpha*eps_g`.

This does not close local-maximum identity: neighbour-order margins are separate, and plateaus have zero uniqueness margin under the existing `>=` rule. A global-max switch changes the floor itself and is another child assumption.

### Deterministic discriminators

1. `[0,50,51,50,0,0,500,1000,500]`: `A_g=1000`, so the floor is 50. A peak only 1 ADC above both neighbours is selected at sample 2. Therefore the rule is a global-height filter, not a prominence/basin filter.
2. Early peak `49.9` versus `50.1` ADC with the same late 1000-ADC maximum: only 0.2 ADC moves the selected component from late sample 7 to early sample 2 by crossing the exact 5% floor.
3. `[0,50,100,100,100,50,0]`: samples 2,3,4 all meet the `>=` local-max condition, so the earliest is an implementation tie-break rather than a unique physical peak; diagnostics expose the multiplicity/plateau.
4. `[0,10,20,30,40]`: no eligible interior maximum exists, so the selector silently becomes global-max unless fallback state is serialized.
5. Clean unimodal pulses remain the negative control in which first-local and global component definitions coincide.

The branch also retains the #1259 same-component CFD contract: with selected peak `(p,A_p)` and threshold `T=f*A_p`, the crossing uses the nearest pre-peak bracket `y[k]<T<=y[k+1]`, `k+1<=p`; rejected earlier activity cannot supply the selected component's time. The explicit `global_max` estimator keeps historical whole-waveform first-crossing semantics.

### Mechanism collapse

Noise, a true earlier particle/pile-up pulse, delayed SiPM activity, electronics/recovery structure, saturation and overlap can all change the selector output. They are observationally equivalent at this atom. A selector transition is evidence of estimator instability, not evidence for a particular microscopic cause.

### Repository actions and provenance

- Created branch from exact protected main.
- Code commit `5cf030d2e50e326903f76b077a7234fbc31ba8a0`; pre-coordination source blob `197ab80571823f6aa13ede1a20b1efc1d9c07b53`.
- Implementation/test head `2d8740501d2e3227506458813a6007173310ba0c` adds ten deterministic controls.
- Opened draft PR #1274, `fix(timing): expose first-local selector identifiability limits`.
- Added stable concern `CCB-1059-PEAK-SELECTOR-IDENTIFIABILITY-001` to existing #1059; no duplicate issue was opened.
- Archived the full atom at `chatgpt_todo/archive/2026-08-12T003900Z_ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001.md` in commit `6dc182bb280979b9ca62637f0f3c235caeeef2e4`.
- A local sparse-clone attempt failed before checkout because the execution container could not resolve `github.com`; therefore there is no local pytest PASS claim.
- PR-triggered MC Validation run `31550836290` was first observed queued on pre-coordination head `2d874...`. These coordination commits create a new final head, so fresh exact-head protected CI is required before readiness/merge.

### External documentation boundary

SciPy's authoritative `peak_prominences` documentation defines prominence by a peak's vertical distance to its lowest contour line/bases; `find_peaks` separately documents local maxima and flat peaks. Those sources justify the terminology correction only. They do not validate a CCB detector component or any choice of `alpha`.

### Four sequential AI votes

**Timing / sampled-signal lead — ACCEPT explicit selector profile and diagnostics / BLOCK detector-truth validation.** The algorithm is now specified exactly, but actual CCB noise, saturation, overlap and component truth are unmeasured here.

**Adversarial waveform / mechanism reviewer — REVISE any robustness or prominence interpretation / BLOCK authorising component identity.** Floor-boundary, plateau and fallback fixtures remain valid counterexamples; microscopic causes are intentionally not inferred.

**Independent statistics / validation reviewer — ACCEPT deterministic identifiability diagnosis / BLOCK timing-resolution inference.** The fixtures establish discontinuous decision surfaces but do not measure real-data misassignment, timing bias or coverage and do not select a validated alternative.

**Claims / provenance reviewer — ACCEPT bounded fail-closed selector state / KEEP #1059 OPEN.** `real_data_cfd_timing.py` can operate in authorising mode and defaults to first-local selection, so selector identity must remain explicit and non-authorising until real-data/truth-transfer children close. The known legacy real-data CFD report remains FLAWED/QUARANTINED.

### Children / next work

Highest-value next child if immutable beam bytes are available: `ARU-TIMING-CFD-REALDATA-TRANSITION-001`. Serialize selector diagnostics in the producer and measure selected/fallback/plateau transitions by run, stave, amplitude and topology with run-aware uncertainty.

If beam bytes are unavailable, next strongest fixture-level child: `ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001`, with controlled baseline/noise/sampling-phase/clipping perturbations and stability margins.

Other surviving children: `ARU-TIMING-CFD-OVERLAP-BASIN-001`, `ARU-TIMING-CFD-TRUTH-TRANSFER-001`, and downstream regeneration/audit of reports, figures and claim rows consuming `first_local_peak` after the estimator changes.

No beam timing resolution, pile-up rate/mechanism, WLS response, PID metric, efficiency, rate, ESS, p-value or detector-performance quantity was regenerated or promoted.