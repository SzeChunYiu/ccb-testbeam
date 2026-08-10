# Latest Handoff

## Selected atom: exact 190 MeV p-d cross-section source identity

Protected `main` at the branch point is `d8c80ad625f415220d92f3cbc761b570b21fe92f`. Before starting this atom, PR #1177 exact head `6f326e83c0a0b9d95ce7e99a01b332d7af7742e3` was verified against MC Validation CI run `31410543289` (`success`) and squash-merged. The current work is on branch `audit/mc-sigma-table-provenance` and is not authorising until its own exact-head CI succeeds.

### Primary-literature and byte closure

`geant4/src_patch/sigma_pd_cm_190.txt` is 640 bytes, 28 rows and SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`. That digest exactly matches the cross-section table recorded by both historical S21 and S21b.

All 28 triples match Table VI of K. Ermisch et al., *Systematic investigation of three-nucleon force effects in elastic scattering of polarized protons from deuterons at intermediate energies*, *Physical Review C* **71**, 064004 (2005), DOI `10.1103/PhysRevC.71.064004`.

The retained columns are exactly:

1. CM scattering angle `theta_cm` in degrees;
2. differential cross section `dσ/dΩ` in mb/sr;
3. statistical uncertainty on `dσ/dΩ` in mb/sr.

The measured support retained by the file is 26.49–169.78 degrees CM. The paper reports 3% point-to-point systematic uncertainty and total systematic uncertainty <4.5% at 190 MeV; those systematic terms are not encoded in the repository's three-column file.

This eliminates the previous “perhaps the table is actually lab-frame” escape hypothesis in #1053. Combined with the retained S21b 30k-event closure (`PrimaryWeight = sigma(theta_lab)`, lab-angle R² ~ 0.999999999993), the legacy source assigned a **CM cross-section table at a lab angle**. That is a confirmed frame misuse. It still does not prove the raw `PrimaryWeight` vector's event-carrier semantics for every historical product, so #880/#1053 remain open.

A new sidecar `geant4/src_patch/sigma_pd_cm_190.source.json` binds the DOI/Table-VI projection, frame, units, support, uncertainty meaning and historical digest identity. Focused tests freeze the exact 640 bytes and 28 source rows; the raw table itself is unchanged.

### Adversarial child: current direct sampler is not exact for its own declared node PDF

The current direct source has the correct high-level campaign class: it calls `SampleThetaCM()` and leaves primary event weights at unity, avoiding double-counting the target law. But the exact numerical implementation is not yet closed.

`BuildSigmaCDF()` assigns node density `p_i = sigma_i sin(theta_i)` and integrates interval masses by trapezoids. `SampleThetaCM()` then linearly interpolates theta against cumulative mass. For interval width `d` and node values `a,b`, the trapezoid construction implies a linearly varying density, but the inverse generates a constant density within that interval. The exact CDF difference is

`Delta(x) = (b-a) x (1-x/d) / (2 Z)`,

with maximum `|b-a| d/(8 Z)` at the midpoint.

For the exact 28-row table, the repository-resident deterministic audit finds:

- normalization `1.8240017962546702` under the current trapezoid construction;
- current nominal probability below measured support: `0.3394630084684921`;
- above measured support: `0.003869284858232269`;
- total outside measured support: **`0.3433322933267244`**;
- maximum CDF self-discrepancy versus the linearly varying node PDF: **`0.08486575211712302`** at 13.245 degrees.

These are deterministic software/numerical results, not Monte Carlo or detector validation. They are preserved in `tools/audit/research_sigma_cm_sampler_contract.py`, `tests/test_sigma_cm_sampler_contract.py`, and `results/research/sigma_cm_sampler_contract_v1.json`.

### Four role-separated disposition

- **Source/kinematics lead — ACCEPT table provenance / REVISE source authorization.** Full row-level primary-source match eliminates the lab-table hypothesis. Residual: interpolation/support physics and source covariance.
- **Adversarial mechanism reviewer — BLOCK exact-sampler wording.** Off-node CDF algebra falsifies equivalence of trapezoid integration plus linear-theta inversion to the linearly varying node PDF; the first interval alone gives the 0.08487 discrepancy.
- **Independent statistics/validation reviewer — ACCEPT deterministic closure / BLOCK uncertainty-free source inference.** Table identity is exact; source systematics/covariance remain absent from the generator contract.
- **Claims/provenance reviewer — REVISE CL-021 / BLOCK detector promotion.** `docs/validation/CL-021_scattering_model.md` is revised on the branch so historical B2/B8 central-value numbers remain nonauthorising diagnostics rather than proof that the current source model is fully physical.

### Issues and child atoms

- #1053 updated with exact source/frame/units/digest evidence.
- #1178 (`ARU-MC-CS-SAMPLER-001`) opened for interpolation/inverse/support semantics, analytic CDF closure and seeded generator-level validation.
- #1179 (`ARU-MC-CS-UNCERTAINTY-001`) opened for source statistical/systematic covariance and nuisance propagation.

No beam ROOT data were opened, no production Geant4 campaign was run, and no real ESS, weighted spectrum, p-value, PID, penetration, timing, energy, pile-up, rate, or detector-performance quantity was regenerated or promoted.

### Next

Require exact-head CI on this branch and merge only if the regression/lint gate passes. Then #1178 is the highest-value executable atom: make `cross_section_interpolation_mode` and `cross_section_support_mode` explicit, implement an exact/numerically controlled inverse CDF, test off-node closure, and only then run seeded generator-only MC. #1179 follows for source uncertainty. Immutable production `PrimaryWeight` carrier evidence under #880/#1053 remains a separate prerequisite for #1169's historical weighted event path.
