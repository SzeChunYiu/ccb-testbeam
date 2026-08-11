# Latest Handoff

## Component-bound first-local-peak CFD crossing

Selected atom: `ARU-TIMING-CFD-COMPONENT-CROSSING-BINDING-001`, child of #1059 and canonical timing primitive #1063; #968 remains the microscopic late-component/pile-up mechanism parent.

### Live repository state

The atom was selected from protected `main@ed1cea48e3b68bad8c30b7970cb2355cef94d02d`, the merge of Lane05 Wave-A PR #1239. During this review, main advanced independently to `f350ad9ed824fff7c5cd9500d7c592f6a287fb21` via optical PR #1246. Draft PR #1250 incorporated that exact main without force-push by moving the audit branch forward to GitHub-signed merge commit `0fe20aab80932783c1bf945a4b01e393602dc0e6`; its parents are current-main `f350ad9...` and audit head `982899c...`.

#1059 remains open and its real-data/mechanism acceptance criteria remain unmet. Do not mark #1250 ready or merge until every required protected context on its exact final head is green; use an expected-head guard if it reaches merge readiness.

### Atomic contract

For baseline/polarity-corrected waveform `y[s]`, selected local peak sample `p`, selected amplitude `A_p`, and CFD fraction `f`, define `T=f*A_p`. A component-bound crossing is the nearest pre-peak rising bracket

`y[k] < T <= y[k+1]`, `k+1 <= p`,

with

`t = k + (T-y[k])/(y[k+1]-y[k])`.

If no sample before `p` is below threshold, the selected rise is left-censored and returns `NO_CROSSING_IN_WINDOW`/NaN. Earlier activity above `T` does not itself imply censoring if the trace subsequently returns below `T` before the selected rise. `global_max` remains a separate estimator with the historical whole-waveform first-crossing rule.

### Why #1239 was not sufficient

The merged `first_local_peak` implementation selected only an amplitude. `cfd_time_samples()` then rescanned from sample 0, so a bump explicitly rejected by the peak selector could still define the time.

Deterministic fixture A:

`[0,40,0,50,100,50,0,0,500,1000,500]`.

Global maximum 1000 gives the existing 5% selector floor of 50. The 40-ADC bump is rejected; the first selected local peak is 100 at sample 4. CFD20 has `T=20`. The old implementation returned `t=0.5` from the rejected bump; the selected component's own 2→3 bracket gives `t=2.4` samples.

Adversarial fixture B forced a revision of the first repair draft:

`[30,0,50,100,50,0,250,500,250]`.

Sample 0 is above the selected peak's CFD20 threshold, but the waveform returns below threshold at sample 1 before the selected rise. The selected-component crossing is therefore observed at `t=1.4`; reusing the global sample-0 left-censor rule was rejected.

### Implementation and executed tests

Branch: `audit/cfd-component-bound-crossing`.

- `scripts/digital_cfd.py`: internal peak selection now returns both amplitude and peak index; `first_local_peak` searches backward from that peak for the nearest below-threshold sample and interpolates the following bracket. Public amplitude helper and `global_max` semantics are retained.
- `tests/test_cfd_component_binding.py`: five deterministic controls for rejected-bump binding, component-relative censoring recovery, clean single-pulse equivalence, genuine selected-component left-censoring, and global estimator non-regression.
- Exact repository blob identities were re-established before isolated execution: source `4aa845e2cb41c96cf70f010f135758e8fb94f5ae`, tests `00a686df5a83690caabb51751bd8ace9d72d0c50`.
- Environment: Python 3.13.5, NumPy 2.3.5, pytest 9.0.2, Linux 6.18.35 x86_64. Focused exact-blob command `python -m pytest -q /tmp/ccb_exact/tests/test_cfd_component_binding.py` returned `5 passed in 0.07s`.
- Stable concern `CCB-1059-COMPONENT-CROSSING-BINDING-001` added to existing #1059; no duplicate issue.
- Immutable record: `chatgpt_todo/archive/2026-08-11T215500Z_ARU-TIMING-CFD-COMPONENT-CROSSING-BINDING-001.md`.

No random seed is involved in these deterministic fixtures. The focused execution is a software/estimator oracle, not detector measurement or a substitute for protected CI.

### Four sequential AI reviews

**Timing/estimator lead — detector timing, digital CFD, censoring semantics: ACCEPT same-component contract / BLOCK detector-truth interpretation.** Evidence is the exact canonical source plus #1059/#1239. The counter-hypothesis that amplitude relabeling alone fixes component identity is falsified by fixture A. Real-waveform peak identity remains open.

**Adversarial waveform reviewer — multipulse/noise/pile-up stress tests: first draft REVISE; corrected draft ACCEPT bounded semantics conditional on CI.** Fixture B falsified global sample-0 censoring in a component-bound estimator. Overlap without a below-threshold valley remains unresolved.

**Independent validation reviewer — estimator identifiability and held-out validation: ACCEPT exact-blob deterministic oracle / BLOCK timing-resolution inference.** Five exact-blob tests passed, but synthetic fixtures do not establish component-assignment accuracy or run/stave transfer on CCB data.

**Claims/provenance reviewer — traceability and claim-ledger governance: ACCEPT bounded repair / BLOCK #1059 completion and timing-claim promotion.** The parent still requires real-data fraction/component transition decomposition, stable-component validation and ambiguous-pulse governance.

### Child atoms / next work

Highest-value next child after exact-head CI is `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001`. The current selector uses `y[j] >= 0.05*global_max`; despite the argument name `min_prominence_frac`, this is an amplitude floor, not topographic prominence. It introduces a new uncalibrated component-assignment assumption that must be tested against noise, overlap, saturation and domain shift.

Other surviving children: `ARU-TIMING-CFD-OVERLAP-BASIN-001`, `ARU-TIMING-CFD-REALDATA-TRANSITION-001`, `ARU-TIMING-CFD-TRUTH-TRANSFER-001`, and regeneration/audit of every downstream report that consumes the changed `first_local_peak` estimator.

### Claim boundary

No immutable beam bytes, production Geant4/MC population, timing-resolution number, pile-up rate/mechanism, WLS response, PID result, rate, ESS, p-value or detector-performance claim was regenerated or promoted. #1059 remains OPEN and public timing claims remain gated.
