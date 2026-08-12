# ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001

Status: PARTIAL — deterministic selector semantics and falsifiers implemented; detector-component identity remains unvalidated.  
Parent: #1059 / #1063.  
Microscopic mechanism dependencies: #968, #1009, #1010.  
Integration PR: #1274 (`audit/cfd-selector-identifiability-v1`).  
Branch base at creation: protected `main@75b80839042a367e54743401cc2d11cfab6d4c3b`.  
Pre-coordination implementation head: `2d8740501d2e3227506458813a6007173310ba0c`.  
Pre-coordination source blob: `scripts/digital_cfd.py@197ab80571823f6aa13ede1a20b1efc1d9c07b53`.  

## 1. Exact atomic contract

Input is a baseline/polarity-corrected sampled waveform `y[0..N-1]` in ADC-like amplitude units. The selector has no intrinsic time unit; indices are integer sample positions. Downstream CFD converts the interpolated sample coordinate through the separately declared sample period.

For the existing first-local-peak rule define

- `A_g = max_i y[i]`;
- default global fraction `alpha = 0.05`;
- interior candidate `j` is eligible when
  `y[j] >= y[j-1]`, `y[j] >= y[j+1]`, and `y[j] >= alpha*A_g`;
- `j*` is the smallest eligible index;
- if no eligible interior sample exists, `j* = argmax_i y[i]`.

The selected output is `(j*, A*=y[j*])` plus diagnostic state. It is a discrete algorithmic component label, not a detector-truth particle/pulse identity.

The branch freezes this exact reduced model as `first_local_peak_global_fraction_floor_v1`, state `HYPOTHESIS_UNVALIDATED_COMPONENT_IDENTITY`, with `authorising_component_identity=false`. The historical argument name `min_prominence_frac` is retained for compatibility but documented as a misnomer: the implementation applies a global-amplitude floor and does not compute topographic prominence.

The dependent component-bound CFD contract inherited from #1259 is

`T = f*A*`, with the returned crossing formed from the nearest pre-peak rising bracket `y[k] < T <= y[k+1]`, `k+1 <= j*`. Earlier rejected activity may not supply the selected component's time. The explicit `global_max` estimator retains whole-waveform first-crossing semantics.

## 2. Competing mechanisms/descriptions

H1 — intended prompt component: the earliest eligible local maximum corresponds to the intended prompt detector pulse.  
H2 — electronic/noise excursion: an early excursion crosses the global-height floor and becomes the selector output.  
H3 — true earlier particle/pile-up component: an earlier physical pulse is selected.  
H4 — delayed/correlated SiPM response or recovery structure changes the global maximum or creates an earlier eligible maximum.  
H5 — electronics shaping/retrigger/baseline structure changes local-maximum ordering.  
H6 — saturation/clipping changes `A_g`, therefore moving the global fraction floor and eligibility boundary.  
H7 — overlap/sampling phase makes the discrete local maximum or its ordering non-unique.  
H8 — boundary/monotonic waveform: no eligible interior maximum exists and the rule collapses to global-max selection.

H2–H7 are observationally indistinguishable from selector output alone. They are collapsed at this atom instead of being counted as independent evidence for pile-up or any other microscopic cause.

## 3. Equations, invariants, limiting cases and identifiability

For candidate amplitude `A_j`, define the global-floor margin

`m_j = A_j - alpha*A_g`.

Assuming global-maximum identity is unchanged and bounded perturbations satisfy `|delta_j| <= eps_j` and `|delta_g| <= eps_g`, a sufficient condition that the floor side cannot flip is

`|m_j| > eps_j + alpha*eps_g`.

This is only the amplitude-floor part of identifiability. The discrete local-maximum conditions separately require neighbour-ordering margins. Define

`d_L = A_j - y[j-1]`, `d_R = A_j - y[j+1]`.

A plateau has `d_L=0` and/or `d_R=0`, so the current `>=` rule has zero uniqueness margin there. If global-max identity changes, `A_g` and the floor itself can change discontinuously and the sufficient bound above no longer closes the selector.

Limiting cases:

- clean, isolated, strictly unimodal interior pulse: first-local and global selectors coincide and component-bound/global CFD are observationally equivalent;
- `alpha -> 0`: essentially every nonnegative interior local maximum becomes eligible, maximizing early-noise sensitivity;
- increasing `alpha`: earlier components disappear discontinuously when their amplitude falls below `alpha*A_g`;
- no eligible interior maximum: selector silently becomes `global_max` unless fallback state is serialized;
- plateau: multiple adjacent samples satisfy the local-maximum rule and the earliest index is an implementation tie-break, not a unique physical peak.

## 4. Deterministic discriminating experiments

No RNG is required.

### F1 — global-height floor is not topographic prominence

Waveform: `[0,50,51,50,0,0,500,1000,500]`.

`A_g=1000`, so `alpha*A_g=50`. The early local maximum is only 1 ADC above each neighbour but is eligible because `51>=50`. The selector therefore chooses sample 2. This falsifies the interpretation that `min_prominence_frac=0.05` imposes a 5%-of-global topographic prominence requirement.

### F2 — arbitrarily local decision boundary

Pair:

- `[0,25,49.9,25,0,0,500,1000,500]`;
- `[0,25,50.1,25,0,0,500,1000,500]`.

The global maximum remains 1000 and the floor remains 50. A 0.2-ADC perturbation moves the early local maximum across the exact threshold. The selected index changes from the late 1000-ADC peak at sample 7 to the early 50.1-ADC peak at sample 2. The selected/global amplitude ratio moves from 1.0 to 0.0501.

### F3 — plateau non-uniqueness

Waveform: `[0,50,100,100,100,50,0]`.

Under `>=`, samples 2,3,4 all satisfy the local-maximum inequalities. The current rule chooses sample 2 only because it is first. The diagnostic records multiplicity 3 and plateau membership.

### F4 — silent fallback family

Waveform: `[0,10,20,30,40]`.

There is no eligible interior local maximum, so the rule selects boundary global peak sample 4. The branch records `FALLBACK_GLOBAL_NO_ELIGIBLE_INTERIOR` explicitly.

### F5 — parent same-component crossing discriminator

`[0,40,0,50,100,50,0,0,500,1000,500]`: the 40-ADC bump is below the 50-ADC selector floor, so the selected peak is 100 at sample 4. At CFD20, the selected threshold is 20 and the component-bound bracket 2→3 gives `t=2.4` samples; whole-waveform first crossing would give `0.5` from the rejected bump.

### F6 — component-relative censoring

`[30,0,50,100,50,0,250,500,250]`: sample 0 is above the selected 100-ADC peak's CFD20 threshold, but the trace returns below it before the selected rise. The selected crossing is observed at `t=1.4` samples rather than being globally left-censored.

Negative control: a clean unimodal `[0,50,100,50,0]` gives the same component-bound and global CFD crossing.

## 5. Implementation executed

Branch created from exact protected base `75b80839042a367e54743401cc2d11cfab6d4c3b`.

Implementation commit `5cf030d2e50e326903f76b077a7234fbc31ba8a0` updated `scripts/digital_cfd.py` and produced blob `197ab80571823f6aa13ede1a20b1efc1d9c07b53`. It adds selector profile/state constants and `first_local_peak_diagnostics()` exposing:

- selected/global amplitudes and sample indices;
- global fraction floor;
- eligible-local-maximum multiplicity;
- selected/global amplitude ratio;
- plateau membership;
- fallback/selection status;
- explicit non-authorising component-identity state.

Implementation/test head `2d8740501d2e3227506458813a6007173310ba0c` adds `tests/test_cfd_component_binding.py` with ten deterministic controls: five component-bound crossing regressions plus five selector-identifiability/parameter controls.

A local sparse-clone execution attempt was made with

`git clone --depth 1 --filter=blob:none --sparse --branch audit/cfd-selector-identifiability-v1 https://github.com/SzeChunYiu/ccb-testbeam.git /tmp/ccb_audit`

and failed before checkout because the execution container could not resolve `github.com`. Therefore this record makes **no local pytest PASS claim**. The final-head GitHub Actions result is the execution authority for this branch.

Draft PR #1274 was opened from the exact base. The first observed PR-triggered MC Validation run on pre-coordination head `2d874...` was `31550836290` and was queued at the time this archive was written. Any subsequent coordination commit changes the head and requires fresh exact-head CI; earlier green heads are not merge authorization.

## 6. External authoritative documentation / source-to-claim map

Authoritative SciPy documentation `scipy.signal.peak_prominences` defines peak prominence from the peak to its lowest contour line / bases. `scipy.signal.find_peaks` separately documents local maxima and flat-peak behavior. These sources support only the terminology distinction that the repository's global-height floor is not a topographic-prominence computation. They do not select a CCB detector-truth component or justify any value of `alpha`.

Sources inspected:

- SciPy API reference, `scipy.signal.peak_prominences`, https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.peak_prominences.html
- SciPy API reference, `scipy.signal.find_peaks`, https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.find_peaks.html

## 7. Four sequential AI review passes

### A. Timing / sampled-signal lead

Background: digital CFD, sampled waveform timing, censoring, pulse-component assignment.

Evidence inspected: current protected-main `digital_cfd.py`, #1059 contract, authorising producer defaults, #1259 component-binding implementation and green predecessor CI, new deterministic selector fixtures.

Strongest counter-hypothesis: a 5%-of-global first-local rule is a sufficiently stable prompt-component selector even if not formally a prominence estimator.

Attempted falsifier: F1/F2 show a low-relief bump can pass and a 0.2-ADC perturbation can change selected component at an exact decision boundary.

Residual uncertainty: actual CCB noise/baseline/sampling/saturation distributions and detector-truth component identity were not measured in this atom.

Vote: **ACCEPT explicit selector profile and diagnostics / BLOCK detector-truth selector validation.**

### B. Adversarial waveform / microscopic-mechanism reviewer

Background: pile-up, overlapping pulses, SiPM correlated noise/recovery, shaping, saturation and DAQ artifacts.

Evidence inspected: local-maximum inequalities, fallback, plateau and boundary fixtures; #968/#1009/#1010 mechanism context.

Strongest counter-hypothesis: the synthetic pathologies are numerically possible but irrelevant to the physical support of real CCB waveforms.

Attempted falsifier: plateau/fallback and floor-boundary fixtures isolate algorithmic discontinuities without assuming any microscopic cause. They prove the support must be measured rather than presumed absent.

Residual uncertainty: incidence of these regimes in immutable beam data is unknown; overlap without a below-threshold basin remains an independent child.

Vote: **REVISE any robustness/prominence interpretation / BLOCK authorising component identity.**

### C. Independent statistics / validation reviewer

Background: estimator identifiability, robustness margins, held-out validation and injection recovery.

Evidence inspected: margin equations, deterministic negative controls, authorising producer path, quarantined legacy report.

Strongest counter-hypothesis: deterministic software closure is enough to choose the first-local selector as the canonical timing estimator.

Attempted falsifier: the fixtures identify instability but do not compare misassignment, timing bias or coverage against held-out detector truth. A validated alternative is not produced.

Residual uncertainty: real-data transition matrix, bounded nuisance scans, run clustering and truth-labelled digitized injections are absent.

Vote: **ACCEPT software/identifiability diagnosis / BLOCK timing-resolution inference.**

### D. Claims / provenance reviewer

Background: code→selection→estimator→artifact→report→claim traceability.

Evidence inspected: #1059 acceptance criteria; `real_data_cfd_timing.py` defaults to first-local mode; quarantined `reports/real_data_cfd_timing/REPORT.md`; timing chapter/report inventory; #1259/#1274 branch provenance.

Strongest counter-hypothesis: because the known real-data CFD report is already quarantined, selector-state provenance has no material claim consequence.

Attempted falsifier: the current producer still exposes authorising mode and defaults to `first_local_peak`; future reruns could therefore emit timing artifacts without an explicit selector-identifiability state unless this contract is retained.

Residual uncertainty: complete downstream consumer/report inventory and regeneration remain unfinished.

Vote: **ACCEPT bounded fail-closed selector state / KEEP #1059 OPEN and timing claims gated.**

## 8. Cross-scale propagation

Micro: selection is a discrete threshold/order operation with explicit non-identifiability near floor, neighbour-order and global-max boundaries.

Meso/waveform: selected component can change under noise, overlap, saturation, baseline and sampling phase; microscopic cause is not identified here.

Event/study: CFD time is conditional on this discrete selection. A fraction scan or timing-width study cannot be interpreted as one stable physical estimator unless component assignment is shown stable on the study population.

Claim: the legacy real-data CFD report remains FLAWED/QUARANTINED. No detector timing resolution, pile-up rate/mechanism, WLS response, PID metric, efficiency or public performance claim is promoted.

## 9. Child atoms spawned / surviving dependencies

- `ARU-TIMING-CFD-REALDATA-TRANSITION-001`: serialize selector diagnostics and measure component/fallback/plateau transitions by run, stave, amplitude and topology on immutable beam data, with run-aware uncertainty.
- `ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001`: bounded nuisance/injected-fault scan over noise, baseline, sampling phase, clipping and amplitude scale.
- `ARU-TIMING-CFD-OVERLAP-BASIN-001`: define behavior when overlapping components have no below-threshold separator before the selected peak.
- `ARU-TIMING-CFD-TRUTH-TRANSFER-001`: held-out digitized MC/injection study with known component identity and misassignment/bias metrics.
- downstream regeneration/audit of every report/figure/claim consuming `first_local_peak` after component-bound and selector-state changes.

## 10. Acceptance / rejection boundary

This atom can become VALIDATED at software/estimator-contract level only after exact final-head CI passes and the branch is integrated without losing the diagnostics. It cannot validate the physical prompt-component selector without independent real-data/truth-transfer children.

Do not close #1059 by choosing the fraction/selector with the narrowest same-sample residual width. Do not use selector transitions alone to label pile-up or another microscopic mechanism. Do not inherit historical timing numbers across the algorithm change without regeneration and provenance.
