# Latest Handoff

## Completed atom: source-UQ × interpolation cross-atom compatibility (#1179)

Protected `main` is now `d4d174d2a1b22eca17694fcf12177404a10eb657`. PR #1190 exact head `9bfa6795b47923a754183713f8f0f8963b4d02f6` passed MC Validation CI run `31430225650`: `1460 passed, 1 skipped, 8 xfailed, 1 xpassed`, six pre-existing warnings, clean ruff, diagnostic upload and enforcement. It was squash-merged as `d4d174d2a1b22eca17694fcf12177404a10eb657`.

The exact source input remains `geant4/src_patch/sigma_pd_cm_190.txt`, 640 bytes / 28 rows, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, on 26.49–169.78 deg CM support. The explicit source-node sensitivity set remains the **NONPROBABILISTIC_ENVELOPE** `0.97 sigma_i <= sigma'_i <= 1.03 sigma_i`; neither it nor the interpolation class carries a nuisance probability law.

### Validated source-level cross-atom result

The surviving measured-support interpolation classes are `linear_node_pdf_exact_inverse_v1` and `linear_cross_section_then_jacobian_v1`. Propagating the same node box through each gives:

- current box: `+0.01430729974634637/-0.014380572923809676` CDF;
- alternative box: `+0.014310586515772328/-0.014374731878122216`;
- alternative **central** CDF: zero violation of the current-mode box on the tested 10,001-point grid;
- alternative **full box image**: extends beyond the current box by `0.0010650343985590949` upward at 39.586706 deg and `0.0002537872354466675` downward at 145.879228 deg;
- two-model/node-box union relative to current nominal: `+0.015299817076167732` at 43.168956 deg and `-0.014380572923809676` at 46.951812 deg; mean-theta range 56.02560085079668–57.5322672970398 deg.

The machine result is bound to executable code by a regression that recomputes the audit and requires exact JSON object equality with `results/research/sigma_cm_uq_interpolation_compatibility_v1.json`.

A supplemental independent local refinement (Python 3.13.5, SciPy 1.17.0, NumPy 2.3.5, no RNG) moved the principal CDF extrema by only O(10^-9): union upward `0.015299818568272061` and union downward `0.01438057665953929`. This confirms grid localisation does not affect the mechanism conclusion, but it is not a proof of global continuous-theta extrema; retain that child only if exact source-level bounds become claim-bearing.

Conditional diagonal-row-statistical references remain separate: max pointwise CDF standard uncertainty `0.0004453566889758832` current versus `0.0004435837618530407` alternative. Do not add these in quadrature with the model/node-box sensitivities without a source-bound common probability model.

### Four review votes

- **Few-nucleon source physicist — REVISE:** interpolation remains a distinct source-model assumption even though it is subdominant to this deliberately broad node-box stress set.
- **Adversarial numerical reviewer — ACCEPT discriminator / BLOCK collapse:** central-curve containment is insufficient; the alternative nuisance image escapes the current box.
- **Independent statistics/UQ reviewer — ACCEPT deterministic mechanics / BLOCK inference:** confidence, quadrature and model averaging remain undefined without covariance/model probabilities.
- **Claims/provenance reviewer — BLOCK CL-021 promotion:** runtime, support, covariance, manifest, generator and detector-chain gates remain unresolved.

### Literature/support child update

A source-side literature pass was recorded on #1178. Ermisch et al. *Phys. Rev. C* **68**, 051001 (2003), DOI `10.1103/PhysRevC.68.051001`, explicitly describes the intermediate-energy p–d cross-section campaign as covering approximately 30–170 deg CM, so the near-forward/backward 190-MeV source law is genuinely not measured by that campaign. Witała, Golak & Skibiński, *Phys. Rev. C* **110**, 024005 (2024), provides a modern Coulomb-inclusive three-nucleon Faddeev framework, but this audit did not recover or execute a source-bound 190-MeV numerical completion. Truncation, constant/endpoint extension and Coulomb/Faddeev completion therefore remain separate source universes; no extrapolation was promoted.

### Next highest-value atom: #1182 source runtime readiness

Issue #1182 is the next dependency-ready P0 atom. Existing PR #1183 contains an executable static audit but intentionally does not change production Geant4 behavior and was built on an older main. Start by reconciling it against current main without force-push or dropping unrelated work.

Required state contract:

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`

and, for every generator instance `j`, configured-source event generation must satisfy

`GenerateEvent_j(e) => readiness_j == CONFIGURED_READY`.

The implementation/review must make readiness per-instance and idempotent, check every source/stopping-table parse, make configured-source failure fatal with non-success semantics, preserve explicit `CSFile=null` as a distinct uniform proposal only if intentionally configured, and bind source/readiness/input hashes to production provenance. Exact executable/run-manager/thread-mode evidence plus compiled seeded sequential/event-parallel controls remain prerequisites for runtime authorisation.

### Claim boundary

#1179 remains open for source-bound covariance/decomposition. #1178 remains open for support/runtime/source closure. #1182 remains open for readiness. CL-021 remains `OPEN / GATED`. No beam ROOT data were opened; no production Geant4 campaign, B2/B8, PID, timing, penetration, energy, pile-up, ESS, p-value, rate, or detector-performance quantity was regenerated or promoted.
