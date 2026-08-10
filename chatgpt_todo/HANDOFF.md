# Latest Handoff

## Completed atom

- **Task:** `ARU-DATAMC-ECDF-001` / issue #1051
- **Validated head:** `b8f9c6a363f9a2a7f658978641392f76605c9a46`
- **CI:** MC Validation run `31387574136` completed successfully; lint passed and the full non-integration suite reported `1329 passed, 1 skipped, 8 xfailed, 1 xpassed`.
- **Merged:** PR #1162 -> `97386889c1820e45b6ce04ba7ddfbda7128f2f46` on protected `main`; #1051 auto-closed.

## Validated local contract

`compare_data_mc.py` v5 now represents the weighted empirical distribution as

`F_w(x) = sum_i w_i I(X_i <= x) / sum_i w_i`

with unique tied support and right-continuous step evaluation. `D = sup_x |F_data(x)-F_MC(x)|` is evaluated exactly on the union of support values. The old piecewise-linear `np.interp` mechanism is eliminated. Regression controls include the exact `[0,1]` midpoint falsifier, direct indicator-sum oracle, all-tied and saturated/quantized fixtures, weighted-row splitting/merging invariance, tie-order invariance, and independent equal-weight agreement with `scipy.stats.ks_2samp(...).statistic`.

## Four final review votes

- **Statistical-method lead — ACCEPT observed-statistic closure.** The finite empirical step-function `D` now matches the declared mathematical object; no statement is made about its weighted null distribution.
- **Adversarial mechanism reviewer — ACCEPT local D / BLOCK inferential p-value.** Representation, tie ordering and interpolation pseudo-mass are eliminated as mechanisms; the legacy value-permutation null remains invalid for non-uniform MC weights.
- **Independent statistics/validation reviewer — ACCEPT deterministic software/statistic closure.** Exact-head CI and two independent oracles validate the implemented observed statistic, not type-I calibration or detector physics.
- **Claims/provenance reviewer — REVISE downstream products / no claim promotion.** Output v5 marks the retained numerical p-value `NONAUTHORISING_BLOCKED_ISSUE_1049`, plots display it as blocked, and real DATA/MC products must be regenerated before corrected `D` values are quoted.

## Evidence boundary

No real beam ROOT bytes or campaign comparison outputs were available in this runtime. Therefore no real DATA/MC `D`, p-value, PID, penetration, timing, energy, pile-up, or detector-performance result was regenerated or promoted. #1027 still governs the physical meaning of ADC saturation/ties; #1022 still governs weight propagation in canonical DeltaE-E/penetration analyses.

## Next highest-value atom

Proceed to **#1049 / `ARU-WKS-NULL-001`**. The current numerical p-value shuffles pooled values and replaces the original weighted design with unit weights, so it is non-authorising even though observed `D` is now correct. The next research session should first define the concrete null and statistical unit from the actual DATA/MC sampling design, preserve PrimaryWeight semantics documented under #880, include the fitted MeV->ADC scale as a nuisance fitted from the same comparison chain, then choose and validate a design-consistent resampling/calibration law with explicit type-I simulations and tie/saturation stress tests. Do not assume iid rows, fixed scale, or signed-weight semantics without evidence.
