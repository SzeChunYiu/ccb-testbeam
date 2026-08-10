# CL-021 — MV3 scattering-model (p+CD2 CM-angle cross-section weighting)

**Status: OPEN — hypothesis FALSIFIED; source model remains GATED.**

The exact `sigma_pd_cm_190.txt` bytes are now source-bound to Table VI of
K. Ermisch et al., *Physical Review C* **71**, 064004 (2005), DOI
`10.1103/PhysRevC.71.064004`. The repository file is the 190 MeV
centre-of-mass differential cross section `dσ/dΩ` in mb/sr versus `theta_cm`
in degrees, with the retained third column equal to the statistical
uncertainty on `dσ/dΩ`. Its SHA-256 is
`0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`,
matching the table digest recorded by the historical S21/S21b audits.

The current `ScatteringGenerator.cc` uses those central values to build a
nominal `sigma(theta_cm) * sin(theta_cm)` CDF and leaves the generated primary
weights at unity. This is the correct *campaign class* for direct target-law
sampling, and it avoids re-applying the legacy nonunit `PrimaryWeight` after
generation.

However, the current implementation is **not yet authorised as an exact draw
from the declared continuous source law**. `BuildSigmaCDF()` integrates
trapezoids between node values `sigma_i sin(theta_i)`, while
`SampleThetaCM()` linearly interpolates theta inside each cumulative interval.
That inverse makes the generated density piecewise constant inside each
interval rather than sampling the linearly varying node PDF implied by the
trapezoid construction. For the exact 28-row table, the deterministic audit in
`results/research/sigma_cm_sampler_contract_v1.json` finds a maximum CDF
self-discrepancy of `0.08486575211712302` at 13.245 degrees. The same current
algorithm assigns `0.3433322933267244` of its nominal probability outside the
measured Table-VI support of 26.49–169.78 degrees, so the support/extrapolation
model is material and must be explicit. See #1178.

The source paper also reports a 3% point-to-point systematic uncertainty and a
total systematic uncertainty below 4.5% at 190 MeV. Those systematic
components are not encoded in the three-column repository table and have not
yet been propagated through the source model. See #1179.

The earlier central-value MV3 result remains a **nonauthorising source-model
diagnostic**: B2 changed from 0.475 (uniform) to 0.253 (current CS-sampled
implementation), while the referenced data value was 0.933; B8 changed from
0.181 to 0.414, and the proton mean kinetic energy changed from about 105 to
160 MeV. Those numbers showed that replacing the uniform sampler with the
current cross-section-driven implementation did not close the B2 discrepancy.
They must not be interpreted as a detector-validated proof that the elastic
source spectrum is the unique cause while #1178/#1179 and the downstream
detector-response chain remain open.

**Re-attribution remains a hypothesis, not a validated detector conclusion.**
Forward p+d elastic kinematics can produce high-energy forward protons, whereas
the data-facing B2 population is low-energy dominated; inelastic nuclear
secondaries, the recoil-deuteron channel, Sample-I selection, source support,
and detector-response effects remain competing mechanisms.

Recommendation: keep the source table and direct-sampling campaign class, but
do **not** describe the present numerical sampler as fully “physically
correct” or close CL-021. Resolve #1053, #1178 and #1179, preserve unit event
weights for direct-sampled campaigns unless another documented factor exists,
and propagate surviving source variants only through explicitly labelled truth
studies until the detector-response chain is validated. See
`reports/scatter_cl021/REPORT.md` for the historical central-value numbers and
plots.
