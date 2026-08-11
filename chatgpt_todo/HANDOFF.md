# Latest Handoff

## Component-bound first-local-peak CFD crossing

Selected atom: `ARU-TIMING-CFD-COMPONENT-CROSSING-BINDING-001`, child of #1059/#1063; #968 remains the microscopic late-component/pile-up mechanism parent.

### Repository state

The clean integration branch `audit/cfd-component-bound-crossing-v2` starts from exact protected `main@f350ad9ed824fff7c5cd9500d7c592f6a287fb21`. Draft PR #1259 supersedes #1250. #1250 was closed unmerged because incorporating a concurrently advanced main through a non-force merge made the PR include unrelated optical-lane changes; it was not force-rewritten or merged. #1259 was recreated from the new exact main and contains the timing atom plus audit/coordination only.

#1059 remains OPEN and no precision-timing claim is authorised by this child alone.

### Exact estimator contract

For waveform `y[s]`, selected peak sample `p`, selected amplitude `A_p`, CFD fraction `f`, and threshold `T=f*A_p`, `first_local_peak` timing must use the nearest pre-peak rising bracket

`y[k] < T <= y[k+1]`, `k+1 <= p`,

with

`t = k + (T-y[k])/(y[k+1]-y[k])`.

If no sample before `p` is below `T`, the selected rise is `NO_CROSSING_IN_WINDOW`/NaN. Earlier above-threshold activity is not itself selected-component censoring if the trace later returns below `T` before the selected rise. `global_max` remains a separate historical whole-waveform first-crossing estimator.

### Discriminators

Fixture A: `[0,40,0,50,100,50,0,0,500,1000,500]`. Global max 1000 gives the existing 5% selector floor 50. The 40-ADC bump is rejected; the first admitted local peak is 100 at sample 4; CFD20 has `T=20`. Before repair the returned time was `0.5` from the rejected bump. Same-component interpolation uses samples 2→3 and gives `2.4` samples.

Fixture B forced an adversarial revision: `[30,0,50,100,50,0,250,500,250]`. Sample 0 is above the selected peak's threshold, but the waveform returns below threshold at sample 1 before the selected rise. Therefore the selected crossing is observed at `t=1.4`; global sample-0 censoring was rejected for this component-bound estimator.

Clean single-pulse equivalence, genuine selected-rise left-censoring, and `global_max` non-regression are separate negative controls.

### Executed evidence

Exact repository blobs were reconstructed and verified with `git hash-object` before isolated execution:

- `scripts/digital_cfd.py`: `4aa845e2cb41c96cf70f010f135758e8fb94f5ae`;
- `tests/test_cfd_component_binding.py`: `00a686df5a83690caabb51751bd8ace9d72d0c50`.

Environment: Python 3.13.5, NumPy 2.3.5, pytest 9.0.2, Linux 6.18.35 x86_64. Exact focused command `python -m pytest -q /tmp/ccb_exact/tests/test_cfd_component_binding.py` returned `5 passed in 0.07s`. No RNG. This is deterministic software evidence only.

Protected GitHub MC Validation must still pass for every required context on the exact final #1259 head before readiness or merge. Earlier CI heads and the focused local test are not substitutes.

### Mechanism review

Clean unimodal pulses collapse global-first and selected-component crossing to the same estimator. Earlier rejected noise, true earlier pile-up/particle activity, and delayed/recovery/electronics structure are observationally indistinguishable at this atom; #968 and detector-response atoms retain microscopic ownership. The repair does not establish that the selected first local peak is detector truth.

### Four sequential AI reviews

**Timing/estimator lead — digital CFD and censoring:** `ACCEPT` same-component contract / `BLOCK` detector-truth interpretation. Fixture A falsifies amplitude-only component relabeling.

**Adversarial waveform reviewer — multipulse/noise/pile-up:** first draft `REVISE`; corrected semantics `ACCEPT` conditional on exact-head CI. Fixture B falsifies unconditional sample-0 censoring. Overlap without a below-threshold separator remains unresolved.

**Independent statistics/validation reviewer — identifiability and held-out transfer:** `ACCEPT` exact-blob deterministic oracle / `BLOCK` timing-resolution inference. Five focused tests pass, but there are no immutable CCB waveforms, truth labels, run-clustered estimates, or held-out detector-domain comparisons in this atom.

**Claims/provenance reviewer — traceability and claim governance:** `ACCEPT` bounded repair / `BLOCK` #1059 completion and public timing-claim promotion. The authorising real-data script defaults to `first_local_peak`, so affected results must be regenerated after the estimator changes rather than inherited from the old implementation.

### Children / next atom

Highest-value child is `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001`: current `min_prominence_frac` is actually a 5%-of-global amplitude floor plus a local-maximum condition, not topographic prominence. Noise, overlap, saturation, baseline residuals, sampling phase and data/MC domain shift can therefore change which component is selected.

Also open: `ARU-TIMING-CFD-OVERLAP-BASIN-001`, `ARU-TIMING-CFD-REALDATA-TRANSITION-001`, `ARU-TIMING-CFD-TRUTH-TRANSFER-001`, and downstream report/claim regeneration.

### Claim boundary

No beam timing resolution, pile-up mechanism/rate, WLS timing law, PID result, rate, ESS, p-value or detector-performance quantity was produced or promoted. #1059 remains OPEN/PARTIAL.
