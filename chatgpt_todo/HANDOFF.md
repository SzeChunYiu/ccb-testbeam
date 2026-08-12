# Latest Handoff

## First-local CFD selector nuisance sensitivity: deterministic support mapped; detector support unresolved

Selected atom: `ARU-TIMING-CFD-NOISE-PHASE-SATURATION-SENSITIVITY-001`, child of #1059/#1063.

### Live provenance

The parent selector-identifiability/component-bound-crossing repair is now present on protected main via PR #1278 at exact `main@5b7312e8ecabdfbfb9fe2d74a26a4e70352eaec6`. Exact pre-merge parent head `d2ba6a37776d14b6fdcd0967c9e724e4752c24aa` passed pull-request MC Validation `31557640867` and push MC Validation `31557638606`; both were required before merge. Draft #1274 was closed unmerged only because its ready transition was unavailable; its same science was recreated without force-push as #1278.

#1059 had drifted to `closed/completed` although its own real-data transition, ambiguity, truth-transfer and downstream-regeneration criteria remain unresolved. It was reopened and remains OPEN/PARTIAL.

Immutable beam ROOT files required by `scripts/real_data_cfd_timing.py` are external to GitHub under `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root` and unavailable in this execution environment. The checked-in timing result is explicitly `FLAWED_LEGACY_OUTPUT_QUARANTINED`, so no historical timing number is reused as new evidence.

### Deterministic robustness contract

For the named parent selector with floor `F=alpha*max(y)`, the child computes a sufficient exact-selected-index radius for arbitrary additive sample perturbations `||delta||_inf < rho`.

For selected local sample `j`, sufficient candidate-persistence pieces are `(y[j]-F)/(1+alpha)` for floor eligibility, `(y[j]-y[j-1])/2` and `(y[j]-y[j+1])/2` for neighbour ordering. For each earlier candidate, every currently failed predicate supplies a failure-persistence radius; because one persistent failure is enough to keep that sample ineligible, use the maximum per earlier sample, then the minimum across earlier samples. The overall exact-index certificate is the minimum of selected eligibility and earlier-exclusion pieces. The guarantee is strict, sufficient rather than necessary, and non-authorising for physical pulse identity.

Fallback states combine persistence of all interior ineligibilities with half the unique global-argmax gap. Ties/plateaus naturally give zero exact-index certificate.

### Exact deterministic discriminators

1. Near-floor `[0,25,49.9,25,0,0,500,1000,500]`: adversarial `+eps` on early peak and `-eps` on global peak flips at `eps*=0.1/1.05=0.09523809523809524 ADC`; tests check both sides.
2. Common residual baseline `[0,20,40,20,0,0,500,1000,500]+b`: `m'(b)=m+(1-alpha)b`; selector transition at `b*=10/0.95=10.526315789473685 ADC`.
3. Clipping only the later dominant component `min(y,C)`: unchanged early 40-ADC component becomes eligible at exact `C=800 ADC`; `C=801` remains late.
4. Synthetic separated triangular continuous fixture sampled at `n+phi`: `phi=0/.2/.5/.8` selects indices `10/3/10/9`; deterministic 1001-point phase support scan gives `{3:229,9:300,10:472}`. These are support counts only, not a detector probability because no CCB phase measure is supplied.
5. Controls: clean single pulse has 25-ADC sufficient exact-index radius; `100/100/100` plateau has zero; monotonic fallback has 5 ADC.

### Mechanism boundary

Residual baseline, digitizer clipping, sub-sample phase, true pile-up, SiPM delayed/correlated activity, electronics shaping/recovery and DAQ corruption can all alter selector output. The controlled transformations establish estimator non-invariance only; they do not identify which mechanism occurs or how often.

### Implementation

PR #1277 carries `scripts/cfd_selector_sensitivity.py`, seven focused deterministic tests, the immutable ARU archive, and coordination updates. After parent #1278 integration, #1277 is to target protected main and requires fresh exact-final-head push and pull-request checks. No RNG, beam data, production MC or fitted nuisance distribution participates.

### Four sequential AI votes

**Timing / sampled-signal lead:** ACCEPT deterministic sensitivity law; BLOCK detector-stability inference.  
**Adversarial waveform / DAQ reviewer:** ACCEPT estimator counterexamples; BLOCK occurrence and microscopic-mechanism claims.  
**Independent validation reviewer:** ACCEPT deterministic support oracle; REJECT phase-grid counts as probabilities.  
**Claims / provenance reviewer:** ACCEPT bounded software child; KEEP #1059 OPEN/PARTIAL and timing claims gated.

### Next work

Highest-value physical child remains `ARU-TIMING-CFD-REALDATA-TRANSITION-001` when immutable beam bytes become available. Before comparing mathematical margins to detector support, separately close `ARU-TIMING-CFD-BASELINE-RESIDUAL-DISTRIBUTION-001`, `ARU-TIMING-CFD-DAQ-CLIPPING-TRANSFER-001`, and `ARU-TIMING-CFD-SAMPLING-PHASE-DISTRIBUTION-001`; held-out truth transfer remains required.

Do not close #1059, do not promote a timing resolution, and do not infer pile-up/saturation/noise from a selector switch alone.
