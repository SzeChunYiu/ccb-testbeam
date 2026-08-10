# Latest Handoff

## Signed-weight numerical contract research (#1174)

Protected `main` is `368ad62bc5b0f776ded077dbed9a5f22288896e1`. In this session PR #1175 was merged only after exact-head MC Validation CI run `31408060880` succeeded with `1379 passed, 1 skipped, 8 xfailed, 1 xpassed`; that merge closes the bounded nonnegative helper migration while leaving signed/source semantics separate.

The new atom is signed-weight diagnostics. For `m=max|w|`, `u=w/m`, define `S=sum u`, `A=sum |u|`, `Q=sum u^2`. The locally surviving descriptive decomposition is `S^2/Q` (signed ESS-like), `A^2/Q` (absolute ESS), dominance `1/A`, cancellation severity `1-|S|/A`, and orientation `sign(S)`.

Deterministic fixtures established three concrete defects in the legacy signed-capable helper semantics: `[-1,-2]` produces legacy cancellation `2.0`; the legacy `n_positive==0` predicate labels the same nonzero signed vector as all-zero; and a signed normalized cumulative mass can be nonmonotone/outside `[0,1]`, so it cannot be reused as the probability ECDF used by DATA↔MC comparison.

The exact `[10,-9,1]` rational oracle is `S=2`, `A=20`, `Q=182`, signed ESS-like `2/91`, absolute ESS `200/91`, dominance `1/2`, cancellation severity `9/10`. Positive common scales `1e300` and `1e-300` preserve the dimensionless diagnostics under max-absolute scaling. A `1e308`-scale fixture makes legacy raw absolute/squared moments unrepresentable while the scaled diagnostics remain defined.

Repository work on branch `fix/signed-weight-diagnostic-contract` adds an executable research utility, `13` focused regression/falsifier tests, a machine-readable result, and an immutable ARU record. This is deliberately nonauthorising: no production CCB generator file was available to establish whether negative weights exist, why they would exist, or what signed target measure they represent.

Four-role result: generator/source lead **BLOCK authorising use / ACCEPT diagnostic research**; adversarial reviewer **REJECT legacy cancellation and all-zero semantics**; statistics reviewer **ACCEPT local decomposition / BLOCK generic ESS inference**; claims/provenance reviewer **BLOCK CCB signed-weight claims**.

Next gate: require exact-head CI on the research PR. After that, the highest-information physical task remains #880/#1053 immutable generator-mode evidence (file hash, config, event-wise sign/cardinality, source adapter and target measure). Production repair of `validate_mc_weights.py` should not close #1174 until that source contract and downstream consumer compatibility are explicit.
