# Active Task

- **Task ID:** `ARU-MC-WEIGHT-SCALE-001 / ARU-MC-EVENT-WEIGHT-POPULATION-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T151500Z`
- **Current remote main SHA inspected:** `dcb4c12a4d7714d2f420e5ca1a61d2fb6048edbe`
- **Selected atom:** positive-common-scale invariance of the already-derived nonnegative generator-event weight population.
- **Trigger:** active PR `#1171` initially required raw binary64 `sum(w^2)` to be finite and explicitly expected `[1e154,1e154]` to fail. That contradicts the exact normalized-measure invariants `F_{cw}=F_w`, `ESS(cw)=ESS(w)`, and `max(cw)/sum(cw)=max(w)/sum(w)` for `c>0`.
- **Exact falsifiers executed:** `[1,2,7]` is accepted by the raw-moment path, but the same relative weights scaled by `1e300` fail because raw `sum(w^2)=inf`, while scaling by `1e-300` fails because raw `sum(w^2)=0`. `[1e308,1e308]` can overflow raw `sum(w)` although its normalized weights are `(1/2,1/2)`. Two minimum-positive subnormal equal weights underflow in the raw square sum. Max-scaled moments recover the same ESS/dominance in every fixture.
- **Preferred/implemented local mechanism:** `m=max(w)>0`, `u=w/m`, `S1'=math.fsum(u)`, `S2'=math.fsum(u^2)`, `ESS=S1'^2/S2'`, maximum-weight fraction `1/S1'`. Policy ID is now `nonnegative_event_measure_v2`; raw-unit `sum_w`/`sum_w2` are optional provenance (`None` when not faithfully representable), while `m,S1',S2'` are authorising moments.
- **Local execution:** isolated exact module/tests under Python 3.13.5 / NumPy 2.3.5 returned `24 passed in 0.09s` (pytest exit 0). An unrelated artifact-tool spreadsheet warmup timeout appeared on stderr and is preserved in the ARU record; it did not originate in the tested MC code.
- **Repository actions:** PR `#1171` code/tests/docs/body revised in place; new child issue `#1172` owns migration of duplicate raw-moment logic already on `main` in `tools/audit/validate_mc_weights.py`, `tools/audit/audit_mc_weight_usage.py`, and `scripts/single_stave/strict_event_weights.py`; immutable audit `2026-08-10T151500Z_ARU-MC-WEIGHT-SCALE-001.md` added.
- **Raw carrier remains unresolved:** #880/#1053 still distinguish source-proven scalar-event, common-replicated-primary, and direct-sampled/unit-weight adapters. This numerical atom does not authorize `weights[0]` or close #1169.
- **Claim state:** no production ROOT/Geant4 sample or real ESS/spectrum/p-value/detector result was regenerated. #1049/#1052/#1164/#880/#1053 remain gates; no public physics claim is promoted.
- **Next:** require fresh exact-head CI on the fully updated #1171 head. If green and mergeable, merge only #1171's bounded primitive/policy repair. Then migrate the duplicate helpers under #1172 unless immutable production source-weight bytes become available first.
- **Status:** `ACTIVE / IMPLEMENTED_PENDING_EXACT_HEAD_CI / PARTIAL`
