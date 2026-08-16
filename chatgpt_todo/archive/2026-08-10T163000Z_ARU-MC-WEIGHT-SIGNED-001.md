# ARU-MC-WEIGHT-SIGNED-001 — signed-weight numerical falsifiers

Status: **ACTIVE / RESEARCH FIXTURES EXECUTED / PRODUCTION SOURCE SEMANTICS BLOCKED**

Parent/dependencies: #1174, #1172, #880, #1053, #1049. This atom is a numerical/source-contract review, not detector validation and not evidence that the CCB production generator emits negative weights.

## Exact atom

Input: one finite signed binary64 event-weight vector `w=(w_i)` after a future source-specific event-weight adapter has defined the statistical unit and estimand.

For dimensionless signed diagnostics, define

`m=max_i |w_i| > 0`, `u_i=w_i/m`,

`S=sum_i u_i`, `A=sum_i |u_i|`, `Q=sum_i u_i^2`.

Candidate diagnostics have distinct meanings:

- signed ESS-like cancellation diagnostic: `S^2/Q`;
- total-variation / absolute ESS diagnostic: `A^2/Q`;
- dominance: `1/A`;
- cancellation severity: `C=1-|S|/A`, constrained to `[0,1]`;
- signed-mass orientation: `sign(S)`.

A common positive finite scale must leave all five dimensionless outputs unchanged. A global negative sign flips only orientation; it must not turn cancellation severity into a value above one.

## Competing mechanisms and eliminations

1. Treat signed weights as probability weights: **rejected**. The fixture `x=[0,1,2]`, `w=[1,-2,2]` has normalized cumulative signed mass `[1,-1,1]`, which is nonmonotone and leaves `[0,1]`.
2. Legacy cancellation `1-S/A`: **rejected as a quantity named fraction**. For all-negative `[-1,-2]` it equals `2`. Decompose instead into bounded severity `1-|S|/A` plus orientation.
3. Legacy all-zero predicate `n_positive==0`: **rejected for a signed-capable validator**. It classifies `[-1,-2]` as all-zero despite nonzero signed/absolute mass.
4. Raw first/second moments in original units: **rejected as the numerical validity representation**. `sum(|w|)` and `sum(w^2)` can overflow under positive common scaling while the dimensionless signed measure is unchanged.
5. Max-absolute scaled signed diagnostics: **survive locally** for descriptive numerics only.
6. Taking `|w|` or dropping negative rows for inference: **rejected** absent a generator/source derivation because either changes the estimand.

## Executed fixtures

Environment: Python 3.13 / NumPy in the automation runtime. No ROOT or Geant4.

`tools/audit/research_signed_weight_contract.py` and `tests/test_signed_weight_contract_research.py` were executed locally; focused result: **13 passed**.

Exact rational oracle for `[10,-9,1]`:

- `S=2`, `A=20`, `Q=182`;
- signed ESS-like `=2/91`;
- absolute ESS `=200/91`;
- dominance `=1/2`;
- cancellation severity `=9/10`.

Common scales `1e300` and `1e-300` preserve those dimensionless outputs in the max-absolute representation.

For `[1e308,-9e307,1e307]`, the legacy raw absolute total overflows and raw squared moment is nonfinite, while scaled `S=0.2`, `A=2`, `Q=1.82`, absolute ESS `200/91`, severity `0.9` remain defined.

For `[-1,-2]`, the legacy formula reports cancellation `2.0` and the legacy `n_positive==0` predicate marks the vector as all-zero; the separated contract reports cancellation severity `0`, orientation `-1`.

For exact cancellation `[1,-1]`, signed ESS-like is `0` while absolute ESS is `2`, proving that one generic number cannot encode both net signed signal and sampling mass.

Machine-readable result: `results/research/signed_weight_contract_v1.json`.

## Cross-atom compatibility

`compare_data_mc.py` currently calls `validate_mc_weights` with `require_nonnegative=True`, and its ECDF explicitly rejects negative weights. Therefore the current DATA↔MC probability-CDF path must remain nonnegative and is not authorised by this signed research.

A future production signed-weight path must first bind generator/source semantics (#880/#1053), immutable file/config provenance, event unit, and why signed weights occur. Primary literature establishes that some NLO+parton-shower generators can emit negative event weights (Frixione & Webber, JHEP 06 (2002) 029, DOI 10.1088/1126-6708/2002/06/029), but this is **not evidence that CCB's current generator does so**.

## Four sequential AI review passes

### A. Generator/source-physics lead — BLOCK AUTHORISING USE
Evidence: #880/#1053 unresolved raw carrier; repository signed-capable helper; no immutable production signed-weight sample. Strongest counter-hypothesis: signed support is merely generic utility code and can be ignored. Falsifier: a public signed-capable validator already exposes semantics, so its numerical labels can mislead even if unused. Residual: actual campaign sign prevalence and target generator measure. Vote: **BLOCK production signed inference; ACCEPT diagnostic research**.

### B. Adversarial mechanism reviewer — REJECT LEGACY LABELS
Evidence: all-negative, exact-cancellation, extreme-scale and signed-CDF fixtures. Strongest counter-hypothesis: `1-S/A` plus `n_positive==0` are harmless diagnostics. Falsifier: `[-1,-2]` yields a “fraction” of 2 and is falsely classified as all-zero. Residual: global sign orientation may be physically meaningful for a future source. Vote: **REJECT legacy cancellation/all-zero semantics**.

### C. Independent statistics/validation reviewer — ACCEPT LOCAL DECOMPOSITION / BLOCK INFERENCE
Evidence: rational oracle, positive-scale invariance, exact cancellation. Strongest counter-hypothesis: `S^2/Q` is a generic ESS. Falsifier: `[1,-1]` gives signed ESS-like 0 but absolute ESS 2. Residual: covariance, event clustering, generator subtraction structure, null calibration. Vote: **ACCEPT descriptive decomposition only**.

### D. Claims/provenance reviewer — BLOCK PROMOTION
Evidence: compare_data_mc requires nonnegative weights; no production signed sample was inspected. Strongest counter-hypothesis: generic MC@NLO literature proves relevance to this repository. Falsifier: literature establishes possibility in another generator class, not CCB provenance. Vote: **BLOCK any statement that CCB production contains signed weights or that a physics result changes**.

## Residual children / handoff

1. Production-source discriminator under #880/#1053: immutable generator file hash/tree/config, event-wise sign counts, adapter identity, event unit, and target measure.
2. Production validator repair under #1174: replace `1-S/A`, fix all-negative misclassification, and separate raw provenance from scale-stable dimensionless diagnostics only after consumer compatibility is explicit.
3. `compare_data_mc.py` remains a nonnegative probability consumer; if its validator is made scale-stable, its own weighted median/ECDF/histogram arithmetic must also be checked for extreme-scale composition.
4. #1049 remains the inferential/null-calibration gate.

No beam/MC production result or public detector claim is promoted by this atom.
