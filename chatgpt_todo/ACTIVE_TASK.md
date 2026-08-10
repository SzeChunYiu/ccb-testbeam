# Active Task

- **Task ID:** `ARU-MC-WEIGHT-SCALE-001 / ARU-MC-WEIGHT-CARRIER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T153200Z`
- **Current remote main SHA inspected:** `069b1d66f1a775003b284376d71c76673136f60a`
- **Validated/merged this session:** PR `#1171` exact head `d6c08aefe8da25c890ec5e797511fa53a53e4802` passed MC Validation CI run `31403740933`; squash merge `069b1d66f1a775003b284376d71c76673136f60a` places `nonnegative_event_measure_v2` on protected `main`.
- **Closed local atom:** positive-common-scale invariance of an already-derived nonnegative event-weight population. Authorising moments are now `m=max(w)>0`, `S1'=fsum(w/m)`, `S2'=fsum((w/m)^2)`, with `ESS=S1'^2/S2'` and max-weight fraction `1/S1'`. Raw-unit `sum_w`/`sum_w2` are nonauthorising convenience provenance and may be null when binary64 cannot represent them faithfully.
- **Exact falsifiers retained:** `[1,2,7]` versus common scaling by `1e300` and `1e-300`; `[1e154,1e154]`; `[1e308,1e308]`; and equal minimum-positive subnormals. The rejected raw-moment mechanism changed software authorisation solely through overflow/underflow although the normalized event measure was unchanged.
- **Four-role result:** generator/source lead `REVISE`; adversarial numerical reviewer `BLOCK raw-moment gate`; independent statistics reviewer `ACCEPT local max-scaled contract / BLOCK inference`; claims/provenance reviewer `REVISE duplicate helpers / no physics promotion`.
- **Open child:** `#1172 / ARU-MC-WEIGHT-SCALE-001` now owns migration of duplicate raw-moment validity logic in `tools/audit/validate_mc_weights.py`, `tools/audit/audit_mc_weight_usage.py`, `scripts/single_stave/strict_event_weights.py`, and any additional claim-bearing consumers found by search.
- **Upstream blocker unchanged:** #880/#1053 still must identify the generator-mode-specific raw `PrimaryWeight` -> event-weight adapter. PR #1169 remains scientifically blocked from treating arbitrary `weights[0]` as a validated general carrier.
- **Claim state:** no production ROOT/Geant4 sample or real ESS/spectrum/p-value/PID/penetration/timing/calibration/pile-up/rate/detector result was regenerated or promoted. #1049/#1052/#1164/#880/#1053 remain gates.
- **Next highest-value atom:** if immutable production weight bytes remain unavailable, implement #1172 by consolidating duplicate nonnegative event-weight diagnostics onto the validated package primitive while preserving signed-weight semantics as a separate universe. If source bytes become available, event-wise raw-weight cardinality/equality by generator mode has higher physical information value and should pre-empt that code-only migration.
- **Status:** `ACTIVE / LOCAL_PRIMITIVE_VALIDATED_ON_MAIN / SOURCE_CARRIER_BLOCKED / MIGRATION_OPEN`
