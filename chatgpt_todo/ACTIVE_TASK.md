# Active Task

- **Task ID:** `ARU-MC-WEIGHT-SCALE-001 / ARU-MC-WEIGHT-CARRIER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T155100Z`
- **Current remote main SHA inspected:** `b12cc42d54cdb649f81f8d9b1001c130f85f9afe` (PR #1173 post-merge coordination).
- **Selected atom:** #1172 migration of duplicate nonnegative weight diagnostics/normalized estimators onto validated `nonnegative_event_measure_v2`.
- **Implementation branch:** `fix/weight-diagnostic-scale-invariance`, based on `main@b12cc42d54cdb649f81f8d9b1001c130f85f9afe`.
- **Implemented:** `tools/audit/audit_mc_weight_usage.py` and `scripts/single_stave/strict_event_weights.py` delegate the nonnegative event-measure contract to the package primitive. The strict normalized weighted mean/median/fraction/correlation paths now use `w/max(w)` rather than reopening raw total-weight overflow after validation. Raw `sum_w`/`sum_w2` are optional provenance; authorising scaled moments/ESS/dominance are explicit.
- **Exact falsifiers added:** `[1,2,7]` with common scales `1`, `1e300`, `1e-300`; `[1e154,1e154]`; `[1e308,1e308]`; equal minimum-positive subnormals; ordinary-range compatibility; NaN/negative/all-zero/shape/alignment failures; JSON `allow_nan=False`.
- **Repository search consequence:** `tools/audit/validate_mc_weights.py` is signed-weight-capable and is not equivalent to the nonnegative probability measure. Dedicated child #1174 (`ARU-MC-WEIGHT-SIGNED-001`) now owns its source/estimand/numerical contract. Legacy `scripts/mc01_trigger_split_truth.py` also contains raw-weight arithmetic, but its arbitrary `PrimaryWeight[0]` plus unit fallback is upstream-blocked by #880/#1053 and is not certified by this numerical migration.
- **Four-role result:** generator/source lead `REVISE`; adversarial numerical reviewer `ACCEPT H2 / BLOCK raw-moment H1`; independent statistics reviewer `ACCEPT local deterministic closure / BLOCK inference`; claims/provenance reviewer `REVISE helpers/docs / BLOCK physics promotion`.
- **Upstream blocker unchanged:** #880/#1053 still must identify the generator-mode-specific raw `PrimaryWeight` → event-weight adapter. PR #1169 remains scientifically blocked from treating arbitrary `weights[0]` as a validated general carrier.
- **Claim state:** no production ROOT/Geant4 sample or real ESS/spectrum/p-value/PID/penetration/timing/calibration/pile-up/rate/detector result was regenerated or promoted. #1049/#1052/#1164/#880/#1053 remain gates.
- **Next gate:** open a focused PR, run exact-head CI, repair any regression, and merge only if protected-branch checks pass. Then determine whether any retained production report changes when immutable production weights are available.
- **Status:** `ACTIVE / IMPLEMENTED_ON_BRANCH / CI_PENDING / SOURCE_CARRIER_BLOCKED / SIGNED_CHILD_OPEN`
