# ARU-MC-CS-TABLE-PROVENANCE-001 — 190 MeV p-d cross-section source identity

## Selected atomic universe

Bind the exact bytes consumed by the CCB elastic scattering source to a primary-literature measurand before deciding any generator-weight or sampling semantics.

Input contract: `geant4/src_patch/sigma_pd_cm_190.txt`, 640 bytes, 28 rows, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`.

Output contract: a source record specifying reaction, beam energy, frame, units, source table, support, uncertainty meanings, and historical byte identity. This atom changes provenance/claim authorization only; it does not change the raw table or generate detector data.

## Evidence inspected

Repository evidence:

- historical S21 source review and S21b weighted source/geometry audit;
- S21b `result.json`, including the exact external sigma-table SHA and 30k-event weight closure;
- current `geant4/src_patch/sigma_pd_cm_190.txt` bytes;
- current `geant4/src_patch/ScatteringGenerator.cc` direct-CDF implementation;
- `docs/validation/CL-021_scattering_model.md`;
- issues #880 and #1053;
- open PR #1169 weight/event-statistical-unit contract.

Primary literature:

- K. Ermisch et al., *Systematic investigation of three-nucleon force effects in elastic scattering of polarized protons from deuterons at intermediate energies*, Physical Review C 71, 064004 (2005), DOI `10.1103/PhysRevC.71.064004`;
- source Table VI at 190 MeV.

The 28 repository triples match the Table-VI projection `(theta_cm, dσ/dΩ, statistical uncertainty)` row-for-row. The source table uses CM angle in degrees and differential cross section in mb/sr. The paper reports 3% point-to-point systematic uncertainty and total systematic uncertainty <4.5% at 190 MeV; those systematics are not present in the repository's three-column table.

Historical identity closes exactly: the repository SHA-256 equals the sigma-table SHA recorded by both S21 and S21b.

## Competing source-identity hypotheses

1. **H1 — exact Table-VI CM `dσ/dΩ` projection.** Survives and is accepted for these exact bytes.
2. **H2 — lab-frame differential cross-section table.** Eliminated: primary-literature Table VI identifies the retained first column as `theta_cm`, and all 28 rows match.
3. **H3 — unknown/ad-hoc numerical table coincidentally named CM.** Eliminated by exact row-level primary-source match plus historical digest identity.
4. **H4 — source central values are sufficient for all quantitative source claims.** Rejected as a closure claim: source statistical/systematic uncertainty and interpolation/support modeling remain separate atoms.

Equivalent source attributions to the earlier rapid communication are not treated as independent evidence. The complete 2005 PRC article is the row-level source used for the binding.

## Equations and invariants

For a CM differential cross section, the nominal polar target density after azimuthal integration is

`p(theta_cm) ∝ (dσ/dΩ)(theta_cm) sin(theta_cm)`.

For legacy uniform-theta proposal `q(theta_cm)=1/pi`, a correct normalized-shape importance factor must be proportional to the target/proposal Radon–Nikodym ratio, hence to `sigma_cm(theta_cm) sin(theta_cm)` up to a positive common constant.

Source-byte invariant:

`SHA256(repository table) = SHA256(S21 table) = SHA256(S21b table) = 0ca33e76...89edfc`.

This immediately makes the retained S21b empirical closure `PrimaryWeight = sigma(theta_lab)` a confirmed **frame misuse of a CM table**, not an ambiguous lab-table interpretation. It still does not by itself define the raw vector-to-event adapter for every product.

## Executed deterministic child falsifier

While checking upward compatibility with the current direct sampler, the audit derived an independent numerical child atom now tracked as #1178.

`BuildSigmaCDF()` integrates trapezoids between node values `p_i=sigma_i sin(theta_i)`, but `SampleThetaCM()` linearly interpolates theta within each cumulative interval. For interval width `d` and node densities `a,b`, the implied linear-node-PDF CDF and the actually sampled piecewise-constant density differ by

`Delta(x) = (b-a) x (1-x/d)/(2 Z)`.

The maximum interval deviation is `|b-a| d/(8 Z)` at `x=d/2`.

Using the exact table:

- trapezoid normalization: `1.8240017962546702`;
- probability assigned below measured support: `0.3394630084684921`;
- probability above measured support: `0.003869284858232269`;
- total outside Table-VI support: `0.3433322933267244`;
- maximum self-consistency CDF deviation: `0.08486575211712302` at 13.245 deg.

These are deterministic numerical results, not MC or detector validation. They are preserved in `tools/audit/research_sigma_cm_sampler_contract.py`, focused tests, and `results/research/sigma_cm_sampler_contract_v1.json`.

## Four sequential AI review passes

### A. Source / kinematics lead — ACCEPT source identity; REVISE source-model authorization

Evidence inspected: exact table bytes, Table VI, source code, S21/S21b. Strongest counter-hypothesis: file name says CM but rows might be lab quantities. Attempted falsifier: full row-level comparison to the primary table. H2 failed. Residual uncertainty: interpolation/support policy and cross-section covariance. Vote: **ACCEPT provenance / REVISE source-model claim**.

### B. Adversarial mechanism reviewer — ACCEPT H1; BLOCK legacy and current overclaims

Strongest counter-hypothesis: legacy `sigma(theta_lab)` may still be physically valid because the table could be lab-frame. Primary source eliminates that escape hatch. A second adversarial pass tested whether current trapezoid CDF + linear inverse exactly samples its declared node PDF; analytic off-node closure fails. Residual: physically justified source behavior outside 26.49–169.78 deg. Vote: **BLOCK legacy weight correctness and exact-current-sampler wording**.

### C. Independent statistics / validation reviewer — ACCEPT deterministic identity; BLOCK uncertainty-free inference

The source match is exact and does not depend on statistical estimation. The source paper's pointwise statistical errors are retained in column 3, but its systematic uncertainty is not encoded. A global normalization nuisance and angle-dependent shape nuisance are observationally different for normalized source distributions. Vote: **ACCEPT identity / BLOCK quantitative uncertainty claims**.

### D. Claims / provenance reviewer — REVISE CL-021; no detector promotion

`CL-021_scattering_model.md` previously called the current sampler physically correct. That wording is too strong given the newly explicit measured support, unpropagated source systematics, and #1178 numerical mismatch. The branch revises the claim document while preserving the historical central-value numbers as nonauthorising diagnostics. Vote: **REVISE**.

## Repository actions

- verified and squash-merged coordination PR #1177 after exact-head MC Validation CI run `31410543289` succeeded; resulting main commit `d8c80ad625f415220d92f3cbc761b570b21fe92f`;
- branch `audit/mc-sigma-table-provenance` created from that main;
- added `geant4/src_patch/sigma_pd_cm_190.source.json`;
- added exact-byte/row/source-contract regression tests;
- added deterministic sampler research utility, tests, and machine-readable result;
- revised `docs/validation/CL-021_scattering_model.md` to gate exact sampler/source uncertainty claims;
- updated #1053 with the resolved table identity;
- opened child #1178 (`ARU-MC-CS-SAMPLER-001`);
- opened child #1179 (`ARU-MC-CS-UNCERTAINTY-001`).

No raw table value was edited. No ROOT beam data were opened. No Geant4 campaign was executed. No detector-performance quantity was regenerated.

## Cross-scale propagation

Micro/source-table identity now constrains generator semantics: the legacy lab-angle lookup cannot be reinterpreted as a native lab-frame table. The current direct-CDF campaign remains the correct *class* (direct target-law generation with unit event weights) but its exact numerical distribution and source nuisance envelope remain blocked by #1178/#1179.

Those source atoms propagate to generator event weights (#880/#1053), event/stave truth (#1169/#1164), DATA/MC statistical-unit compatibility (#1049), and CL-021. None may be promoted to detector closure without quenching, optical/WLS, SiPM, electronics/digitization, identical reconstruction, and held-out comparison.

## Child atoms

- #1178 — exact CM sampler interpolation/inverse/support contract.
- #1179 — cross-section statistical/systematic covariance and propagation.
- existing #880/#1053 — generator measure mode and raw-to-event weight carrier.

## Acceptance state

`ARU-MC-CS-TABLE-PROVENANCE-001`: **VALIDATED at literature/byte-contract level pending repository CI for the new regression files**. The parent source-weight/source-sampler problem is not complete.

## Next highest-value atom

#1178 is dependency-ready and has the strongest immediate information value: repair or explicitly redefine the direct CM inverse CDF, make support/extrapolation a versioned model choice, prove off-node CDF closure analytically, and only then run seeded generator-level MC. #1179 follows for source nuisance propagation. Immutable production `PrimaryWeight` carrier evidence under #880/#1053 remains required before #1169 can authorize a historical weighted event product.
