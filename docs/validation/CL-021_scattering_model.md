# CL-021 — MV3 scattering-model (p+CD2 CM-angle cross-section weighting)

**Status: CENTRAL_VALUE_ONLY — primary source covariance unavailable (blocker preserved per #1179).**

The exact `sigma_pd_cm_190.txt` bytes are source-bound to Table VI of
K. Ermisch et al., *Physical Review C* **71**, 064004 (2005), DOI
`10.1103/PhysRevC.71.064004`. The repository file is the 190 MeV
centre-of-mass differential cross section `dσ/dΩ` in mb/sr versus `theta_cm`
in degrees, with the retained third column equal to the statistical
uncertainty on `dσ/dΩ`. Its SHA-256 is
`0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`,
matching the table digest recorded by the historical S21/S21b audits.

The direct-sampling campaign class uses those central values to construct a
nominal polar-angle density proportional to `sigma(theta_cm) * sin(theta_cm)`
and leaves generated primary event weights at unity. This avoids re-applying
the legacy nonunit `PrimaryWeight` after generation.

The tracked source now makes the central-value numerical law explicit as
`cross_section_interpolation_mode=linear_node_pdf_exact_inverse_v1` and
`cross_section_support_mode=measured_table_support_truncate_v1`. Between
measured Table-VI nodes it linearly interpolates the node density
`p_i = sigma_i sin(theta_i)`, integrates each interval by its exact trapezoid
mass, and analytically inverts that linearly varying density inside the chosen
interval. The deterministic contract audit in
`results/research/sigma_cm_sampler_contract_v2.json` closes the tested
interval-mass fractions to a maximum absolute error of
`3.3306690738754696e-16`. The corresponding measured-support normalization is
`1.1977630765144902` in the code's numerical integration units.

This fixes the previous **numerical self-inconsistency**, but it does not solve
the source-support physics. The older implementation assigned
`0.3433322933267244` of its nominal probability outside the measured Table-VI
support of 26.49–169.78 degrees and differed from its own linearly varying node
PDF by as much as `0.08486575211712302` in CDF at 13.245 degrees. The new
reference instead conditions the nominal central-value distribution on the
measured support, so its off-support probability is exactly zero **by declared
model definition**, not because the experiment established a zero physical
cross section outside the measured angles. Truncation, defensible extrapolation
and any source-bound theory/Coulomb completion remain competing support models
under #1178 and must be propagated as source-model sensitivity before a
physical source claim is promoted.

The between-node interpolation itself is also a model-form assumption. The
surviving `linear_cross_section_then_jacobian_v1` alternative interpolates the
published `dσ/dΩ` first and then multiplies by `sin(theta)`. It agrees at every
published cross-section node and on support, but its normalized CDF differs from
the current reference by at most `0.0010129801982659559`; its mean `theta_cm`
is lower by `0.024267831224125052` degrees. The source paper does not prescribe
one of these between-node rules, so this is deterministic model sensitivity,
not a confidence band or evidence that either interpolation is uniquely
physical.

The source paper reports a 3% point-to-point systematic uncertainty and total
systematic uncertainty below 4.5% at 190 MeV. Section IV D explains that the
point-to-point term was introduced as an extra per-point error until a
high-order polynomial fit to the measured angular cross section reached
approximately unit chi-square, after discussing target-thickness variation and
background-subtraction systematics. The paper does not provide a row covariance
matrix, so the 3% term must not silently be reinterpreted as 28 independent
Gaussian nuisances.

`results/research/sigma_cm_source_uncertainty_v1.json` therefore separates
source facts from explicit model-dependent sensitivity. A fully common 4.5%
scale control changes the normalized source CDF by no more than
`3.3306690738754696e-16`, confirming that pure normalization cancels from the
shape. As a deliberately **nonprobabilistic** stress envelope, allowing every
central `sigma_i` independently to range over `[0.97, 1.03] sigma_i` gives a
maximum upward CDF excursion `0.01430729974634637` and downward excursion
`0.014380572923809676` on a 10,001-point measured-support scan, both near
46.951812 degrees. The nominal source mean `theta_cm` is
`56.78396200051643` degrees; the same box permits
`56.050251002153615`–`57.5322672970398` degrees. These bounds are a sensitivity
model, not a confidence interval and not an inferred covariance.

The interpolation and source-node universes do not collapse into one another.
`results/research/sigma_cm_uq_interpolation_compatibility_v1.json` propagates
the same explicit 3% node box through both surviving interpolation classes.
The alternative central curve lies inside the current-mode box on the tested
10,001-point grid, but its **full propagated box** extends beyond the current
box by `0.0010650343985590949` upward near 39.586706 degrees and
`0.0002537872354466675` downward near 145.879228 degrees. The union of both
interpolation classes and the same node box, measured relative to the current
nominal source, reaches `+0.015299817076167732` in CDF near 43.168956 degrees
and `-0.014380572923809676` near 46.951812 degrees; the mean-angle union is
56.02560085079668–57.5322672970398 degrees. This union is a deterministic
cross-model sensitivity set, not a probability distribution, and it must not be
added in quadrature with statistical uncertainties.

For the retained third-column statistical uncertainties only, a separate
first-order diagonal delta-method reference gives a maximum pointwise CDF
standard uncertainty `0.0004453566889758832` near 49.488045 degrees and a
mean-angle standard uncertainty `0.02252797870713097` degrees for the current
interpolation. Under the alternative interpolation these become
`0.0004435837618530407` and `0.022356857259092505` degrees. Those calculations
are conditional on independent row statistical errors and do not replace the
missing systematic covariance. #1179 remains open for a defensible nuisance
model and generator/downstream propagation.

The earlier central-value MV3 result remains a **nonauthorising source-model
diagnostic**: B2 changed from 0.475 (uniform) to 0.253 (the superseded direct-CS
implementation), while the referenced data value was 0.933; B8 changed from
0.181 to 0.414, and the proton mean kinetic energy changed from about 105 to
160 MeV. Those numbers showed that replacing the uniform sampler with that
cross-section-driven implementation did not close the B2 discrepancy. They
must not be interpreted as a detector-validated proof that the elastic source
spectrum is the unique cause while #1178/#1179 and the downstream detector-
response chain remain open. They also have not been regenerated with the new
explicit support/interpolation modes.

**Re-attribution remains a hypothesis, not a validated detector conclusion.**
Forward p+d elastic kinematics can produce high-energy forward protons, whereas
the data-facing B2 population is low-energy dominated; inelastic nuclear
secondaries, the recoil-deuteron channel, Sample-I selection, source support,
and detector-response effects remain competing mechanisms.

**Recommendation (2026-08-14):** The regenerated 100k campaign (`cmc_100k_regenerated_20260814`) is bound as central-value-only with explicit declaration at
`geant4/uncertainty/cmc_100k_regenerated_20260814_source_systematics_declaration.json`.
The source table is source-bound, the sampler mode (direct CDF inverse) is validated,
and source-node sensitivity is quantified (PR #1190). However, primary source covariance
remains unavailable, so no propagated source-systematic campaign exists. CL-021 remains
CENTRAL_VALUE_ONLY; detector-level claims must not assert source-systematic propagation.
See the declaration for authorized vs prohibited claims and the preserved blocker path.
