# Active Task

- **Task ID:** `ARU-MC-WEIGHT-SIGNED-001 / ARU-MC-WEIGHT-CARRIER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T163000Z`
- **Current remote main SHA inspected:** `368ad62bc5b0f776ded077dbed9a5f22288896e1`.
- **Validated/merged this session:** PR #1175 exact head `de7c5c1c09390c305deee1e53cae22c34f428ce5` passed MC Validation CI run `31408060880` (`1379 passed, 1 skipped, 8 xfailed, 1 xpassed`) and was squash-merged as `368ad62bc5b0f776ded077dbed9a5f22288896e1`.
- **Selected new atom:** #1174 signed-weight numerical semantics, with no assumption that CCB production actually contains negative weights.
- **Executed falsifiers:** exact rational `[10,-9,1]`; common scales `1e300/1e-300`; all-negative `[-1,-2]`; exact cancellation `[1,-1]`; binary64 large/subnormal boundaries; signed cumulative-mass counterexample `[1,-2,2]`.
- **Finding:** legacy `1-S/A` can report `2.0` for all-negative weights, while the legacy `n_positive==0` validation predicate misclassifies an all-negative vector as all-zero. A signed cumulative measure is also not a probability ECDF.
- **Surviving local description:** max-absolute scaled `S,A,Q`, bounded cancellation severity `1-|S|/A`, separate signed-mass orientation, distinct signed ESS-like `S^2/Q` and absolute ESS `A^2/Q`.
- **Research branch:** `fix/signed-weight-diagnostic-contract`; focused local research tests `13 passed`.
- **Scientific boundary:** no production ROOT/Geant4 file was opened; signed-weight prevalence/source semantics remain blocked by #880/#1053; #1049 inference remains blocked.
- **Status:** `ACTIVE / NUMERICAL_RESEARCH_EXECUTED / PRODUCTION_SOURCE_BLOCKED / CI_PENDING`
