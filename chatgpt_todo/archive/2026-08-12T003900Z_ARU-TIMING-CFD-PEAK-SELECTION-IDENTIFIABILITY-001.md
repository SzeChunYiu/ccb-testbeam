# ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001

Status: `PARTIAL` — software selector law/diagnostics are specified and deterministic counterexamples exist; physical component identity is not validated.  
Parents: #1059 / #1063.  
Microscopic mechanism boundary: #968 (reopened physics-BLOCKED), #1009, #1010.  
Integration PR: #1274 (`audit/cfd-selector-identifiability-v1`).  
Branch base at creation: protected `main@75b80839042a367e54743401cc2d11cfab6d4c3b`.  

## Exact contract

Input is a sampled waveform `y[0..N-1]` after the separately governed baseline/polarity stages. Amplitudes are in the producer's ADC-like analysis units; the selector outputs an integer sample index and amplitude, not a physical-particle identity. Downstream CFD converts interpolated sample coordinates using the separately declared sample period.

For the current first-local selector:

- `A_g = max_i y[i]`;
- default `alpha = 0.05`, with #1274 rejecting nonfinite or out-of-domain values outside `[0,1]`;
- interior `j` is eligible iff `y[j]>=y[j-1]`, `y[j]>=y[j+1]`, and `y[j]>=alpha*A_g`;
- choose the smallest eligible `j`;
- if no eligible interior sample exists, choose `argmax(y)` and mark an explicit fallback.

The branch names this exact reduced model `first_local_peak_global_fraction_floor_v1`, state `HYPOTHESIS_UNVALIDATED_COMPONENT_IDENTITY`, with `authorising_component_identity=false`. The legacy keyword `min_prominence_frac` remains for API compatibility but is explicitly documented as a misnomer: the implementation does not calculate topographic prominence.

The component-bound CFD dependency carried from #1259 is

`T=f*A*`, `y[k]<T<=y[k+1]`, `k+1<=j*`,

where `j*`/`A*` are the selected component. The nearest pre-peak rising bracket supplies the time. Earlier rejected activity cannot supply the selected component's crossing. Explicit `global_max` mode keeps historical whole-waveform first-crossing semantics.

## Equations / identifiability conditions

For candidate amplitude `A_j`, define

`m_j = A_j - alpha*A_g`.

Assuming global-maximum identity is unchanged and bounded perturbations satisfy `|delta_j|<=eps_j`, `|delta_g|<=eps_g`, a sufficient condition that the amplitude-floor decision cannot flip is

`|m_j| > eps_j + alpha*eps_g`.

This closes only the global-floor decision. Local-maximum identity also depends on neighbour-order margins

`d_L=A_j-y[j-1]`, `d_R=A_j-y[j+1]`.

A plateau has zero uniqueness margin under the current `>=` rule. A change in global-max identity changes `A_g` and the floor itself, so the bound above no longer suffices.

Limiting cases:

- isolated strictly unimodal interior pulse: first-local and global selectors coincide;
- `alpha -> 0`: early local maxima are admitted increasingly easily;
- increasing `alpha`: early candidates disappear discontinuously at `A_j=alpha*A_g`;
- no eligible interior peak: algorithm collapses to global-max unless fallback state is recorded;
- plateau: multiple samples can satisfy the local-max rule and the earliest sample is an implementation tie-break.

## Competing microscopic descriptions

H1 intended prompt component; H2 noise/electronic excursion; H3 true earlier particle/pile-up component; H4 delayed/correlated SiPM or recovery activity; H5 electronics shaping/retrigger/baseline structure; H6 saturation/clipping changing `A_g`; H7 overlap/sampling phase changing discrete peak ordering; H8 boundary/monotonic fallback.

H2–H7 are observationally indistinguishable from selector output alone. They are collapsed at this atom rather than counted as independent evidence for pile-up or another mechanism.

## Deterministic falsifiers and controls

No RNG is used.

### F1 — corrected global-height-versus-prominence discriminator

Waveform: `[0,50,51,50,50,500,1000,500]`.

`A_g=1000`, so the selector floor is 50 ADC and the 51-ADC early peak is admitted. For that early peak, the left basin minimum is 0 and the right basin minimum before the first higher sample is 50. The higher base is therefore 50 and topographic prominence is

`51 - max(0,50) = 1 ADC`,

far below the 50-ADC selector floor. Thus the implemented rule is not a 5%-of-global prominence threshold.

**Preserved adversarial correction.** The first draft used `[0,50,51,50,0,0,500,1000,500]` and incorrectly called its prominence 1 ADC. That was wrong: the right basin reaches zero, so the topographic prominence is 51 ADC. The adversarial review caught this before integration. Test, PR body, stable concern and handoff were corrected. This revision is retained explicitly as provenance.

### F2 — selector identity discontinuity at the global floor

Pair:

- `[0,25,49.9,25,0,0,500,1000,500]`;
- `[0,25,50.1,25,0,0,500,1000,500]`.

The global maximum stays 1000 and the floor stays 50. A 0.2-ADC perturbation changes the selected index from late sample 7 to early sample 2. Selected/global amplitude ratio changes from 1.0 to 0.0501.

### F3 — plateau non-uniqueness

`[0,50,100,100,100,50,0]` gives eligible samples 2,3,4 under `>=`; the earliest is chosen. Diagnostics record multiplicity and plateau membership.

### F4 — silent fallback family

`[0,10,20,30,40]` has no eligible interior local maximum and therefore falls back to boundary global sample 4. #1274 records `FALLBACK_GLOBAL_NO_ELIGIBLE_INTERIOR`.

### F5 — parameter-domain negative controls

`alpha<0`, `alpha>1`, NaN and infinity are rejected. `alpha=0` and `alpha=1` remain explicit limiting cases.

### F6/F7 — dependent component-bound crossing controls

`[0,40,0,50,100,50,0,0,500,1000,500]`: the rejected 40-ADC bump must not supply the time for the selected 100-ADC peak. CFD20 gives `t=2.4` samples rather than whole-waveform `0.5`.

`[30,0,50,100,50,0,250,500,250]`: sample 0 is above the selected component threshold but the trace drops below before the selected rise; component-relative crossing is observed at `t=1.4` samples rather than globally left-censored.

Clean unimodal `[0,50,100,50,0]` is the negative control where global/component-bound timing coincide.

## Repository implementation / exact provenance

- `5cf030d2e50e326903f76b077a7234fbc31ba8a0`: introduced selector profile/state and diagnostics plus component-bound crossing dependency.
- `a0d8910986292fdfbf614fb830ea75e13b5a38ae`: fail-closed selector fraction domain `[0,1]`.
- `ee070d6bce20b327a5b830b6d01166e0266e8ace`: corrected the prominence discriminator and retained explicit mathematical check in the focused regression.
- #1274 changes only `scripts/digital_cfd.py`, `tests/test_cfd_component_binding.py`, this archive, `ACTIVE_TASK.md`, and `HANDOFF.md`.
- Stable concern `CCB-1059-PEAK-SELECTOR-IDENTIFIABILITY-001` was updated rather than opening a duplicate #1059 child issue.

A local sparse-clone attempt

`git clone --depth 1 --filter=blob:none --sparse --branch audit/cfd-selector-identifiability-v1 https://github.com/SzeChunYiu/ccb-testbeam.git /tmp/ccb_audit`

failed before checkout because the execution container could not resolve `github.com`; therefore there is **no local checkout/pytest PASS claim**. GitHub Actions on the exact final branch head is the repository execution authority.

Every branch write changes the head. Earlier queued/green #1274 runs and #1259's green runs are not merge authorization for a later head. Both duplicate final-head required `test` contexts must be successful before readiness/merge.

## External authoritative documentation / source-to-claim map

SciPy `scipy.signal.peak_prominences` defines prominence by vertical distance to the peak's lowest contour line / bases. `scipy.signal.find_peaks` separately defines local maxima and flat-peak handling. These sources support the terminology/mathematical distinction only. They do not validate a CCB physical component or any value of `alpha`.

- SciPy API: `scipy.signal.peak_prominences`, https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.peak_prominences.html
- SciPy API: `scipy.signal.find_peaks`, https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.find_peaks.html

## Cross-atom governance finding: #968

Live review found #968 closed as `completed` with a campaign-ledger note. Merged PR #1239, however, explicitly lists **#968 B2 broad-residual mechanism discrimination** under `BLOCKED / out of scope for this code PR (need dedicated studies / data)`. The current issue campaign ledger marks Lane05 merged but does not provide a Lane05 per-issue physics disposition satisfying #968's acceptance criteria. #968 was therefore reopened as physics-BLOCKED. This does not revert or invalidate #1239's bounded timing software fixes.

## Four sequential AI review passes

### A. Timing / sampled-signal lead

Background: digital CFD, sampled waveform timing, censoring and component assignment.

Evidence: current-main selector, #1059 contract, authorising producer default, #1259 component-bound code, #1274 diagnostics/tests.

Strongest counter-hypothesis: 5%-of-global first-local selection is sufficiently stable to represent a prompt component even if the parameter name is imprecise.

Falsifier: corrected F1 plus F2 show that low-prominence absolute-height candidates can pass and component identity can flip at a small perturbation around the global-floor boundary.

Residual: actual CCB noise/baseline/sampling/saturation support and truth identity are unmeasured here.

Vote: **ACCEPT explicit selector profile/diagnostics / BLOCK detector-truth selector validation.**

### B. Adversarial waveform / mechanism reviewer

Background: pile-up, overlapping pulses, SiPM correlated noise/recovery, shaping, saturation and DAQ artifacts.

Evidence: selector equations, SciPy prominence definition, F1–F5, #968/#1009/#1010 context.

Strongest counter-hypothesis: synthetic pathologies are irrelevant to physical waveform support.

Attempted falsifier: first review actually **rejected the first F1 derivation** because the alleged 1-ADC prominence was mathematically wrong. A corrected fixture was then constructed and independently checked against the prominence definition. Boundary/plateau/fallback controls remain mechanism-neutral.

Residual: occurrence rates in immutable beam data and microscopic cause are unknown.

Vote: **REVISE first draft; ACCEPT corrected selector-law falsifier / BLOCK physical component authorization.**

### C. Independent statistics / validation reviewer

Background: estimator identifiability, robustness margins, held-out validation and injection recovery.

Evidence: margin derivation, deterministic controls, branch tests, authorising producer path, quarantined legacy report.

Strongest counter-hypothesis: deterministic closure justifies choosing this selector as canonical.

Falsifier: fixtures demonstrate instability but do not estimate real-data misassignment, timing bias, uncertainty coverage or compare validated alternatives.

Residual: run/stave transition matrix, nuisance scans and truth-labelled injections absent.

Vote: **ACCEPT software/identifiability diagnosis / BLOCK timing-resolution inference.**

### D. Claims / provenance reviewer

Background: code→selection→estimator→artifact→report→claim traceability.

Evidence: #1059, `real_data_cfd_timing.py`, quarantined `reports/real_data_cfd_timing/REPORT.md`, timing chapter/report inventory, #1239/#968 governance, #1259/#1274 provenance.

Strongest counter-hypothesis: existing report quarantine makes selector-state governance immaterial.

Falsifier: the producer defaults to `first_local_peak` and can operate in authorising mode, so future artifacts can inherit an unvalidated component label unless this state remains explicit; #968 closure also showed that merged infrastructure can be mistaken for physics completion.

Residual: downstream consumer inventory/regeneration unfinished.

Vote: **ACCEPT bounded fail-closed selector state / KEEP #1059 and #968 OPEN; timing claims gated.**

## Cross-scale propagation

Micro: discrete eligibility/order/fallback decisions have explicit non-identifiable boundaries.  
Waveform: noise, overlap, saturation, baseline and sampling phase can move selected component without identifying a microscopic mechanism.  
Event/study: CFD time is conditional on selected component; fraction scans and timing widths require component-assignment stability evidence.  
Claim: legacy real-data CFD report remains FLAWED/QUARANTINED; no detector timing resolution or pile-up mechanism is promoted.

## Child atoms / dependencies

- `ARU-TIMING-CFD-REALDATA-TRANSITION-001`: serialize selector diagnostics and measure selected/fallback/plateau transitions by run, stave, amplitude and topology on immutable beam data with run-aware uncertainty.
- `ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001`: controlled baseline/noise/sampling-phase/clipping/amplitude perturbation scan.
- `ARU-TIMING-CFD-OVERLAP-BASIN-001`: behavior when overlapping components lack a below-threshold separator.
- `ARU-TIMING-CFD-TRUTH-TRANSFER-001`: held-out digitized MC/injection with known component identity and misassignment/bias metrics.
- downstream regeneration/audit of reports, figures and claim rows consuming `first_local_peak`.
- #968 physical B2 mechanism discrimination remains independently BLOCKED/open.

## Acceptance boundary

Software-contract VALIDATED requires exact final-head protected CI and successful integration retaining diagnostics/tests. That does **not** validate the physical prompt-component selector. Physical authorization requires real-data/truth-transfer children and cross-scale compatibility.

Do not close #1059 from same-sample narrow residuals alone. Do not label selector transitions as pile-up or another mechanism without independent discriminants. Do not inherit historical timing numbers across the algorithm change without regeneration and provenance.
