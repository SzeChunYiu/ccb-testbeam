# Active Task

- **Task ID:** `ARU-DATAMC-ECDF-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T121900Z`
- **Current remote main SHA at branch start:** `4c8cebefe077f081f182eafd34d6b20e8d4ac067`
- **Selected atom:** issue `#1051`, the P0 weighted-ECDF implementation defect in `scripts/compare_data_mc.py`.
- **Implementation branch / PR:** `fix/data-mc-right-continuous-ecdf` / `#1162`.
- **Implemented observed-statistic invariant:** `F_w(x)=sum_i w_i I(X_i <= x)/sum_i w_i`, with unique tied support, right-continuous step evaluation, and exact KS-like `D = sup_x |F_data(x)-F_MC(x)|` evaluated on the union of support points.
- **Discriminating controls added:** `[0,1]` midpoint counterexample; direct indicator-sum oracle; all-tied and ADC-saturation-like support; row splitting/merging invariance; tie permutation invariance; equal-weight agreement with `scipy.stats.ks_2samp(...).statistic`; invalid-measure fail-closed tests.
- **Inference boundary:** the numerical legacy permutation p-value is explicitly `NONAUTHORISING_BLOCKED_ISSUE_1049`; this branch repairs the observed EDF distance only and does not claim calibrated goodness-of-fit probability.
- **External-data boundary:** no beam ROOT bytes or campaign MC outputs are available here, so no real DATA<->MC discrepancy table is regenerated and no detector-performance claim changes.
- **Current gate:** exact-head GitHub MC Validation CI is required after all branch handoff commits; do not merge #1162 or close #1051 on stale CI.
- **Status:** `ACTIVE / IMPLEMENTED_PENDING_CI`
