# ARU-MC-CS-UNCERTAINTY-001 — 190 MeV p-d source uncertainty contract

## Atom and dependency graph

Selected atom: the transformation

`Ermisch Table-VI central values/statistical errors/systematic statements -> normalized p(theta_cm) source nuisance model -> generator truth distribution -> downstream source-sensitive claims`.

Parent/dependencies: #1178 central-value sampler/support law, #1053/#880 generator measure, CL-021. Existing issue #1179 owns this universe; no duplicate issue is created. Children spawned here: source systematic covariance/recoverable nuisance structure; support-model uncertainty covariance/cross-term; generator-only nuisance propagation; downstream detector-chain source sensitivity.

## Expert group and sequential review roles

1. **Few-nucleon source physicist** — background in p-d elastic scattering, CM differential cross sections and experimental systematics; owns source semantics and physics nuisance decomposition.
2. **Adversarial mechanism/numerical reviewer** — background in inverse-CDF source algorithms and robustness; attempts to break normalization/correlation assumptions with deterministic counterworlds.
3. **Independent statistics/validation reviewer** — background in ratio estimators, covariance propagation and simulation calibration; separates conditional calculations from coverage claims.
4. **Claims/provenance reviewer** — background in scientific traceability and claim governance; maps every numerical result to source bytes/model IDs and blocks overinterpretation.

These are sequential AI review roles, not independent human collaborators.

## Exact input/output contract

Immutable input table:

- path: `geant4/src_patch/sigma_pd_cm_190.txt`;
- SHA-256: `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`;
- 640 bytes, 28 rows;
- `theta_cm` in degrees, `dσ/dΩ` in mb/sr, third column absolute statistical uncertainty in mb/sr;
- measured CM support 26.49–169.78 degrees;
- primary source: K. Ermisch et al., PRC 71, 064004 (2005), DOI `10.1103/PhysRevC.71.064004`, Table VI.

Nominal source law inherited from #1178:

`p(theta|sigma) = g(theta;sigma) / Z(sigma)`,

where node values are `g_i = sigma_i sin(theta_i)`, `g(theta)` is linearly interpolated on measured support, and

`Z(sigma) = integral g(theta;sigma) dtheta`.

Output of this atom is not a single "source uncertainty" number. It is a typed set of source facts, explicitly conditional statistical propagation, and nonprobabilistic stress envelopes. Units and statuses are serialized in `results/research/sigma_cm_source_uncertainty_v1.json`.

## Primary-literature facts and source-to-claim mapping

The source paper reports at 190 MeV:

- 3% point-to-point systematic uncertainty;
- total systematic uncertainty below 4.5%;
- Section IV D explains that target-thickness variation across measurements and background-subtraction uncertainty contribute to excess scatter; an extra error is added to each angular cross-section point until a high-order polynomial fit reaches approximately unit chi-square. This extra term is called the point-to-point systematic uncertainty.

The paper does not supply a 28x28 covariance matrix in the retained source table. Therefore `3% point-to-point` does **not** uniquely identify independent Gaussian row nuisances. This source-method fact is now recorded in `sigma_pd_cm_190.source.json` rather than being inferred downstream.

Stable concern `SRC-UQ-001` (P0 for quantitative source-uncertainty claims): **do not convert one quoted percentage into a covariance structure without an explicit additional model.** Rebuttal/falsifier requirement: recover a source-bound covariance/decomposition or preserve multiple compatible nuisance worlds and their downstream sensitivity.

## Competing microscopic/statistical mechanisms

### H1 — fully common multiplicative normalization

`sigma_i' = c sigma_i` for all i. For normalized angular shape,

`F(theta;c sigma) = F(theta;sigma)`.

Survives as a normalization nuisance for absolute-rate estimands, but is observationally equivalent to no change for normalized shape.

### H2 — independent rowwise 3% Gaussian systematic

Not source-identified. It may be a candidate sensitivity model, but cannot be promoted as the experimental covariance merely because the quoted term is called point-to-point.

### H3 — nodewise bounded 3% shape perturbation

`sigma_i' in [0.97,1.03] sigma_i` independently. This is a conservative deterministic **box sensitivity**, not a probability distribution. Survives as a falsifier/envelope.

### H4 — correlated smooth shape mode

Target thickness or angle/time-dependent normalization drift can produce correlated angular distortions. Survives; correlation length/form is unresolved.

### H5 — alternating/localized 3% perturbations

Adversarial shape controls. Survive as negative controls but are not source probabilities.

### H6 — statistical third-column errors treated with diagonal first-order covariance

Survives only as a conditional reference under independent-row statistical errors. It is not the systematic covariance.

### H7 — no source uncertainty because the CDF is normalized

Rejected. Only a fully common scale cancels. Angle-dependent perturbations alter normalized shape.

Equivalent global-scale parameterizations are collapsed into H1 because they induce the same normalized angular measure.

## Equations, invariants and identifiability

For any fixed theta under the linear-node model, cumulative and total masses are linear in the node cross sections:

`N(theta;sigma) = a(theta) . sigma`,

`Z(sigma) = b . sigma`,

so

`F(theta;sigma) = (a(theta).sigma)/(b.sigma)`.

This makes the independent-box extrema a linear-fractional optimization. At candidate ratio r, the maximum over a box is determined by the signs of `(a-r b)_i`: select the upper bound where the coefficient is positive and the lower bound where it is negative. Bisection on the root of that maximized linear form gives the exact box extremum for each fixed theta. The continuous-theta supremum is approximated here on a declared 10,001-point support grid; it is not called an exact continuous supremum.

The normalized mean angle is another linear-fractional ratio. For interval left endpoint `L` and width `h`, first-moment coefficients for node densities are

- left node: `L h/2 + h^2/6`;
- right node: `L h/2 + h^2/3`.

For a ratio `R=(a.sigma)/(b.sigma)`, the first-order gradient is

`dR/dsigma_i = (a_i Z - N b_i)/Z^2`.

The conditional diagonal statistical variance is

`Var(R) approximately sum_i (dR/dsigma_i)^2 s_i^2`.

Identifiability limit: a total bound and one point-to-point percentage cannot recover covariance eigenmodes or distinguish smooth drift from independent local errors.

## Executed experiments and exact results

Independent local environment used for the deterministic reference execution:

- Python `3.13.5`;
- executable `/opt/pyvenv/bin/python`;
- Linux `6.18.35-x86_64`, glibc 2.41;
- no RNG/seeds; no beam data; no Geant4.

Equivalent source utility execution produced the committed JSON. A focused local pytest subset covering exact input binding, common-scale cancellation, box extrema and a small exact-corner oracle returned `4 passed` in 26.92 s. This is local supporting evidence only; exact-head repository CI remains the merge gate.

Deterministic results:

- nominal measured-support normalization: `1.19776307651449`;
- nominal mean theta_cm: `56.78396200051643 deg`;
- fully common `+4.5%` scale control: max normalized-CDF change `3.3306690738754696e-16` (floating-point noise);
- independent-node `[0.97,1.03]` box, 10,001 theta points:
  - maximum upward CDF excursion `0.01430729974634637` at `46.951812 deg`;
  - maximum downward excursion `0.014380572923809676` at `46.951812 deg`;
  - mean-angle range `56.050251002153615` to `57.5322672970398 deg`;
- alternating `+3%/-3%` node control: CDF sup delta `0.0014567989868344983`;
- opposite alternating pattern: `0.0014569781233605278`;
- conditional diagonal statistical reference:
  - maximum pointwise CDF standard uncertainty `0.0004453566889758832` near `49.488045 deg`;
  - mean-angle standard uncertainty `0.02252797870713097 deg`.

The order-of-magnitude difference between the alternating controls and the nodewise box is direct evidence that the quoted 3% does not define one unique shape effect without correlation assumptions.

## Hypotheses eliminated and survivors

Eliminated:

- "normalization removes all source uncertainty";
- "3% point-to-point uniquely means 28 independent Gaussian nuisances";
- combining the 3% and <4.5% terms as undocumented independent percentages;
- calling the nodewise box a 68%/95% interval or covariance-derived band.

Surviving:

- pure common normalization for absolute-rate work, which cancels for normalized shape;
- conditional diagonal statistical propagation from the third column;
- nonprobabilistic nodewise box as a stress envelope;
- source-bound smooth/correlated systematic modes if recoverable;
- support/interpolation uncertainty as a separate nuisance family under #1178;
- a deliberately conservative multi-model envelope if source covariance cannot be recovered.

## Cross-atom propagation

Micro/source nodes -> normalized theta_cm source -> p/d kinematics -> truth energy/angle/penetration mixtures -> detector response -> DATA/MC comparison -> CL-021/B2/B8 claims.

A local central-value sampler can be numerically exact while the source uncertainty remains unidentified. Conversely, a valid source uncertainty model cannot authorize detector claims until #1182 runtime readiness, #1052 detector measurand, event weights, quenching/optical/SiPM/electronics and DATA-like reconstruction gates pass.

## Four sequential review passes

### (a) Few-nucleon source physicist — **REVISE**
Evidence inspected: exact source table/sidecar, Ermisch Table VI and Sec. IV D, #1178 sampler model. Strongest counter-hypothesis: normalized direct sampling makes the total <4.5% systematic irrelevant. Attempted falsifier: common-scale control indeed cancels, while angle-dependent node perturbations do not. Residual uncertainty: experimental covariance decomposition, smoothness/correlation across angular settings, and support outside measured angles. Vote: **REVISE source authorization; accept common-scale equivalence only for shape.**

### (b) Adversarial mechanism reviewer — **BLOCK single-covariance promotion**
Evidence inspected: exact linear-fractional map and 3% systematic statement. Strongest counter-hypothesis: treating every row as iid 3% is a harmless default. Attempted falsifier: alternating perturbations change the CDF by ~0.00146 while the allowed nodewise box reaches ~0.01438; materially different correlation worlds share the same 3% marginal bound. Residual: physically admissible correlation structure. Vote: **BLOCK invented iid covariance; ACCEPT box only as stress test.**

### (c) Independent statistics/validation reviewer — **ACCEPT deterministic mechanics / BLOCK coverage claim**
Evidence inspected: exact-corner oracle, common-scale invariant, delta-method equations, committed JSON. Strongest counter-hypothesis: the box envelope is a confidence band. Falsifier: no nuisance probability law/covariance was used, so coverage is undefined. Residual: statistical-row dependence and nonlinear propagation beyond first order. Vote: **ACCEPT deterministic sensitivity and conditional statistical reference; BLOCK probabilistic inference.**

### (d) Claims/provenance reviewer — **BLOCK CL-021 promotion**
Evidence inspected: CL-021, issue #1179, exact table SHA/source DOI, current runtime blockers. Strongest counter-hypothesis: the central-value sampler fix means CL-021 is solved. Falsifier: source covariance/support, compiled runtime, manifest binding and detector-chain regeneration remain open. Residual: real downstream source sensitivity. Vote: **BLOCK claim promotion; REVISE docs to expose uncertainty model IDs/status.**

## Repository/claim consequences

This branch adds the executable sensitivity audit, tests, machine-readable result, richer source sidecar semantics and a CL-021 update. It does **not** alter the central source table or production Geant4 generator.

PR #1184 is a stale follow-on relative to `main@f5f96951...`; its current diff only rewords a comment and would replace the exact source-model IDs with wording that says the MV3/CL-021 residual is fixed. That wording is incompatible with the open gates above and should not be merged as claim language.

No B2/B8 historical diagnostic is regenerated. CL-021 remains OPEN/GATED. #1179 remains open because this work does not invent the missing systematic covariance.

## Next highest-value child atom

First preference: recover any source-bound covariance/decomposition from experiment auxiliary material or author documentation; if unavailable, define preregistered nuisance families (common normalization + smooth angular modes + bounded point-to-point residual) that are demonstrably consistent with the paper without pretending uniqueness. Then propagate those modes through a compiled, fail-closed generator only after #1182/runtime closure. Separately, #1178 support-model uncertainty must be scanned because truncation can dominate the forward-source phase space independently of the 3% table uncertainty.
