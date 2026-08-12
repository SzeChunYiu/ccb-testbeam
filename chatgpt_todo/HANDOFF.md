# Latest Handoff

## First-local CFD selector: deterministic nuisance sensitivity is explicit, physical support is not

Selected atom: `ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001`, child of #1059/#1063. This work is stacked on parent PR #1274 because current protected main still lacks the component-bound crossing and selector-diagnostic dependency.

### Live provenance

Protected main at selection: `ac2e0bdd873016531f9ef31b30048275c3d2965d`, required context `test`. Parent #1274 was refreshed without force-push onto that main as exact head `06618a7ab7b3836b0c7a0e7e0160c88842eee2f9`; fresh push and pull-request CI were triggered and must both be green before it can integrate.

#1059 was found incorrectly `closed/completed` even though its issue body still requires real-data fraction/component decomposition, ambiguous-component handling, truth transfer, and downstream regeneration. The prior issue thread itself said to keep it open. It has been reopened; software/ADR integration is not scientific completion.

Immutable beam ROOT files expected by `scripts/real_data_cfd_timing.py` are outside GitHub under `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root` and are unavailable here. `reports/real_data_cfd_timing/result.json` is explicitly `FLAWED_LEGACY_OUTPUT_QUARANTINED`, so no historical timing number is reused as new evidence.

### Additive robustness contract

For the named parent selector with `F=alpha*max(y)`, the child module computes a **sufficient exact-selected-index** radius for arbitrary additive sample perturbations `||delta||_inf < rho`.

For selected local sample `j`, the sufficient candidate-persistence pieces are:

- floor: `(y[j]-F)/(1+alpha)`;
- left local ordering: `(y[j]-y[j-1])/2`;
- right local ordering: `(y[j]-y[j+1])/2`.

For each earlier candidate `k`, every currently failed eligibility predicate supplies a failure-persistence radius: floor deficit divided by `1+alpha`, or neighbour-order deficit divided by 2. Because one persisting failed predicate is enough to keep `k` ineligible, use the maximum available failure radius for that `k`, then the minimum across earlier samples. The overall selected-index certificate is the minimum of selected eligibility and earlier-exclusion pieces. The bound is sufficient, not necessary, and the guarantee is strict (`eps<rho`).

Fallback states combine persistence of all interior ineligibilities with half the unique global-argmax gap. Ties/plateaus naturally give zero exact-index certificate.

### Exact deterministic discriminators

1. Near-floor waveform `[0,25,49.9,25,0,0,500,1000,500]`: adversarial `+eps` on the early candidate and `-eps` on the global peak flips selection at `eps*=0.1/1.05=0.09523809523809524 ADC`. The software certificate matches this boundary.
2. Common residual baseline on `[0,20,40,20,0,0,500,1000,500]`: local ordering is unchanged, but the selector margin changes as `m'(b)=m+(1-alpha)b`; transition threshold is `b*=10/0.95=10.526315789473685 ADC`.
3. Clipping only the later dominant component: with `y'=min(y,C)`, the unchanged early 40-ADC component becomes eligible at exact `C=800 ADC`; `C=801` remains late while `C=800` retargets early.
4. Sampling phase: a synthetic separated triangular waveform sampled at `n+phi` selects index 10 at `phi=0`, 3 at `.2`, 10 at `.5`, and 9 at `.8`. A deterministic 1001-point phase support grid gives `{3:229,9:300,10:472}`. Do not interpret those counts as detector probabilities; no physical phase measure is specified.
5. Controls: clean `[0,50,100,50,0]` has a 25-ADC sufficient exact-index certificate; the `100,100,100` plateau has zero; monotonic boundary fallback has 5 ADC.

### Mechanism boundary

Baseline residuals, digitizer clipping, sub-sample phase, true pile-up, SiPM delayed/correlated activity, electronics shaping/recovery and DAQ corruption can all change selector output. The controlled transforms only establish estimator non-invariance. They do not identify which mechanism occurs in CCB data or how often.

### Implementation

Stacked branch: `audit/cfd-selector-nuisance-sensitivity-v1` from parent #1274 exact head `06618a7...`.

New files:
- `scripts/cfd_selector_sensitivity.py` — pure deterministic L-infinity certificate;
- `tests/test_cfd_selector_sensitivity.py` — exact near-floor, baseline, clipping, 1001-phase, clean, plateau and fallback controls;
- `chatgpt_todo/archive/...ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001.md`.

Coordination: this `HANDOFF.md` and `ACTIVE_TASK.md`. No RNG, beam data, production MC or fitted detector nuisance distribution participates.

### Four sequential AI votes

**Timing / sampled-signal lead:** ACCEPT deterministic sensitivity law; BLOCK detector-stability inference.  
**Adversarial waveform / DAQ reviewer:** ACCEPT estimator counterexamples; BLOCK occurrence and microscopic-mechanism claims.  
**Independent validation reviewer:** ACCEPT deterministic support oracle; REJECT interpreting the phase-grid counts as probabilities.  
**Claims / provenance reviewer:** ACCEPT bounded software child; KEEP #1059 OPEN/PARTIAL and all timing-performance claims gated.

### Next work

Highest-value physical child remains `ARU-TIMING-CFD-REALDATA-TRANSITION-001` once immutable beam bytes are available. Before comparing mathematical margins to detector support, separately close `ARU-TIMING-CFD-BASELINE-RESIDUAL-DISTRIBUTION-001`, `ARU-TIMING-CFD-DAQ-CLIPPING-TRANSFER-001`, and `ARU-TIMING-CFD-SAMPLING-PHASE-DISTRIBUTION-001`; held-out truth transfer remains required.

Do not close #1059, do not promote a timing resolution, and do not call a selector switch pile-up/saturation/noise solely from this atom.
