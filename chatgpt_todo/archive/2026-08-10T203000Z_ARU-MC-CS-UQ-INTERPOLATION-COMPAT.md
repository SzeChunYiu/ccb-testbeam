# ARU-MC-CS-UQ-INTERPOLATION-COMPAT-001 — source node envelope × interpolation model

## Team and sequential review roles

1. **Few-nucleon source physicist** — background in p–d elastic scattering, differential-cross-section source construction, kinematic source terms and detector-independent generator interpretation. Owns the physical meaning of `dσ/dΩ`, the `sin(theta)` Jacobian and the distinction between measured-node information and interpolation/support assumptions.
2. **Adversarial numerical-mechanism reviewer** — background in floating-point numerical analysis, inverse transforms and sensitivity analysis. Owns equivalence collapse, representation invariance, hostile counterexamples and cross-model envelope composition.
3. **Independent statistics/UQ reviewer** — background in empirical-process statistics, covariance modelling and uncertainty propagation. Owns identifiability, conditional statistical references, nonprobabilistic envelopes and prohibition on unsupported confidence semantics.
4. **Claims/provenance reviewer** — background in reproducible scientific software and evidence governance. Owns exact hashes, source/model IDs, result-to-claim propagation, status language and unresolved dependency handoff.

These are AI review roles, not independent human collaborators.

## Parent / dependency graph

Parent issue: #1179 (`ARU-MC-CS-UNCERTAINTY-001`).

Upstream evidence already validated on main before this atom:

- exact Table-VI bytes and DOI binding (#1180);
- explicit measured-support reference and exact inverse for `linear_node_pdf_exact_inverse_v1` (#1178);
- interpolation-order model sensitivity `linear_node_pdf_exact_inverse_v1` versus `linear_cross_section_then_jacobian_v1` (`results/research/sigma_cm_interpolation_sensitivity_v1.json`);
- deterministic 3% node-box and conditional diagonal-row-statistical sensitivity (`results/research/sigma_cm_source_uncertainty_v1.json`).

Downstream dependencies remain #1182 runtime readiness, production generator manifest binding, #1053 generator-measure semantics, detector-response transport and CL-021.

## Exact atom contract

Input bytes:

- `geant4/src_patch/sigma_pd_cm_190.txt`;
- 640 bytes, 28 rows;
- SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`;
- `theta_cm` support 26.49–169.78 degrees;
- source observable `sigma_i = dσ/dΩ(theta_i)` in mb/sr;
- third column absolute statistical uncertainty in mb/sr.

The normalized source observable is dimensionless cumulative probability

`F(theta; sigma, M) = N_M(theta; sigma) / Z_M(sigma)`

for interpolation model `M`, where both numerator and denominator are linear in the 28 source nodes for each surviving interpolation class.

The explicit node-box sensitivity set is

`B = {sigma': 0.97 sigma_i <= sigma'_i <= 1.03 sigma_i for every i}`.

`B` is a **NONPROBABILISTIC_ENVELOPE**. It has no implied coverage or density over nuisance vectors.

Outputs are source-level CDF/mean-angle sensitivity only. No detector, event-selection, rate or confidence-level quantity is authorised.

## Competing mechanisms / mathematical descriptions

A. **Current interpolation only + 3% node box.** This is the already-executed #1179 sensitivity but does not test whether the box composes with a surviving interpolation alternative.

B. **Alternative interpolation central curve treated as automatically covered by current-mode box.** Observationally tempting if the central alternative lies inside the current box, but this collapses distinct model-form and source-node nuisance universes without testing their joint image.

C. **Independent additive/quadrature combination of interpolation and node-box effects.** Rejected on semantics: interpolation class has no probability weight and the box has no probability law; quadrature is undefined. Pointwise arithmetic addition is at best a conservative construction and need not equal the image of the actual model union.

D. **Union of each surviving interpolation class propagated through the same explicit node box.** Survives as the strongest deterministic cross-atom sensitivity construction available without inventing probabilities or covariance.

Equivalent pure common source-normalization modes remain collapsed for normalized shape because `F(theta; c sigma, M)=F(theta; sigma, M)` for `c>0`.

## Equations / invariants

For `linear_node_pdf_exact_inverse_v1`, the interval polar-density basis is linear between endpoint values `sigma_i sin(theta_i)`.

For `linear_cross_section_then_jacobian_v1`, the measured observable is interpolated first:

`sigma(theta) = sigma_i (theta_{i+1}-theta)/h + sigma_{i+1}(theta-theta_i)/h`,

then multiplied by `sin(theta)`. The node-basis integrals are analytic using

`I0(a,b)=∫sin(theta)dtheta`,
`I1(a,b)=∫theta sin(theta)dtheta`,
`I2(a,b)=∫theta^2 sin(theta)dtheta`.

For either model, fixed-theta box extrema of

`R(sigma)=(a·sigma)/(b·sigma)`

are linear-fractional and are solved by monotone root bisection over the independent positive box. This avoids Monte-Carlo nuisance sampling and seed dependence.

Required compatibility invariant:

`U(theta) = union_M { F_M(theta; sigma') : sigma' in B }`.

A single-model box is cross-model closed only if the full alternative-model image is contained, not merely the alternative central curve.

## Executed discriminators

Environment: Python 3.13.5; no RNG. Local source bytes were reconstructed exactly from the connected GitHub file and verified to the canonical SHA-256 above.

Command:

`python tools/audit/research_sigma_cm_uq_interpolation_compatibility.py --output results/research/sigma_cm_uq_interpolation_compatibility_v1.json`

Equivalent local path execution generated the committed machine-readable result. Focused regression:

`pytest -q test_compat.py` → `4 passed in 11.97s`.

A 10,001-point measured-support grid was used for cross-model composition. Each point uses analytic node coefficients and deterministic linear-fractional box extrema; there is no stochastic seed or event count.

### Results

Current interpolation reproduces the previously merged #1179 node-box sensitivity exactly on the same grid:

- upward CDF excursion `0.01430729974634637` at 46.951812°;
- downward CDF excursion `0.014380572923809676` at 46.951812°;
- mean-angle range 56.050251002153615–57.5322672970398°.

Alternative interpolation under its own same node box gives:

- upward CDF excursion `0.014310586515772328` at 42.997008°;
- downward CDF excursion `0.014374731878122216` at 47.023457°;
- mean-angle range 56.02560085079668–57.50849000593509°.

The alternative **central** curve has zero violation of the current-mode 3% box on the tested grid. That is not sufficient closure. Propagating the node box through the alternative model extends beyond the current-mode box by:

- upper extension `0.0010650343985590949` at 39.586706°;
- lower extension `0.0002537872354466675` at 145.879228°.

The union of both interpolation classes and the same node box, expressed relative to the current nominal reference, reaches:

- upward CDF excursion `0.015299817076167732` at 43.168956°;
- downward CDF excursion `0.014380572923809676` at 46.951812°;
- mean-angle range 56.02560085079668–57.5322672970398°.

The 10,001-point central interpolation CDF difference is `0.001012980056818935`, consistent with the separately merged analytic maximum `0.0010129801982659559`. The interpolation central difference is therefore small compared with the deliberately broad node box, but not interchangeable with it.

Conditional diagonal-row-statistical references remain close across interpolation models but distinct:

- current: max pointwise CDF standard uncertainty `0.0004453566889758832`, mean-angle standard uncertainty `0.02252797870713097°`;
- alternative: `0.0004435837618530407`, `0.022356857259092505°`.

These are conditional delta-method values, not systematic covariance reconstruction.

## Hypotheses eliminated / surviving

Eliminated:

- **H-COMP-1:** “the current-mode 3% box closes interpolation uncertainty because it contains the alternative nominal.” False: the alternative model's propagated box breaches the current box.
- **H-COMP-2:** “interpolation and node-box effects should be quadrature-combined.” Rejected because neither supplies the required common probabilistic nuisance law.
- **H-COMP-3:** “the two interpolation classes become equivalent once source-node uncertainty is admitted.” False: their full box images differ.

Surviving:

- **H-COMP-S1:** preserve interpolation class as a discrete model-form nuisance and propagate each explicit source-node sensitivity construction through each surviving class;
- **H-COMP-S2:** if future source information supplies a justified covariance/eigenmode model, propagate that same source-space model independently through each interpolation class before model averaging/enveloping is considered;
- **H-COMP-S3:** a source-authoritative interpolation prescription could eliminate the model-form branch, but no such prescription is presently bound.

## Four sequential review passes

### (a) Few-nucleon source physicist — REVISE

Evidence inspected: exact Table-VI node values/provenance, #1178 interpolation definitions, #1179 source-uncertainty contract and the new composed result.

Strongest counter-hypothesis: the 3% source statement is so broad that interpolation choice is physically negligible and can be discarded.

Attempted falsifier: propagate the exact same 3% source-node set through both interpolation classes rather than comparing central curves only.

Residual uncertainty: physical angular covariance and source-authorised between-node functional form remain unavailable; measured-support truncation remains a separate physics model.

Vote: **REVISE** — interpolation is subdominant to this stress box but remains a separate source-model dependency.

### (b) Adversarial numerical-mechanism reviewer — ACCEPT discriminator / BLOCK collapse

Evidence inspected: linear coefficient derivations, positive-box linear-fractional extrema, 10,001-point cross-model grid and prior analytic interpolation audit.

Strongest counter-hypothesis: if the alternative nominal lies within the current box, all alternative perturbations will also lie within it.

Attempted falsifier: compare the **full alternative box image** with the current box. It breaches upward by `0.0010650343985590949` and downward by `0.0002537872354466675`.

Residual uncertainty: grid localisation of the cross-model union is finite-resolution; individual fixed-theta box extrema are deterministic to binary64/root-solve precision. A future analytic search for envelope-extremum theta can remove this remaining grid localisation.

Vote: **ACCEPT local cross-atom result / BLOCK single-box closure**.

### (c) Independent statistics/UQ reviewer — ACCEPT mechanics / BLOCK inference

Evidence inspected: source statements already mapped in #1179, box semantics, conditional statistical delta method and new union construction.

Strongest counter-hypothesis: interpolation shift and 3% node envelope can be combined as independent one-sigma contributions.

Attempted falsifier: inspect the definitions. There is no nuisance probability law for interpolation model and no coverage law for the 3% box; independence and one-sigma semantics are undefined.

Residual uncertainty: experimental row covariance, decomposition of point-to-point versus common systematics, and any probability assigned to interpolation families.

Vote: **ACCEPT deterministic sensitivity / BLOCK confidence, p-value or quadrature use**.

### (d) Claims/provenance reviewer — BLOCK promotion

Evidence inspected: current `main` source hash/model IDs, CL-021, #1178/#1179/#1182 and machine-readable outputs.

Strongest counter-hypothesis: because both source sensitivities are now quantified, CL-021 can move to validated.

Attempted falsifier: follow dependencies upward. Runtime compiled Geant4 closure, source fault semantics, support-model sensitivity, production manifest binding and detector-response propagation remain open.

Residual uncertainty: no production generator or detector-level sample was regenerated under the model union.

Vote: **BLOCK CL-021 promotion / ACCEPT repository-level source sensitivity evidence**.

## Cross-scale propagation / claim consequences

Micro/source-node and interpolation choices now compose explicitly at source-CDF level. They have **not** been propagated through generated p/d kinematics, detector deposition, quenching, optical/WLS transport, SiPM/electronics, waveform reconstruction, selection, weighted statistics or DATA comparison. Therefore no B2/B8, PID, timing, penetration, energy, pile-up, rate or detector-performance result changes status.

CL-021 remains `OPEN / GATED`.

## Child atoms spawned

1. **ARU-MC-CS-UQ-THETA-EXTREMA-001:** remove finite-grid localisation for the cross-model envelope extrema if these source-level bounds become claim-bearing.
2. **ARU-MC-CS-UQ-COVARIANCE-001:** recover source-bound covariance/decomposition or preregister explicit smooth/common/residual nuisance families; do not infer iid 3% rows.
3. **ARU-MC-CS-SUPPORT-COMPAT-001:** propagate surviving uncertainty/interpolation mechanisms across independently justified off-support models; support truncation remains a separate source-physics universe.
4. **ARU-MC-CS-GENERATOR-PROP-001:** after #1182 compiled fail-closed readiness, run paired seeded generator-only samples for surviving source models with exact source/model/seed/event provenance.

Parent #1179 remains open while these material assumptions are unresolved.
