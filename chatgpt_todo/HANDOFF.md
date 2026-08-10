# Latest Handoff

## Validated signed-weight numerical research; production source semantics still blocked

Protected `main` is now `45c7cbd1fa84768db7086dea56bc74336e906b9d`. Two bounded changes were validated and merged this session. PR #1175 migrated the nonnegative helper paths to `nonnegative_event_measure_v2` after exact-head MC Validation CI run `31408060880` reported `1379 passed, 1 skipped, 8 xfailed, 1 xpassed`; squash merge `368ad62bc5b0f776ded077dbed9a5f22288896e1`. PR #1176 added nonauthorising signed-weight research after run `31409887721` reported `1392 passed, 1 skipped, 8 xfailed, 1 xpassed`; squash merge `45c7cbd1fa84768db7086dea56bc74336e906b9d`.

### Signed atom result

For a future source-authorized signed event-weight vector, use `m=max|w|`, `S=sum(w/m)`, `A=sum(|w|/m)`, `Q=sum((w/m)^2)` to separate descriptive quantities with different meanings: signed ESS-like `S^2/Q`, absolute ESS `A^2/Q`, dominance `1/A`, cancellation severity `1-|S|/A`, and signed-mass orientation `sign(S)`.

The deterministic falsifiers are now repository-resident. Exact `[10,-9,1]` gives signed ESS-like `2/91`, absolute ESS `200/91`, dominance `1/2`, and cancellation severity `9/10`; positive common scales `1e300` and `1e-300` preserve the dimensionless diagnostics. All-negative `[-1,-2]` exposes two production-helper semantic defects: legacy `1-S/A` reports `2.0`, and `n_positive==0` falsely maps a nonzero all-negative vector to `ALL_ZERO_WEIGHTS`. Exact cancellation `[1,-1]` gives signed ESS-like `0` but absolute ESS `2`. `x=[0,1,2], w=[1,-2,2]` yields normalized cumulative signed mass `[1,-1,1]`, eliminating reuse of signed weights as the ordinary probability ECDF.

A further source/API mismatch is recorded on #1174: `validate_mc_weights.py` publishes a policy string saying `NONNEGATIVE`, while its default `require_nonnegative=False` path intentionally permits mixed signed weights with a nonblocking finding. This must be resolved explicitly rather than hidden behind a generic policy label.

### Scientific/source boundary

No immutable production CCB file was inspected that demonstrates negative weights. #1053 currently identifies the relevant CCB generator-measure worlds as a legacy positive cross-section-like `PrimaryWeight` and a direct-`sigma*sin(theta)` sampler intended to use unit event weight. Generic MC@NLO literature establishes that negative event weights can exist in other generator classes, but does not establish their presence in this repository's production campaign.

`compare_data_mc.py` remains explicitly nonnegative (`require_nonnegative=True`) and its weighted ECDF rejects negative weights. Signed research must not broaden that probability-measure boundary. If the shared validator later becomes scale-stable for extreme nonnegative vectors, migrate the comparison script's local weighted median/ECDF/histogram arithmetic in the same transaction; otherwise a vector could pass validation and fail/change semantics during consumption.

### Four review votes

- Generator/source-physics lead: **BLOCK authorising signed use / ACCEPT diagnostic research**. Residual: immutable generator mode, sign prevalence, raw adapter and target measure.
- Adversarial mechanism reviewer: **REJECT legacy cancellation/all-zero semantics**. `[-1,-2]` is the direct falsifier.
- Independent statistics reviewer: **ACCEPT local descriptive decomposition / BLOCK generic ESS inference**. Exact cancellation proves net signed signal and absolute sampling mass are distinct.
- Claims/provenance reviewer: **BLOCK CCB signed-weight claims and any probability-CDF promotion**. The research artifacts are software/numerical evidence only.

### Next

Highest-information work is #880/#1053 on immutable representative generator files: record file/tree/schema hashes, generator commit/config/table provenance, event-wise `PrimaryWeight` cardinality/sign/equality, primary PDG/TrackID ordering, source adapter ID, and target measure. If those production bytes remain inaccessible, the next bounded code leaf is #1174 production-semantic cleanup: correct misleading signed diagnostics/policy text while keeping the path explicitly nonauthorising unless source semantics justify it. #1049 remains the inferential/null-calibration gate.
