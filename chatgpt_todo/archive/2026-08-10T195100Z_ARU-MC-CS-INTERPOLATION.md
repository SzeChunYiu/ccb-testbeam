# ARU-MC-CS-INTERPOLATION-001 — 190 MeV p-d source interpolation order

Status: `PARTIAL / DETERMINISTIC_SOURCE_MODEL_SENSITIVITY / NO_DETECTOR_AUTHORIZATION`

Parent: #1178. Cross-dependencies: #1179 source uncertainty, #1182 runtime readiness, #1053/#880 event-measure provenance, CL-021.

## Atomic input/output contract

Input is the exact repository cross-section table `geant4/src_patch/sigma_pd_cm_190.txt`: 640 bytes, 28 rows, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, with `theta_cm` in degrees and `dσ/dΩ` in mb/sr over 26.49–169.78 degrees. The source paper is K. Ermisch et al., *Phys. Rev. C* 71, 064004 (2005), DOI `10.1103/PhysRevC.71.064004`. The experiment supplies angular cross-section measurements; the repository has no source-bound prescription that uniquely fixes the between-node interpolation used by the generator.

The shape-only source measurand is

`p(theta) = g(theta) / integral g(theta)dtheta`,

with the polar Jacobian `g(theta)=sigma(theta) sin(theta)`.

The selected atom asks whether the operations

`interpolate -> multiply by sin(theta)`

and

`multiply node values by sin(theta_i) -> interpolate`

are observationally equivalent on the exact measured support.

## Competing mathematical descriptions

### H1 — current production reference

`g_A(theta) = Lin[(theta_i, sigma_i sin(theta_i))]`.

Mode ID: `linear_node_pdf_exact_inverse_v1`. The current generator exactly inverts this piecewise-linear polar-density law.

### H2 — published-observable interpolation first

`g_B(theta) = Lin[(theta_i, sigma_i)] * sin(theta)`.

Research mode ID: `linear_cross_section_then_jacobian_v1`.

H1 and H2 agree exactly at every published node because both give `sigma_i sin(theta_i)` there. They differ between nodes because linear interpolation and multiplication by `sin(theta)` do not commute.

### H3 — discrete node masses

Rejected for the current generator question because the generated `theta_cm` is continuous; a discrete-node probability measure is a different source model.

### H4 — spline/theory-constrained interpolation

Survives only as a child model family. It requires explicit regularization/physics assumptions and must not be selected from detector agreement alone.

Support extrapolation is not part of this atom: both H1 and H2 use `measured_table_support_truncate_v1`, so the comparison isolates interpolation order.

## Equations and invariants

On interval `[theta_i,theta_{i+1}]`, H1 is linear directly in `g` and has trapezoid mass

`M_A = 0.5 * (g_i + g_{i+1}) * Delta_theta`.

For H2, write the piecewise-linear cross section as `sigma(theta)=a+b theta`. Then

`M_B = integral (a+b theta) sin(theta) dtheta`,

with antiderivative

`-(a+b theta) cos(theta) + b sin(theta)`.

For the first moment, H2 uses

`integral theta(a+b theta)sin(theta)dtheta`.

Both models must satisfy CDF endpoints 0/1, nonnegative density on measured support, and node equality. In the vanishing-interval limit their difference tends to zero. A common positive cross-section scaling cancels from both normalized shapes.

A representation-invariance discriminator is available without inventing a new physical source. Insert an exact midpoint node on every original linear-sigma segment:

`theta_m=(theta_i+theta_{i+1})/2`, `sigma_m=(sigma_i+sigma_{i+1})/2`.

These added knots are mathematically redundant under H2, so H2 must be unchanged. They are not redundant under H1 because `sigma_m sin(theta_m)` is generally not the midpoint of `sigma_i sin(theta_i)` and `sigma_{i+1} sin(theta_{i+1})`.

## Executed deterministic experiment

Research utility: `tools/audit/research_sigma_cm_interpolation_sensitivity.py`.

Machine result: `results/research/sigma_cm_interpolation_sensitivity_v1.json`.

No RNG is used. Local known-answer regression command:

`python -m pytest -q tests/test_sigma_cm_interpolation_sensitivity.py`

Result before repository push: `4 passed in 0.05s` in a minimal repo-layout fixture using the exact table bytes.

An independent dense 500,001-point trapezoidal numerical check was also run against the analytic integrals. The dense-minus-analytic differences were approximately `4.38e-12` in H2 normalization, `-5.34e-10 deg` in H2 mean angle, `6.49e-12` in H1 normalization, and `-5.75e-10 deg` in H1 mean angle. This is a numerical implementation cross-check only.

### Exact central-value results

- H1 normalization: `1.1977630765144902`.
- H2 normalization: `1.2035777046844027`.
- H1 mean `theta_cm`: `56.7839620005164 deg`.
- H2 mean `theta_cm`: `56.759694169292274 deg`.
- H2 minus H1 mean shift: `-0.024267831224125052 deg`.
- Supremum normalized-CDF difference: `0.0010129801982659559` at `43.94458149140975 deg`.
- Median shift H2-H1: `-0.05619069758156213 deg`.
- 95th-percentile shift H2-H1: `+0.13082849690529305 deg`.

### Representation-refinement falsifier

After inserting one exact sigma-linear midpoint in every interval:

- H2 max normalized-CDF change: `1.4432899320127035e-15` (binary64-scale numerical noise).
- H1 max normalized-CDF change: `0.000768558730840585`, near `43.75661087434171 deg`.

Therefore H1 and H2 are not duplicate parameterizations of one continuous model. They are distinct interpolation assumptions even though they match all measured nodes.

## Four sequential AI review passes

### (a) Few-nucleon source physicist — **REVISE**

Background/role: elastic p-d source kinematics, differential-cross-section observables, polar-angle Jacobians. Evidence inspected: exact table/source identity, current source-model sidecar, #1178 source law, Ermisch source metadata. Strongest counter-hypothesis: because both models pass through every measured point, interpolation order is immaterial. Attempted falsifier: exact CDF/mean/quantile comparison on identical support. Result: nonzero shape differences survive normalization. Residual uncertainty: the primary experiment does not provide a unique continuous between-angle source law in repository provenance. Vote: **REVISE source-model authorization; retain current law only as a named reference until sensitivity is propagated.**

### (b) Adversarial numerical/model reviewer — **ACCEPT distinction / BLOCK hidden equivalence**

Background/role: numerical analysis, reparameterization invariance, interpolation and inverse-CDF failure modes. Evidence inspected: analytic interval integrals and midpoint-refinement control. Strongest counter-hypothesis: H1 and H2 are merely algebraic rewrites. Attempted falsifier: insert redundant sigma-linear midpoint knots. H2 is unchanged to `1.44e-15`; H1 moves by `7.69e-4` in CDF. Residual uncertainty: spline/theory-guided alternatives are untested. Vote: **BLOCK treating interpolation choice as numerically closed physics.**

### (c) Independent statistics/UQ reviewer — **ACCEPT deterministic sensitivity / BLOCK probabilistic interpretation**

Background/role: uncertainty propagation and identifiability. Evidence inspected: exact deterministic source comparison, #1179 distinction between statistical errors/systematics/model form. Strongest counter-hypothesis: the CDF difference can be interpreted as a one-sigma uncertainty. Attempted falsifier: identify a probability law or covariance over H1/H2. None exists. Residual uncertainty: no probability weight over interpolation families and no source-bound covariance. Vote: **ACCEPT the sensitivity number; BLOCK confidence/coverage language.**

### (d) Claims/provenance reviewer — **BLOCK CL-021 promotion**

Background/role: source-to-claim mapping and reproducibility. Evidence inspected: CL-021 dependencies, current source-model sidecar, open #1178/#1179/#1182. Strongest counter-hypothesis: exact inverse-CDF closure already makes the source physically complete. Attempted falsifier: hold table/support fixed and change only defensible interpolation order; source shape changes measurably. Residual uncertainty: compiled Geant4, runtime fail-closed behavior, off-support model, source UQ, detector-chain propagation. Vote: **BLOCK physical-source/detector claim promotion.**

## Cross-atom propagation and surviving child atoms

This result is upstream of generator-level angular distributions, truth energy/path distributions, event/stave deposition, quenching, optical/WLS transport, SiPM/electronics/digitization, and any DATA/MC comparison. It does not establish that a `~1e-3` source-CDF difference is material or negligible after detector selection; that must be tested rather than assumed.

Children spawned/retained:

- source-bound interpolation family beyond H1/H2 (spline/theory-constrained only if independently justified);
- #1178 off-support completion/truncation sensitivity;
- #1179 covariance/nuisance model, kept distinct from interpolation model form;
- #1182 compiled runtime readiness/fault semantics;
- generator-only paired-seed propagation of H1/H2 once compiled execution is available;
- detector-chain propagation only after the complete response chain exists.

## Claim/wiki consequence

CL-021 remains `OPEN/GATED`. The present result is `SIMULATION_SOURCE_MODEL_SENSITIVITY`, not a detector uncertainty band. No beam ROOT data, production Geant4 campaign, detector response, B2/B8 quantity, PID, timing, penetration, energy calibration, pile-up, ESS, or DATA/MC p-value was regenerated.
