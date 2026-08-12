# ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001

Status: `PARTIAL` — deterministic selector-sensitivity laws and fixtures implemented; exact-head repository CI and physical CCB nuisance support remain separate gates.  
Parents: #1059 / #1063.  
Dependency: `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001` / PR #1274.  
Microscopic mechanism boundary: #968, #1009, #1010.  

## Exact atom contract

Input is a finite sampled waveform `y[0..N-1]` after separately governed baseline and polarity operations. Amplitudes are in the producer's ADC-like analysis units. The parent selector uses global floor fraction `alpha=0.05` by default, selects the earliest interior sample satisfying local-maximum inequalities and `y[j] >= alpha*max(y)`, and otherwise falls back to `argmax(y)`.

This atom asks only whether that **software-selected sample index** is invariant under explicitly defined nuisance transformations. Output is selector state plus deterministic sufficient robustness bounds. It does not output a particle identity, noise probability, saturation probability, or timing resolution.

## L-infinity additive-perturbation certificate

For an accepted candidate `j`, global maximum `A_g`, floor `F=alpha*A_g`, define

- floor margin `m_F = y[j]-F`;
- neighbour margins `m_L=y[j]-y[j-1]`, `m_R=y[j]-y[j+1]`.

For arbitrary additive perturbation `delta` satisfying `||delta||_inf < eps`, `max(y)` is 1-Lipschitz in L-infinity norm. Therefore the accepted candidate remains above the global floor when

`eps < m_F/(1+alpha)`,

and its local-maximum inequalities remain true when

`eps < m_L/2`, `eps < m_R/2`.

Every earlier interior candidate `k<j` must also remain ineligible. For each currently failed predicate, sufficient persistence radii are

- floor failure: `(F-y[k])/(1+alpha)` when `y[k]<F`;
- left-order failure: `(y[k-1]-y[k])/2` when `y[k]<y[k-1]`;
- right-order failure: `(y[k+1]-y[k])/2` when `y[k]<y[k+1]`.

Keeping any one failed predicate false is enough to keep `k` ineligible, so its strongest certificate is the maximum of its applicable failure radii. The earlier-exclusion certificate is the minimum over all earlier candidates. The final exact-selected-index sufficient radius is the minimum of selected-floor, neighbour-order, and earlier-exclusion radii. The guarantee is strict (`eps < rho`), sufficient rather than necessary, and is explicitly non-authorising for physical component identity.

For fallback-to-global states, the certificate combines persistence of ineligibility for every interior candidate with half the unique argmax gap. Ties and selected plateaus naturally yield zero exact-index radius.

## Competing mechanisms / transformations

H1 bounded independent additive sample perturbation; H2 residual common-mode baseline offset; H3 clipping/saturation of a dominant later component; H4 sub-sample acquisition phase; H5 true earlier particle/pile-up; H6 SiPM delayed/correlated activity; H7 electronics shaping/recovery; H8 DAQ corruption or baseline error.

H5-H8 are not distinguishable from selector output in this atom. H1-H4 are controlled mathematical transformations used to test estimator stability, not claims that those mechanisms occur with any measured frequency in CCB data.

## Deterministic discriminators

No RNG is used.

### F1 — exact near-floor L-infinity boundary

`[0,25,49.9,25,0,0,500,1000,500]`, `alpha=0.05` selects the late sample 7. The early local maximum is 0.1 ADC below the 50-ADC floor. Apply the adversarial perturbation `+eps` to the early peak and `-eps` to the global peak. Eligibility flips when

`49.9 + eps = 0.05*(1000-eps)`,

so

`eps* = 0.1/1.05 = 0.09523809523809524 ADC`.

The implemented sufficient certificate returns the same boundary; a perturbation at `0.999*eps*` retains the late selector while `1.001*eps*` retargets the early component.

### F2 — residual common-mode baseline is not selector-neutral

For `[0,20,40,20,0,0,500,1000,500]`, adding a constant baseline residual `b` preserves all neighbour-order relations but changes the global-floor margin because

`m'(b) = (A_j+b) - alpha*(A_g+b) = m + (1-alpha)b`.

The unchanged early 40-ADC component reaches the selector floor at

`b* = 10/(1-0.05) = 10.526315789473685 ADC`.

The deterministic regression checks selector identity immediately below and above this threshold. This is a software sensitivity threshold, not a measured CCB baseline bias.

### F3 — clipping a later maximum can retarget an unchanged early pulse

On the same fixture, apply `y' = min(y,C)`. For `40<C<1000`, the early pulse remains 40 ADC while the global maximum becomes `C`; early eligibility is `40 >= 0.05*C`, hence the exact boundary is `C=800 ADC`. The regression selects the late component at `C=801` and the early component at `C=800` and `C=700`.

No claim is made that the detector clips at these fixture amplitudes; #1014/#1073 and DAQ provenance govern physical ADC saturation.

### F4 — sub-sample phase can change discrete component assignment

A deliberately synthetic, separated continuous fixture is sampled at `t=n+phi`, `n=0..15`:

- early triangle: center 3.2 samples, amplitude 55, half-width 0.8;
- late triangle: center 10.2, amplitude 1000, half-width 2.0.

Examples: `phi=0 -> index 10`; `phi=0.2 -> index 3`; `phi=0.5 -> index 10`; `phi=0.8 -> index 9`. An exhaustive deterministic grid of 1001 equally spaced phases in `[0,1)` yields selected-index counts `{3:229, 9:300, 10:472}`. These counts characterize this fixture/grid only and are **not a detector misassignment probability**, because no CCB sampling-phase distribution is assumed.

### F5/F6 — controls

Clean `[0,50,100,50,0]` has a positive 25-ADC sufficient exact-index radius. Plateau `[0,50,100,100,100,50,0]` has zero exact-index certificate because the selected sample ties its right neighbour. Monotonic fallback `[0,10,20,30,40]` has a 5-ADC exact fallback-index certificate from the argmax/order margins.

## Implementation / reproducibility

New pure module: `scripts/cfd_selector_sensitivity.py`.  
Focused tests: `tests/test_cfd_selector_sensitivity.py`.  
No RNG/seeds. Phase scan event count: 1001 deterministic phase points.  
Parent exact branch dependency at implementation start: PR #1274 head `06618a7ab7b3836b0c7a0e7e0160c88842eee2f9`, itself refreshed non-force onto protected `main@ac2e0bdd873016531f9ef31b30048275c3d2965d`.

Immutable beam ROOT files required by `scripts/real_data_cfd_timing.py` live outside GitHub under `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root` and are not available through this execution environment. The checked-in timing result is explicitly `FLAWED_LEGACY_OUTPUT_QUARANTINED`; it is not reused as new beam evidence. Therefore this fixture atom is the strongest valid substitute in this run.

Exact-head GitHub CI is required before calling the software implementation VALIDATED. A green parent PR does not authorize a later child head. Repository CI evidence, when available, belongs in PR/issue execution comments so appending a run ID does not itself mutate the validated source head.

## Cross-scale compatibility

Micro/algorithm: selector identity has explicit nuisance decision boundaries and a sufficient additive robustness certificate.  
Waveform: baseline, clipping, sample phase, overlap, and device/electronics activity can all alter assignment; this atom does not identify which occurs in data.  
Event/study: a CFD time conditional on `first_local_peak` is conditional on this assignment; authorising studies require run/stave/amplitude/topology transition diagnostics and uncertainty.  
Claim: no timing-resolution, pile-up, saturation, DAQ, SiPM, or detector-performance claim is promoted.

## Four sequential AI review passes

### A. Timing / sampled-signal lead
Background: digital CFD, sampled-waveform timing, censoring and component assignment.  
Evidence: parent selector law, exact analytic boundaries F1-F4, clean/plateau controls.  
Strongest counter-hypothesis: the selector is practically stable despite formal decision boundaries.  
Falsifier: finite perturbations and phase/clipping transformations produce exact component changes in deterministic support.  
Residual: physical nuisance support and scale in CCB waveforms are unmeasured.  
Vote: **ACCEPT deterministic sensitivity law / BLOCK detector-stability inference.**

### B. Adversarial waveform / DAQ reviewer
Background: baseline faults, digitizer clipping, sampling aperture/phase, pile-up and response artifacts.  
Evidence: common-mode baseline and clipping equations, phase fixture, #968/#1009/#1010 dependencies.  
Strongest counter-hypothesis: these fixtures are outside physical waveform support.  
Falsifier: the transformations are intentionally mechanism-agnostic; they establish software non-invariance but cannot establish occurrence.  
Residual: real baseline residuals, ADC transfer/clipping, aperture and phase distribution remain unresolved.  
Vote: **ACCEPT estimator counterexamples / BLOCK occurrence and mechanism claims.**

### C. Independent statistics / validation reviewer
Background: robustness bounds, sensitivity analysis, held-out validation and statistical-unit governance.  
Evidence: closed-form L-infinity certificate, exact threshold tests, 1001-point deterministic phase scan.  
Strongest counter-hypothesis: phase-grid counts can be interpreted as a misassignment rate.  
Falsifier: no physical phase probability measure is specified, so the counts are support coverage only.  
Residual: real-data run-clustered transition rates and truth-labelled injection transfer absent.  
Vote: **ACCEPT deterministic oracle / REJECT probabilistic detector interpretation.**

### D. Claims / provenance reviewer
Background: code-to-artifact-to-claim traceability and completion governance.  
Evidence: #1059 acceptance criteria, authorising producer default, quarantined legacy timing result, parent/child PR provenance.  
Strongest counter-hypothesis: merged software/ADR evidence is enough to close #1059.  
Falsifier: real-data transition decomposition, ambiguity handling, truth transfer and downstream regeneration are explicitly still absent.  
Residual: consumer inventory and authorising rerun remain open.  
Vote: **ACCEPT bounded software child / KEEP #1059 OPEN/PARTIAL and timing claims gated.**

## Children spawned / next work

- `ARU-TIMING-CFD-REALDATA-TRANSITION-001`: on immutable beam bytes, serialize selector diagnostics and estimate transition/fallback/plateau populations by run, stave, amplitude and topology with run-aware uncertainty.
- `ARU-TIMING-CFD-BASELINE-RESIDUAL-DISTRIBUTION-001`: establish real post-baseline residual scale/covariance before comparing to additive/common-mode robustness margins.
- `ARU-TIMING-CFD-DAQ-CLIPPING-TRANSFER-001`: bind actual ADC code/transfer/saturation behavior before mapping clipping thresholds to detector support.
- `ARU-TIMING-CFD-SAMPLING-PHASE-DISTRIBUTION-001`: bind trigger/aperture phase semantics before assigning probabilities to phase-driven selector states.
- `ARU-TIMING-CFD-TRUTH-TRANSFER-001`: held-out digitized injection/MC with known component identity.

Parent #1059 is not complete while these material physical/validation children and downstream regeneration remain unresolved.
