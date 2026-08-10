# ARU-MC-CS-SAMPLER-001 — density-scale adversarial supplement

**Parent atom:** #1178 / `ARU-MC-CS-SAMPLER-001`  
**Parent record:** `2026-08-10T173000Z_ARU-MC-CS-SAMPLER-EXACT-INVERSE.md`  
**State:** deterministic numerical child corrected on PR #1181; compiled Geant4 validation remains blocked.

During the adversarial pass over the first exact-inverse implementation, a second numerical assumption was isolated: the normalized source distribution must be invariant under positive common rescaling of all cross-section density values. The physical probability law depends only on relative density, so for any finite `c>0`,

`theta(u; c a, c b) = theta(u; a, b)`

for every interval and uniform deviate `u`.

The first quadratic implementation formed products such as `a*a` and `(b-a)(a+b)`. Although the algebra is correct in exact arithmetic, it is not representation-scale invariant in binary64: multiplying a benign interval `[1,5]` by `1e300` can overflow those intermediate products, while multiplying by `1e-300` can underflow them. That means a change of numerical units/normalization could change or invalidate the sampler despite leaving the normalized scientific measure unchanged.

The deterministic repair now divides each interval's endpoint densities by their positive maximum before evaluating the quadratic inverse. The C++ CDF builder also divides all source cross sections by the table-wide positive maximum before forming `sigma*sin(theta)` and integrating interval masses. The common positive scale cancels exactly from the normalized law while keeping the internal values bounded. Regression controls compare `[1,5]` against positive common scales `1e-300`, `1e-200`, `1e200`, and `1e300` at fixed interval mass fraction; all must recover the same local inverse within `2e-15` absolute tolerance.

A transient implementation error was also caught before merge: the first repository edit of the Python audit accidentally used the lowercase token `true` inside a Python expression. That commit would have failed at runtime. It was immediately superseded by a correction using the Python boolean `True`; no CI result or scientific conclusion was claimed from the defective intermediate commit. Preserving this failed attempt is intentional provenance: the review process found both the scientific numerical assumption and an implementation slip rather than silently erasing them.

The tracked C++ source now explicitly includes `<cmath>` for `std::isfinite`/`std::sqrt`. A further parity review found that the external `patch_scatter.py` initially generated the new `std::isfinite` calls without injecting `<cmath>` into the target checkout. That integration gap was corrected and a focused static regression requires the dependency in both tracked source and patch path.

### Sequential reviewer update

- **Source/kinematics lead — ACCEPT scale invariance as a representation invariant / REVISE source physics.** Positive density normalization cannot change a normalized angular law, but this says nothing about physical interpolation/support.
- **Adversarial numerical reviewer — REVISE first exact-inverse implementation, then ACCEPT deterministic correction / BLOCK runtime authorization.** Extreme common scaling falsified the first raw-product implementation; `<cmath>` parity falsified the first external patch revision.
- **Independent validation reviewer — ACCEPT the new deterministic negative controls / BLOCK compiled stochastic closure.** Python/static tests can decide these numerical contracts, but they do not establish generated-angle closure in a Geant4 executable.
- **Claims/provenance reviewer — ACCEPT the correction as implementation provenance / BLOCK claim promotion.** No historical or detector-facing result was regenerated.

The remaining parent blockers are unchanged: configured-source failures must fail closed rather than silently authorise a uniform source; interpolation-order/support alternatives require sensitivity treatment; #1179 owns source covariance; a real Geant4 build and seeded generator-only CDF closure are required; production manifests must serialize source table hash, interpolation/support/event-weight modes, generator commit, seed, and event count; detector-level claims remain downstream-gated.
