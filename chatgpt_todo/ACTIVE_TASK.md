# Active Task

- **Task ID:** `ARU-MC-CS-SAMPLER-001 / ARU-MC-CS-UNCERTAINTY-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T171300Z`
- **Current protected main:** `fa62e8bb6ce7de10f840ebfa016eaa40cd9f74ec`.
- **Validated/merged this session:** PR #1180 exact head `f7f987cc92e4d22792bde691224af36d9fe97e7f` passed MC Validation CI run `31412606076`; checkout, installation, ruff, unit tests, diagnostic upload, enforcement and post-job cleanup all succeeded. PR #1180 squash-merged as `fa62e8bb6ce7de10f840ebfa016eaa40cd9f74ec`.
- **Validated source-table atom:** `sigma_pd_cm_190.txt` is 640 bytes, 28 rows, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, and matches Table VI of Ermisch et al., *Phys. Rev. C* 71, 064004 (2005): CM angle [deg], `dσ/dΩ` [mb/sr], statistical uncertainty [mb/sr], support 26.49–169.78 deg. The lab-table hypothesis in #1053 is eliminated.
- **Legacy consequence:** retained S21b closure `PrimaryWeight=sigma(theta_lab)` is now a confirmed frame misuse of a CM table. #880/#1053 remain open for proposal→target and raw-to-event carrier semantics.
- **Active sampler blocker #1178:** current trapezoid-CDF + linear-theta inverse yields a piecewise-constant interval density. Exact deterministic audit on main gives max CDF self-discrepancy about `0.084865752117123` at 13.245 deg and nominal probability outside measured support about `0.34333229332672427`.
- **Active uncertainty blocker #1179:** the source reports 3% point-to-point systematic and total systematic <4.5%, but those systematic terms are not encoded or propagated.
- **Claim state:** CL-021 validation doc and historical report now carry explicit source-model gates; historical B2/B8 numbers remain nonauthorising mechanism diagnostics. No detector claim was promoted.
- **Next highest-value atom:** #1178 exact inverse-CDF/interpolation/support contract; then #1179 source uncertainty. Immutable production `PrimaryWeight` carrier evidence under #880/#1053 remains necessary before #1169 can authorize historical weighted event products.
- **Status:** `ACTIVE / SOURCE_TABLE_PROVENANCE_VALIDATED_ON_MAIN / SAMPLER_NUMERICS_BLOCKED / SOURCE_UNCERTAINTY_BLOCKED / DETECTOR_INFERENCE_BLOCKED`
