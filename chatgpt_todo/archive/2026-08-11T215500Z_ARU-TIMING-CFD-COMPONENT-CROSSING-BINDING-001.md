# ARU-TIMING-CFD-COMPONENT-CROSSING-BINDING-001

Status: `PARTIAL` pending protected exact-head CI and downstream real-data validation.
Parents: #1059, #1063; microscopic mechanism parent #968.
Clean integration base: protected `main@f350ad9ed824fff7c5cd9500d7c592f6a287fb21`.

## Contract

For waveform `y[s]`, selected local peak `(p,A_p)`, CFD fraction `f`, and `T=f A_p`, `first_local_peak` timing must use the nearest pre-peak rising bracket

`y[k] < T <= y[k+1]`, with `k+1 <= p`,

and

`t = k + (T-y[k])/(y[k+1]-y[k])`.

If no pre-peak sample is below `T`, the selected rise is left-censored and must return `NO_CROSSING_IN_WINDOW`/NaN. Earlier above-threshold activity is not by itself left-censoring if the waveform subsequently returns below threshold before the selected rise. `global_max` remains a distinct whole-waveform first-crossing estimator.

This atom validates estimator self-consistency, not the detector-truth identity of the selected local peak.

## Mechanisms and equivalence

H1 clean unimodal pulse: global-first-crossing and selected-component crossing collapse to the same estimator.

H2 earlier rejected noise/subthreshold activity; H3 earlier physical pulse/pile-up; H4 delayed/recovery/electronics activity: all can generate an earlier threshold excursion and are observationally indistinguishable at this software atom. They remain separate microscopic universes under #968 and detector-response parents.

H5 `global_max` CFD remains intentionally distinct on multi-component waveforms.

## Deterministic falsifiers

Fixture A: `[0,40,0,50,100,50,0,0,500,1000,500]`. Global max 1000 makes the existing 5%-of-global selector floor 50. The 40-ADC bump is rejected; the first selected peak is 100 at sample 4; CFD20 has `T=20`. Pre-repair code returned `t=0.5` from the rejected bump. Same-component interpolation uses samples 2→3 and returns `t=2.4`.

Fixture B: `[30,0,50,100,50,0,250,500,250]`. The selected peak is 100 at sample 3, `T=20`. Although sample 0 is above threshold, sample 1 returns below threshold before the selected rise, so the selected crossing is observed at `t=1.4`; this falsified the first repair draft's reuse of global sample-0 censoring.

Negative controls: clean `[0,50,100,50,0]` gives 0.4 for both estimators; no pre-peak below-threshold sample gives genuine left-censoring; `global_max` preserves its historical first crossing.

No RNG is used.

## Implementation / provenance

Clean branch `audit/cfd-component-bound-crossing-v2` starts from exact `main@f350ad9ed824fff7c5cd9500d7c592f6a287fb21` and contains only this timing repair, its focused tests, and this immutable archive. The earlier draft PR #1250 became unsuitable after a base-lineage merge polluted its changed-file set; it is to be superseded rather than force-pushed.

Exact runtime blobs:
- `scripts/digital_cfd.py`: Git blob `4aa845e2cb41c96cf70f010f135758e8fb94f5ae`;
- `tests/test_cfd_component_binding.py`: Git blob `00a686df5a83690caabb51751bd8ace9d72d0c50`.

Both blobs were reconstructed byte-for-byte and verified with `git hash-object` before isolated execution. Environment: Python 3.13.5, NumPy 2.3.5, pytest 9.0.2, Linux 6.18.35 x86_64. Command:

`python -m pytest -q /tmp/ccb_exact/tests/test_cfd_component_binding.py`

Result: `5 passed in 0.07s`.

This is exact-blob deterministic software evidence, not detector validation and not a replacement for protected GitHub CI.

Stable concern `CCB-1059-COMPONENT-CROSSING-BINDING-001` was added to existing #1059 rather than opening a duplicate issue.

## Four review passes

### Timing/estimator lead — digital CFD and censoring
Evidence: exact #1239 source, #1059 contract, fixtures A/B.
Counter-hypothesis: changing only the amplitude reference is enough to define prompt-component timing.
Falsifier: fixture A still timed a rejected earlier component.
Residual: selected peak may still be the wrong detector component.
Vote: `ACCEPT` same-component contract / `BLOCK` detector-truth interpretation.

### Adversarial waveform reviewer — multi-pulse/noise/pile-up stress
Evidence: first repair draft plus fixture B.
Counter-hypothesis: old sample-0 censoring transfers unchanged.
Falsifier: fixture B has a below-threshold valley before the selected rise.
Residual: overlapping components with no valley remain unresolved.
Vote: first draft `REVISE`; corrected semantics `ACCEPT` conditional on exact-head CI.

### Independent statistics/validation reviewer — identifiability and held-out transfer
Evidence: five exact-blob deterministic tests; no beam population or detector simulation.
Counter-hypothesis: synthetic closure validates timing performance.
Falsifier: fixtures contain no run clustering, waveform-domain transfer or truth labels.
Residual: real-data prevalence/bias and truth-transfer accuracy.
Vote: `ACCEPT` deterministic oracle / `BLOCK` timing-resolution inference.

### Claims/provenance reviewer — scientific state/traceability
Evidence: #1059 remains open with unmet real-data acceptance criteria.
Counter-hypothesis: this bounded repair closes the parent.
Falsifier: peak-selection identifiability, real-data transition decomposition, ambiguous-component governance and downstream regeneration remain unresolved.
Residual: inventory of post-#1239 studies consuming `first_local_peak`.
Vote: `ACCEPT` bounded repair / `BLOCK` #1059 completion and timing-claim promotion.

## Children

- `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001`: current `0.05*global_max` criterion is an uncalibrated amplitude floor, not topographic prominence.
- `ARU-TIMING-CFD-OVERLAP-BASIN-001`: components without a below-threshold separator.
- `ARU-TIMING-CFD-REALDATA-TRANSITION-001`: run/stave/amplitude/topology transition matrix on immutable real data.
- `ARU-TIMING-CFD-TRUTH-TRANSFER-001`: held-out digitized MC/injection component assignment.
- downstream regeneration/audit for reports consuming the changed estimator.

No beam timing resolution, pile-up mechanism/rate, WLS response, PID, ESS, p-value or detector-performance claim is promoted. #1059 remains OPEN.
