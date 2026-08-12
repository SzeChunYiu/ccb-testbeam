# Latest Handoff

## First-local-peak CFD selector is explicit but not physically identified

Selected atom: `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001`, child of #1059/#1063. Microscopic mechanism interpretation remains separate; #968 has been reopened as physics-BLOCKED after live provenance review.

### Live repository state

The clean branch `audit/cfd-selector-identifiability-v1` was created from exact protected `main@75b80839042a367e54743401cc2d11cfab6d4c3b`; the branch-protection contract requires `test`. Draft PR #1274 contains the selector-identifiability work and, because current main lacked it at branch creation, the already-reviewed component-bound CFD crossing dependency from draft #1259.

#1259 remains draft/unmerged. Its exact head `458506cff29daa9fb8a80a7656ebd73bff180b53` had successful pull-request and push MC Validation, but those checks cannot authorize #1274 because #1274 has a different base and additional code/tests.

### Atomic selector contract

For waveform `y`, let `A_g=max(y)` and default `alpha=0.05`. The existing first-local selector is exactly:

- interior `j` is eligible if `y[j]>=y[j-1]`, `y[j]>=y[j+1]`, and `y[j]>=alpha*A_g`;
- choose the smallest eligible `j`;
- if no eligible interior sample exists, fall back to `argmax(y)`.

#1274 freezes this as hypothesis profile `first_local_peak_global_fraction_floor_v1`, state `HYPOTHESIS_UNVALIDATED_COMPONENT_IDENTITY`, with `authorising_component_identity=false`. The legacy parameter name `min_prominence_frac` is retained only for compatibility; the computation is a global-amplitude floor, not topographic prominence. Nonfinite or out-of-domain `alpha` outside `[0,1]` now fails closed.

For candidate amplitude `A_j`, the floor margin is `m_j=A_j-alpha*A_g`. With global-max identity fixed and bounded perturbations `|delta_j|<=eps_j`, `|delta_g|<=eps_g`, a sufficient floor-stability condition is `|m_j| > eps_j + alpha*eps_g`. Neighbour-ordering margins are separate, and plateaus have zero uniqueness margin under the existing `>=` rule. A global-max switch changes the floor itself.

### Corrected deterministic discriminators

1. **Prominence/floor separation:** `[0,50,51,50,50,500,1000,500]`. `A_g=1000`, so the selector floor is 50 ADC and the early 51-ADC peak is admitted. Its left basin minimum is 0 and its right basin minimum before the first higher sample is 50; the higher base is 50, so topographic prominence is `51-max(0,50)=1` ADC. This separates the implemented global-height rule from a prominence threshold.
2. **Floor discontinuity:** otherwise identical traces with early peaks 49.9 and 50.1 ADC and the same 1000-ADC late peak move selected index from late sample 7 to early sample 2 under only a 0.2-ADC perturbation.
3. **Plateau non-uniqueness:** `[0,50,100,100,100,50,0]` gives three eligible samples; choosing the first is an implementation tie-break rather than a unique physical peak.
4. **Fallback:** `[0,10,20,30,40]` has no eligible interior local maximum and therefore collapses to the boundary global maximum; diagnostics expose the fallback.
5. **Parameter domain:** `alpha<0`, `alpha>1`, NaN and infinity are rejected.
6. **Negative control:** a clean unimodal pulse makes first-local and global component definitions coincide.

**Preserved adversarial correction:** the first draft used `[0,50,51,50,0,0,500,1000,500]` and incorrectly called the early peak's prominence 1 ADC. Because the right basin reaches zero, its topographic prominence is actually 51 ADC. The adversarial review caught this before merge. The test, PR body, stable concern and handoff now use the corrected fixture above. The disagreement/correction is part of the provenance rather than being averaged away.

The branch also retains the #1259 same-component CFD contract: with selected peak `(p,A_p)` and threshold `T=f*A_p`, the crossing uses the nearest pre-peak bracket `y[k]<T<=y[k+1]`, `k+1<=p`; rejected earlier activity cannot supply the selected component's time. The explicit `global_max` estimator keeps historical whole-waveform first-crossing semantics.

### Mechanism collapse

Noise, a true earlier particle/pile-up pulse, delayed SiPM activity, electronics/recovery structure, saturation and overlap can all change selector output. They are observationally equivalent at this atom. A selector transition is evidence of estimator instability, not evidence for a particular microscopic cause.

### Cross-atom governance correction

Issue #968 had been closed as `completed` with a campaign-ledger note, but merged PR #1239 explicitly lists **#968 B2 broad-residual mechanism discrimination** under `BLOCKED / out of scope for this code PR (need dedicated studies / data)`. The campaign ledger marks Lane05 merged but does not provide a Lane05 per-issue physics disposition satisfying #968's acceptance criteria. #968 was therefore reopened as physics-BLOCKED. The reopening does not revert or dispute #1239's bounded software fixes.

### Repository actions and provenance

- Branch base: protected `main@75b80839042a367e54743401cc2d11cfab6d4c3b`.
- Code-profile commit `5cf030d2e50e326903f76b077a7234fbc31ba8a0`.
- Parameter-domain commit `a0d8910986292fdfbf614fb830ea75e13b5a38ae`.
- Corrected prominence-test commit `ee070d6bce20b327a5b830b6d01166e0266e8ace`.
- Draft PR #1274: `fix(timing): expose first-local selector identifiability limits`.
- Stable concern `CCB-1059-PEAK-SELECTOR-IDENTIFIABILITY-001` updated with the corrected prominence derivation and explicit adversarial `REVISE` history.
- #968 reopened with evidence that its physics mechanism study remains unresolved.
- Archive: `chatgpt_todo/archive/2026-08-12T003900Z_ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001.md`; correct before integration and treat its first-draft error as superseded by the explicit correction.
- A local sparse-clone attempt failed before checkout because the execution container could not resolve `github.com`; therefore there is no local pytest PASS claim.
- Every branch write changes the exact head. Merge only after both final-head push and pull-request `test` contexts succeed; do not inherit earlier green runs.

### External documentation boundary

SciPy's authoritative `peak_prominences` documentation defines prominence by vertical distance to the lowest contour line / bases; `find_peaks` separately documents local maxima and flat-peak behavior. Those sources justify the terminology correction only. They do not validate a CCB detector component or any `alpha` value.

### Four sequential AI votes

**Timing / sampled-signal lead — ACCEPT explicit selector profile and diagnostics / BLOCK detector-truth validation.** Algorithmic state is now explicit; actual CCB noise, saturation, overlap and component truth are unmeasured here.

**Adversarial waveform / mechanism reviewer — REVISE first falsifier; after correction ACCEPT the floor-vs-prominence distinction / BLOCK authorising component identity.** The first prominence example was mathematically wrong and was corrected before merge. Boundary, plateau and fallback counterexamples remain.

**Independent statistics / validation reviewer — ACCEPT deterministic identifiability diagnosis / BLOCK timing-resolution inference.** Fixtures establish decision-surface discontinuities but do not measure real-data misassignment, timing bias or coverage and do not choose a validated alternative.

**Claims / provenance reviewer — ACCEPT bounded fail-closed selector state / KEEP #1059 and #968 OPEN.** The real-data producer defaults to first-local selection and can operate in authorising mode, while physical component identity and B2 mechanism discrimination remain unresolved. The known legacy real-data CFD report remains FLAWED/QUARANTINED.

### Children / next work

Highest-value next child if immutable beam bytes are available: `ARU-TIMING-CFD-REALDATA-TRANSITION-001`. Serialize selector diagnostics in the producer and measure selected/fallback/plateau transitions by run, stave, amplitude and topology with run-aware uncertainty.

If beam bytes are unavailable, next strongest fixture child: `ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001`, with controlled baseline/noise/sampling-phase/clipping perturbations and stability margins.

Other surviving children: `ARU-TIMING-CFD-OVERLAP-BASIN-001`, `ARU-TIMING-CFD-TRUTH-TRANSFER-001`, and downstream regeneration/audit of reports, figures and claim rows consuming `first_local_peak` after the estimator changes.

No beam timing resolution, pile-up rate/mechanism, WLS response, PID metric, efficiency, rate, ESS, p-value or detector-performance quantity was regenerated or promoted.