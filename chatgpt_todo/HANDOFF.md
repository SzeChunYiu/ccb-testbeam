# Latest Handoff

## Selected atom: exact inverse-CDF and explicit source support (#1178)

Protected `main` at the branch point is `fa62e8bb6ce7de10f840ebfa016eaa40cd9f74ec`, where PR #1180 already bound `sigma_pd_cm_190.txt` to Ermisch et al. Table VI and gated CL-021. The current bounded implementation is on branch `fix/mc-sigma-exact-inverse-support`; do not treat it as merged or runtime-validated until its own exact-head CI passes.

### Exact input/output contract

Input is the 640-byte, 28-row 190 MeV p-d CM differential-cross-section table, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, measured over 26.49–169.78 degrees CM. The nominal source-law node density is

`p_i = (dσ/dΩ)_i sin(theta_i)`.

The branch declares three stable source-model IDs:

- `cross_section_interpolation_mode = linear_node_pdf_exact_inverse_v1`;
- `cross_section_support_mode = measured_table_support_truncate_v1`;
- `event_weight_mode = unit_direct_sampling_v1`.

These are bound with the table digest in `geant4/src_patch/scattering_source_model_v1.json`.

### Mechanism eliminated and replacement equation

The superseded `BuildSigmaCDF()` used trapezoid interval masses but `SampleThetaCM()` interpolated theta linearly in cumulative probability. Therefore each interval was sampled with constant density even though its CDF had been constructed from a linearly varying node PDF. For interval width `d`, endpoint densities `a,b`, and local coordinate `x`, the declared linear law has

`I(x) = a x + (b-a)x^2/(2d)`

with total mass `M=(a+b)d/2`. For requested local mass fraction `f`, the replacement solves `I(x)=fM` using the stable conjugate form

`x = 2 y / (a + sqrt(a^2 + 2 k y))`,

where `k=(b-a)/d` and `y=fM`.

The old deterministic audit is preserved as v1: maximum CDF self-discrepancy ~`0.084865752117123` at 13.245 degrees and ~`0.343332293326724` nominal probability outside measured support. The replacement v2 reference uses measured nodes only, has normalization `1.1977630765144902`, and reaches maximum tested interval-mass-fraction error `3.3306690738754696e-16` over flat/rising/falling/endpoint and every-table-interval off-node controls.

### Support semantics are still a physics gate

`measured_table_support_truncate_v1` is a deliberate conditional reference, not a statement that the physical cross section is zero outside 26.49–169.78 degrees. The previous hidden `[0,pi]` extension is removed from the nominal source because it was neither source-bound nor negligible, but truncation versus an authoritative extrapolation/theory/Coulomb completion remains a distinct sensitivity universe inside #1178. It must not be chosen by tuning to detector agreement.

### Four role-separated review votes

- **Source/kinematics physicist — ACCEPT numerical inverse / REVISE source authorization.** Exact Table-VI input and interval algebra are closed; off-support physics and source covariance are not.
- **Adversarial numerical reviewer — ACCEPT deterministic replacement / BLOCK runtime authorization.** The old sampler is analytically falsified and knot-refinement controls support the continuous linear law, but repository CI does not compile this Geant4 C++ and invalid-source fallback still needs compiled fault tests.
- **Independent statistics/validation reviewer — ACCEPT deterministic contract / BLOCK stochastic validation.** Python/reference closure is machine-testable; a seeded generator-only empirical-CDF test in an actual Geant4 build remains absent.
- **Claims/provenance reviewer — REVISE CL-021 / BLOCK promotion.** The source-model sidecar improves traceability, but support sensitivity, #1179 uncertainty, production manifest serialization and the detector-response chain remain unresolved.

The full evidence, equations, counter-hypotheses and child atoms are preserved in `chatgpt_todo/archive/2026-08-10T173000Z_ARU-MC-CS-SAMPLER-EXACT-INVERSE.md`.

### Repository changes on the branch

`ScatteringGenerator.cc/.hh` now retain node-PDF state and analytically invert the linearly varying density on measured support. `patch_scatter.py` is updated to reproduce those semantics in the external Geant4 checkout. The deterministic research utility now reports both the frozen legacy defect and the implemented reference, with v2 machine-readable output and expanded regression controls. `docs/validation/CL-021_scattering_model.md` explicitly separates numerical closure from support physics. The v1 defect result remains immutable provenance.

### What remains blocked

The current GitHub Actions MC Validation workflow runs Python tests/lint but does **not** compile `geant4/src_patch`. Therefore even a green PR check only validates deterministic/source-level contracts, not C++ build/runtime. Keep #1178 open until a real Geant4 build records source/Geant4/compiler hashes and a fixed seed/event count, generated `theta_cm` is compared against the declared reference, malformed/missing/nonfinite/nonmonotonic source inputs are fault-tested, and the production manifest serializes table SHA, interpolation/support/weight modes, generator commit, seed and event count. #1179 separately owns source statistical/systematic covariance. #1053/#880 remain relevant to historical nonunit `PrimaryWeight` products.

No beam ROOT data were opened, no production Geant4 campaign was generated, and no real ESS, weighted spectrum, p-value, PID, penetration, timing, energy, pile-up, rate or detector-performance quantity was changed.

### Next

Open the bounded PR, require exact-head MC Validation CI, inspect its diff for C++/external-patch parity, and merge only if the available gate succeeds while preserving the explicit runtime blocker. After that the next executable atom is a compiled seeded generator-only closure for #1178 if a Geant4 environment is available; otherwise #1179 source covariance/support sensitivity is the highest-value analytical leaf. Historical event-weight carrier evidence under #880/#1053 remains independent and must not be inferred from the new unit-weight direct-sampling mode.
