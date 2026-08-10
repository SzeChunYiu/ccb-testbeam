# Active Task

- **Task ID:** `ARU-DATAMC-ECDF-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T115300Z`
- **Current remote main SHA:** `f023b8f01272f996e296475b0068095f48b27acf`
- **Just validated/merged:** PR `#1160` on exact head `16a2273e5b1a3c043ddc604264a5a68c1406c1ec`; MC Validation run `31385123680` succeeded; squash merge `f023b8f01272f996e296475b0068095f48b27acf`.
- **Raw provenance state:** canonical `data_side_real_beam.py::timing()` now binds every required run to one manifest row and keeps the full Uproot iteration inside the verified descriptor stream. #1149 remains open for its original S00 selected-table contract/benchmark; #993/#952/#953 and CL-001 remain unresolved/GATED.
- **Data-host blockers:** no real beam ROOT bytes are available here for the complete manifest regeneration or verification-read benchmark. Do not substitute fixture/synthetic I/O as production evidence.
- **Selected next executable atom:** `#1051` / `ARU-DATAMC-ECDF-001`, the confirmed P0 defect where `compare_data_mc` linearly interpolates weighted empirical CDFs instead of evaluating right-continuous step functions.
- **Required ECDF invariant:** `F_w(x)=sum_i w_i I(X_i <= x)/sum_i w_i`; aggregate tied support exactly, remain constant between support points, and make KS-D invariant to splitting one weighted row into identical copies with divided weight.
- **Dependencies / separation:** #1049 owns weighted-KS null/p-value calibration; #880/#1022 own weight semantics; #1027 owns ADC saturation/ties. Repair #1051 first without claiming p-value validity.
- **Status:** `ACTIVE / TRIAGED`
