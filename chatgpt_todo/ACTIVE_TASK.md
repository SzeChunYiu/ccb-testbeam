# Active Task

- **Task ID:** AUD-G4-018
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T220759Z
- **Initial remote main SHA:** `c0a5d46d8a14bb933aa401514ee2f7408276ae0b`
- **Validated implementation/evidence head:** `768e13daa5056dd06f9b962e66b004fa5d9c4d97`
- **Scope:** remove CSV row-order dependence from stopping-power grouped sufficient statistics and make the numerical summation method explicit in machine-readable and terminal reports.
- **Confirmed defect:** repeated binary64 `+=` aggregation produced different deposited-energy sums and mass-stopping proxies for the same validated event multiset when rows were reordered.
- **Validated change:** collect deposits and track lengths per exact particle/energy group, evaluate both with `math.fsum`, record `summation_method=MATH_FSUM_PER_GROUP` in results/CSV, and print the method in terminal output.
- **Commands:** focused `py_compile`; focused pytest for order invariance, report precision, and report reproducibility; exact pre-change Git-blob reconstruction and negative control; SHA-256/blob and line-length checks.
- **Validation:** `8 passed in 0.06s`; exact old blob `79ea2767...` produced `2 failed, 1 passed`; changed Python lines are at most 100 characters; old and new Git blobs were verified.
- **Evidence:** `docs/validation/stopping_power_order_invariance_audit.md`, `stopping_power_order_invariance_validation.json`, and `stopping_power_order_invariance.svg`.
- **Boundary:** numerical aggregation is order-stable, but no real export, uncertainty budget, accepted projectile-energy-loss observable, or stopping-power closure was produced.
- **Status:** COMPLETE for `AUD-G4-018`; accepted stopping-power physics closure remains PARTIAL/BLOCKED.
