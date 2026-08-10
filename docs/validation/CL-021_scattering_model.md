# CL-021 — MV3 scattering-model (p+CD2 CM-angle cross-section weighting)

**Status: OPEN — hypothesis FALSIFIED; source model remains GATED.**

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

The source paper also reports a 3% point-to-point systematic uncertainty and a
total systematic uncertainty below 4.5% at 190 MeV. Those systematic
components are not encoded in the three-column repository table and have not
yet been propagated through the source model. See #1179.

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

Recommendation: keep the source table and direct-sampling campaign class, keep
unit event weights for direct-sampled campaigns unless another documented
factor exists, and use the exact-inverse measured-support law only as an
explicitly labelled nominal truth reference. Do **not** close CL-021 until
#1053, #1178 and #1179 are resolved, the modified Geant4 source is actually
compiled and exercised with seeded generator-level closure, source mode IDs and
table hash are serialized in production provenance, and surviving source
variants are propagated through the validated detector-response chain. See
`reports/scatter_cl021/REPORT.md` for the historical central-value numbers and
plots.
