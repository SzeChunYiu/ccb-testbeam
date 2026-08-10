# ARU-MC-CS-SAMPLER-001 — exact inverse and explicit support reference

**Session stamp:** 2026-08-10T173000Z  
**Branch point:** protected `main@fa62e8bb6ce7de10f840ebfa016eaa40cd9f74ec`  
**Parent:** #1178  
**Source-uncertainty sibling:** #1179  
**Legacy weight/source dependencies:** #1053, #880  
**Claim dependency:** CL-021  
**State:** PARTIAL — deterministic numerical/source implementation complete on branch; compiled Geant4 execution, seeded generator closure, production manifest binding, alternate support sensitivity, and detector propagation remain open.

## 1. Atomic contract

Input is the exact source-bound Table-VI projection `geant4/src_patch/sigma_pd_cm_190.txt`, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, 640 bytes, 28 rows. Each row is `theta_cm` [deg], `dσ/dΩ` [mb/sr], statistical uncertainty [mb/sr], measured over 26.49–169.78 degrees CM.

For the nominal central-value reference, define node density

`p_i = sigma_i sin(theta_i)`

and linearly interpolate `p(theta)` between adjacent measured nodes. The chosen reference support is explicitly conditional on the measured Table-VI range:

`cross_section_support_mode = measured_table_support_truncate_v1`.

The numerical interpolation/inverse identity is

`cross_section_interpolation_mode = linear_node_pdf_exact_inverse_v1`.

The generator output is one sampled `theta_cm` [rad] per source event. Direct target-law sampling retains `event_weight_mode = unit_direct_sampling_v1`, i.e. event weight 1 absent an independently derived factor. The source-model identity is bound in `geant4/src_patch/scattering_source_model_v1.json`.

Scientific meaning is deliberately narrow: this is a nominal truth-level angular source reference. It is not proof that the cross section vanishes outside measured support, not a detector response, and not a detector performance claim.

## 2. Competing mechanisms / descriptions

- **H1 — exact inverse of a linearly interpolated node PDF on explicit support.** Survives and is implemented as the nominal reference.
- **H2 — legacy trapezoid masses plus linear-theta inversion.** Eliminated as an exact representation of H1. It creates a piecewise-constant density inside each interval.
- **H3 — discrete-node sampling.** Eliminated because the declared source model is continuous in angle and the table is a differential cross-section measurement at nodes, not a discrete probability mass function.
- **H4a — measured-support truncation.** Survives as the explicit fail-closed nominal reference used here; interpretation is conditional on published angular support.
- **H4b — constant-σ or endpoint-density extension.** Survives only as a sensitivity model, not as an unlabelled default. The superseded implementation effectively introduced large off-support mass without an explicit source identifier.
- **H4c — source-bound theory/Coulomb completion outside support.** Scientifically plausible and potentially important, but no repository-bound authoritative completion was established in this session. It remains a child sensitivity universe.

H4a/H4b/H4c are not averaged together: they represent different physical source assumptions. Detector agreement cannot be used to choose among them without a preregistered source-model study because that would confound source and detector response.

## 3. Equations, invariants, dimensional checks

For one interval `[theta_0,theta_1]`, width `d`, and endpoint density values `a,b >= 0`, define `x = theta-theta_0`. Linear interpolation gives

`p(x) = a + (b-a)x/d`.

The exact accumulated interval mass is

`I(x) = a x + (b-a)x^2/(2d)`

and total interval mass is

`M = I(d) = (a+b)d/2`.

For a uniform interval-mass deviate `f in [0,1]`, solve `I(x)=f M`. With `k=(b-a)/d` and `y=fM`, the numerically stable conjugate form is

`x = 2y / (a + sqrt(a^2 + 2ky))`.

The flat-density limit `a=b>0` gives `x=fd`. When `a=0,b>0`, the limit gives `x=d sqrt(f)`. Endpoints satisfy `f=0 -> x=0` and `f=1 -> x=d`.

Dimensions: `sigma` is mb/sr, `sin(theta)` is dimensionless, `dtheta` is rad (dimensionless in SI but retained as an angular integration coordinate), so only relative interval masses are used after normalization. No absolute cross section/rate is inferred from this normalized sampling law.

For the superseded algorithm, the exact CDF difference from the linear-node PDF within an interval is

`Delta(x) = (b-a) x (1-x/d)/(2 Z)`

with maximum magnitude `|b-a|d/(8Z)` at the interval midpoint.

## 4. Executed deterministic falsifiers

The exact source table was independently recomputed in the analysis runtime from its 28 numeric rows. This was deterministic arithmetic, not Monte Carlo.

Superseded algorithm:

- normalization: `1.8240017962546706` (the retained v1 artifact records the equivalent binary64 value `1.8240017962546702`);
- probability below measured support: approximately `0.339463008468492`;
- probability above measured support: approximately `0.003869284858232268`;
- total probability outside measured support: approximately `0.34333229332672427`;
- maximum CDF self-discrepancy: approximately `0.084865752117123` at 13.245 degrees, first interval.

Implemented measured-support exact reference:

- normalization: `1.1977630765144902`;
- off-support probability by declared reference definition: `0`;
- probe fractions per measured interval: `0, 0.001, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999, 1`;
- maximum recovered interval-mass-fraction error: `3.3306690738754696e-16`, at interval index 16 for requested fraction `0.99`, recovered `0.9900000000000003`.

Additional exact controls added to `tests/test_sigma_cm_sampler_contract.py`:

- flat, rising, falling, zero-left-endpoint and zero-right-endpoint PDFs;
- invalid negative, zero-mass, nonfinite and out-of-domain inverse inputs;
- exact source-table digest and measured support;
- knot-refinement invariance for the same linearly varying continuous PDF;
- static contract parity between tracked C++ source, header, and the external `patch_scatter.py` path;
- sidecar binding of table digest, interpolation mode, support mode, and unit event-weight mode.

The historical v1 result is retained rather than overwritten. The replacement result is `results/research/sigma_cm_sampler_contract_v2.json`.

## 5. Four sequential AI review passes

### Pass A — source/kinematics physicist

**Background/role:** intermediate-energy p+d elastic kinematics, differential-cross-section source construction, generator target/proposal measures.  
**Evidence inspected:** source sidecar/Table-VI identity, current `ScatteringGenerator.cc/.hh`, historical deterministic v1 audit, CL-021, issue #1178.  
**Strongest counter-hypothesis:** the old `[0,pi]` extension may approximate physically important forward/backward cross section better than truncation.  
**Attempted falsifier:** distinguish numerical exactness from support physics. Exact inverse algebra closes H1, but no source-bound off-support data/theory in the repository identifies H4a/H4b/H4c.  
**Residual uncertainty:** physical angular law outside 26.49–169.78 degrees, energy dependence around the target-loss distribution, source covariance.  
**Vote:** **ACCEPT numerical H1 implementation / REVISE physical source authorization**.

### Pass B — adversarial mechanism/numerics reviewer

**Background/role:** inverse-transform sampling, floating-point failure modes, generator fault injection and equivalence testing.  
**Evidence inspected:** exact interval equations, old CDF construction/inversion, new conjugate quadratic inverse, flat/rising/falling/endpoint fixtures, static C++/patch parity test.  
**Strongest counter-hypothesis:** trapezoid interval masses alone make the old sampler equivalent enough to the declared continuous law.  
**Attempted falsifier:** off-node interval CDF algebra. The old inverse is exactly piecewise constant and reaches a source-scale CDF discrepancy ~0.08487; equivalence is rejected. Knot-refinement control additionally distinguishes a continuous linear law from arbitrary binning.  
**Residual uncertainty:** the current repository CI does not compile this Geant4 source; malformed runtime cross-section inputs and no-CDF uniform fallback deserve an explicit fail-closed integration test in a real build.  
**Vote:** **ACCEPT deterministic replacement / BLOCK compiled-generator authorization**.

### Pass C — independent statistics/validation reviewer

**Background/role:** simulation validation, empirical-CDF tests, reproducibility, source-nuisance propagation.  
**Evidence inspected:** deterministic v1/v2 results, exact table digest, mode sidecar, test design, repository CI workflow.  
**Strongest counter-hypothesis:** deterministic formula closure is enough to validate the generated distribution.  
**Attempted falsifier:** separate mathematical inverse closure from code/runtime closure. The Python reference reaches ~3.3e-16, but the CI workflow runs Python tests only and does not compile/run the C++ Geant4 generator.  
**Residual uncertainty:** seeded generated-angle closure, compiler/library differences, production manifest serialization, source statistical/systematic nuisance law, support sensitivity.  
**Vote:** **ACCEPT deterministic numerical contract / BLOCK stochastic production validation**.

### Pass D — claims/provenance reviewer

**Background/role:** source-to-claim traceability, immutable configuration identity, claim-gate governance.  
**Evidence inspected:** CL-021, source sidecar, new source-model sidecar, #1053/#1178/#1179 dependencies, historical B2/B8 diagnostic wording.  
**Strongest counter-hypothesis:** fixing the inverse is sufficient to call the scattering source “physically correct.”  
**Attempted falsifier:** propagate the local fix upward. Physical source support, source covariance, generator compilation/run provenance, detector-response chain, and real DATA↔MC closure all remain open.  
**Residual uncertainty:** all of those parent/child gates.  
**Vote:** **REVISE CL-021 only; BLOCK detector/source-physics promotion**.

## 6. Micro → meso → event → study → claim propagation

Micro numerical step: interval inverse is now mathematically consistent with its declared continuous node interpolation.

Meso source model: nominal central-value support is explicit and no longer silently extends to `[0,pi]`. This removes one hidden model choice but introduces an explicit truncation assumption that remains a sensitivity child.

Event level: direct-sampled campaigns still require exactly one immutable source-event identity and unit analysis weight under this source mode. #880/#1053 remain relevant for historical nonunit-weight products; this branch does not retroactively reinterpret them.

Study level: historical CL-021 B2/B8 central-value diagnostics were produced with the superseded support/inverse implementation and are not regenerated here. They cannot be reused as numerical results for the new source model.

Claim level: CL-021 stays GATED. No detector or beam-data claim is promoted.

## 7. Child atoms / unresolved assumptions

1. **Compiled generator closure:** build the modified Geant4 source, record compiler/Geant4 version and source hashes, and run a seeded generator-only sample. Compare the empirical angle CDF to the exact declared reference with predetermined finite-sample tolerance. This session cannot honestly execute it because the available GitHub CI does not compile `geant4/src_patch` and no configured Geant4 runtime is available in this execution environment.
2. **Runtime invalid-source fail-closed behavior:** configured cross-section parse/CDF failure currently needs explicit production semantics rather than silently becoming a scientifically different uniform source. Test missing/malformed/nonfinite/nonmonotonic tables in a compiled generator.
3. **Support-model sensitivity:** compare the measured-support conditional reference to source-bound extrapolation/theory completions without tuning on detector agreement.
4. **Source uncertainty:** #1179 must define statistical/systematic nuisance covariance and propagation.
5. **Production provenance:** generator output/run manifest must serialize table SHA-256, interpolation mode, support mode, event-weight mode, generator commit, seed, event count and relevant configuration.
6. **Detector propagation:** only after source variants survive truth-level checks should they enter the Geant4 deposition→quenching→optical→SiPM→electronics→data-like reconstruction chain.

## 8. Repository actions in this branch

- replace the tracked C++ source numerical inverse/support implementation;
- retain node PDF state in the header;
- make the external `patch_scatter.py` reproduce the same semantics;
- expand deterministic audit and regression suite;
- add v2 machine-readable result while preserving v1 defect provenance;
- add `scattering_source_model_v1.json` mode/digest sidecar;
- revise CL-021 so numerical closure is not conflated with physical support closure;
- update coordination/handoff and #1178 after PR creation.

No raw beam data, production MC ROOT file, production Geant4 campaign, detector-response result, ESS, p-value, PID, penetration, timing, energy, pile-up, rate or performance metric was regenerated in this atom.
