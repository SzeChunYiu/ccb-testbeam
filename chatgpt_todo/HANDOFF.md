# Latest Handoff

## Selected atom: 190 MeV p-d source uncertainty (#1179)

Protected `main` at the branch point is `f5f96951c3f56986769a16cd53ab8e23dee3e287`. The deterministic exact-inverse measured-support central-value sampler from #1178 is already on main. This session does **not** reopen that numerical defect; it asks what uncertainty law can legitimately be attached to the 28 source nodes.

### Source-bound input and scientific meaning

The exact table is `geant4/src_patch/sigma_pd_cm_190.txt`, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, 640 bytes, 28 rows, CM support 26.49–169.78 degrees. The third column is the absolute statistical uncertainty on `dσ/dΩ` in mb/sr. The primary source is K. Ermisch et al., *Physical Review C* 71, 064004 (2005), DOI `10.1103/PhysRevC.71.064004`, Table VI.

At 190 MeV the paper reports 3% point-to-point systematic uncertainty and total systematic uncertainty below 4.5%. Section IV D explains that the point-to-point term is an additional error introduced until a high-order polynomial fit to the angular cross section obtains approximately unit chi-square after discussing target-thickness variation and background-subtraction systematics. The paper does not publish a 28×28 covariance matrix in the retained data. Therefore an iid 3% Gaussian row model is an **additional assumption**, not a source fact.

### Equations and mechanism separation

The nominal source shape is

`p(theta|sigma) = g(theta;sigma)/Z(sigma)`

with linearly interpolated node densities `g_i=sigma_i sin(theta_i)` on measured support. For fixed theta,

`F(theta;sigma) = (a(theta)·sigma)/(b·sigma)`.

This makes a bounded nodewise sensitivity exactly linear-fractional at each fixed theta. A common scale `sigma -> c sigma` cancels from normalized shape; angle-dependent distortions do not. Global-normalization parameterizations are therefore one equivalence class for shape, while smooth/angular/local residual modes remain distinct.

### Executed results

New branch: `research/mc-source-uncertainty-envelope`.

Added `tools/audit/research_sigma_cm_source_uncertainty.py`, tests, `results/research/sigma_cm_source_uncertainty_v1.json`, source-sidecar semantics, CL-021 update and immutable ARU record.

Independent local deterministic environment: Python 3.13.5, `/opt/pyvenv/bin/python`, Linux 6.18.35 x86_64/glibc 2.41; no RNG. A focused local subset returned `4 passed` in 26.92 s. Exact-head repository CI is still required before merge.

Results from the exact table/model:

- nominal normalization `1.19776307651449`;
- nominal mean theta_cm `56.78396200051643 deg`;
- fully common +4.5% scale: max normalized-CDF change `3.3306690738754696e-16`;
- nonprobabilistic independent-node ±3% box, 10,001-point theta scan:
  - CDF upward excursion `0.01430729974634637`;
  - downward excursion `0.014380572923809676`;
  - both peak near `46.951812 deg`;
  - mean-angle range `56.050251002153615–57.5322672970398 deg`;
- alternating ±3% node controls: CDF sup shifts `0.0014567989868344983` and `0.0014569781233605278`;
- conditional diagonal statistical reference: max pointwise CDF standard uncertainty `0.0004453566889758832` near `49.488045 deg`; mean-angle standard uncertainty `0.02252797870713097 deg`.

The ±3% box is `NONPROBABILISTIC_ENVELOPE`: no confidence level or coverage is attached. The diagonal statistical result is conditional on independent row statistics and does not replace systematic covariance.

### Four sequential review votes

- **Few-nucleon source physicist — REVISE.** Common normalization cancels for shape, but experimental angular systematic correlations and support uncertainty are unresolved.
- **Adversarial mechanism reviewer — BLOCK invented iid covariance.** The same 3% marginal allowance permits shape effects differing by about an order of magnitude between tested correlation patterns.
- **Independent statistics/validation reviewer — ACCEPT deterministic mechanics / BLOCK coverage claim.** Linear-fractional extrema and conditional delta method are valid for their declared models; they do not identify the physical covariance.
- **Claims/provenance reviewer — BLOCK CL-021 promotion.** #1179, #1178 support sensitivity, #1182 compiled/runtime readiness, production manifest binding and downstream detector response remain open.

Full reasoning is archived at `chatgpt_todo/archive/2026-08-10T185000Z_ARU-MC-CS-UNCERTAINTY.md`.

### Coordination hazard

Open PR #1184 is stale relative to current main: its actual diff is now only comment/include reordering, and the proposed comment says the inverse-CDF change is “fixing the MV3 scattering-model residual (CL-021)”. That claim is too strong while #1179/#1182/support/runtime/detector gates remain. Do not merge that wording as scientific closure.

### Next

Require exact-head CI for the source-uncertainty research PR. Keep #1179 open even if the deterministic research lands. Highest-value follow-up is to recover any source-bound covariance/decomposition; if unavailable, preregister a transparent nuisance family (common normalization + smooth angular modes + bounded residual) and propagate it through a compiled fail-closed generator after #1182. In parallel, #1178 support-model sensitivity is likely a larger source uncertainty than the 3% table term and must remain separate.

No beam ROOT data were opened, no production Geant4 campaign was run, and no detector-level result, ESS, p-value, PID, penetration, timing, energy, pile-up or rate claim was regenerated.
