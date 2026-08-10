# Latest Handoff

## Selected atom: source-UQ × interpolation cross-atom compatibility (#1179)

Protected `main` at the branch point is `af0c3989df0009fb74d5b820123e5c7cbcbce67f`. PR #1186 is now merged after exact-head MC Validation run `31428708910` succeeded, so the deterministic 3% node-box / conditional row-statistical sensitivity is on main. #1179 remains open because no source-bound systematic covariance/decomposition has been recovered.

### Exact contract

Input is `geant4/src_patch/sigma_pd_cm_190.txt`, 640 bytes / 28 rows, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, covering 26.49–169.78 deg CM. The normalized source CDF is `F=N/Z`, and for both surviving interpolation classes the numerator and normalization are linear in the source-node cross sections.

The explicit source-node set remains the **NONPROBABILISTIC_ENVELOPE** `0.97 sigma_i <= sigma'_i <= 1.03 sigma_i`. It has no nuisance probability law or coverage interpretation.

### New cross-atom result

The current interpolation is `linear_node_pdf_exact_inverse_v1`; the surviving comparison is `linear_cross_section_then_jacobian_v1`. On a deterministic 10,001-point measured-support grid, the alternative **central** CDF lies entirely inside the current-mode 3% box. That does not close the model-form universe: propagating the same node box through the alternative interpolation extends beyond the current-mode box by `0.0010650343985590949` upward at 39.586706 deg and `0.0002537872354466675` downward at 145.879228 deg.

The union of both interpolation classes and the same node box, relative to the current nominal source, reaches `+0.015299817076167732` in CDF at 43.168956 deg and `-0.014380572923809676` at 46.951812 deg. Its mean-theta range is 56.02560085079668–57.5322672970398 deg. These are sensitivity bounds, not confidence limits.

The alternative interpolation's own box excursions are `+0.014310586515772328` and `-0.014374731878122216`; the current values reproduce the merged #1179 result exactly at `+0.01430729974634637/-0.014380572923809676`.

Conditional diagonal-row-statistical references remain close but distinct: max pointwise CDF standard uncertainty `0.0004453566889758832` for the current interpolation versus `0.0004435837618530407` for the alternative; mean-angle standard uncertainty `0.02252797870713097` versus `0.022356857259092505` deg. Do not add these in quadrature with interpolation or node-box sensitivity because the required common probabilistic nuisance model is absent.

### Four review votes

- **Few-nucleon source physicist — REVISE:** interpolation is subdominant to the deliberately broad node-box stress set but remains a distinct source-model assumption.
- **Adversarial numerical reviewer — ACCEPT discriminator / BLOCK collapse:** central-curve containment does not imply containment of the alternative model's full nuisance image.
- **Independent statistics/UQ reviewer — ACCEPT deterministic mechanics / BLOCK inference:** no confidence, quadrature or model-averaging semantics are authorised without a source-bound covariance/model prior.
- **Claims/provenance reviewer — BLOCK CL-021 promotion:** runtime, support physics, covariance, production manifest and detector-chain gates remain open.

### Repository work

Branch `research/mc-source-uq-interpolation-compat` contains:

- `tools/audit/research_sigma_cm_uq_interpolation_compatibility.py`;
- `tests/test_sigma_cm_uq_interpolation_compatibility.py`;
- `results/research/sigma_cm_uq_interpolation_compatibility_v1.json`;
- `chatgpt_todo/archive/2026-08-10T203000Z_ARU-MC-CS-UQ-INTERPOLATION-COMPAT.md`;
- this handoff and `ACTIVE_TASK.md`.

Local equivalent execution used Python 3.13.5, no RNG, and returned `4 passed in 11.97s`. Exact-head repository CI is still required before merge.

### Child atoms / next

1. Recover source-bound covariance/decomposition or preregister explicit common/smooth/residual sensitivity families; do not invent iid 3% rows.
2. Propagate surviving source uncertainty/interpolation worlds through independently justified support models; measured-support truncation remains conditional.
3. After #1182, run compiled seeded generator-only propagation with exact source/model/seed/event manifests.
4. If the cross-model envelope becomes claim-bearing, remove the remaining finite-grid theta localisation with an analytic extremum search.

No beam ROOT data were opened, no production Geant4 campaign was generated, and no B2/B8, PID, timing, penetration, energy, pile-up, ESS, p-value, rate or detector-performance quantity was regenerated or promoted.
