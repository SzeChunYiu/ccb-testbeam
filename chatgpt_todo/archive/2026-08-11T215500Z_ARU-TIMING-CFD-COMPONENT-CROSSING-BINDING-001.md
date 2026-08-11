# ARU-TIMING-CFD-COMPONENT-CROSSING-BINDING-001

Status: `PARTIAL` pending exact-head CI and downstream real-data validation.
Parent atoms: #1059, #1063. Mechanism parent: #968.
Selected from protected `main@ed1cea48e3b68bad8c30b7970cb2355cef94d02d` after #1239 merged the Lane05 Wave-A timing-chain contract changes.

## Atomic input/output contract

Input: one baseline/polarity-corrected waveform `y[s]` in ADC-like analysis units; CFD fraction `f` with `0<f<1`; `amplitude_mode=first_local_peak`; existing selector floor `alpha=0.05` of the global maximum.

State: selected local peak sample `p` and amplitude `A_p`; threshold `T=f A_p`.

Output: selected-component CFD crossing time in sample units plus status. The returned crossing must be the nearest pre-peak rising bracket satisfying

`y[k] < T <= y[k+1]`, with `k+1 <= p`,

followed by linear interpolation

`t = k + (T-y[k])/(y[k+1]-y[k])`.

If no pre-peak sample is below `T`, the selected rise is left-censored and the output is `NO_CROSSING_IN_WINDOW`/NaN. Earlier above-threshold activity does not itself imply censoring if the waveform subsequently drops below `T` before the selected peak.

`global_max` remains a separate estimator with its historical whole-waveform first-crossing semantics.

Scientific meaning: estimator self-consistency only. The selected local maximum is not thereby established as the detector-truth particle/component.

## Competing mechanisms / equivalence classes

H1 clean unimodal pulse: global-first-crossing and selected-component crossing are observationally equivalent.

H2 earlier rejected noise/subthreshold bump plus selected prompt pulse: old implementation could use H2 for the returned time while using the later selected pulse for the threshold amplitude.

H3 earlier physical pulse/pile-up followed by the selected peak: numerically equivalent to H2 at this atom.

H4 late correlated-noise/recovery/electronics structure: can create the same multi-component morphology; mechanism identity remains under #968/#1032 and detector-response parents.

H5 explicit `global_max` CFD: not equivalent on multi-component waveforms and intentionally retained as a separately named estimator.

H2-H4 are collapsed here because waveform-only threshold geometry cannot identify their microscopic source.

## Deterministic falsifiers

Fixture A:

`[0,40,0,50,100,50,0,0,500,1000,500]`

Global max is 1000, so the existing 5% selector floor is 50. The 40-ADC bump at sample 1 is rejected; the first selected local peak is 100 at sample 4. CFD20 gives `T=20`. The pre-repair implementation rescanned from sample 0 and returned `t=0.5` from the rejected bump. The same-component bracket is sample 2→3 and gives `t=2+20/50=2.4` samples.

Fixture B exposed an error in the first repair draft:

`[30,0,50,100,50,0,250,500,250]`.

The selected peak is 100 at sample 3 and CFD20 has `T=20`. Sample 0 is above threshold, but sample 1 is below threshold before the selected rise. Therefore the selected component is not left-censored; the observed 1→2 bracket gives `t=1.4`. This rejected a naive reuse of the global sample-0 censor rule.

Negative controls: a clean `[0,50,100,50,0]` pulse must give 0.4 samples for both `global_max` and `first_local_peak`; a selected rise with no pre-peak below-threshold sample must remain left-censored; explicit `global_max` must preserve historical first-crossing behavior.

No RNG is used in these fixtures.

## Implementation provenance

Branch: `audit/cfd-component-bound-crossing` from exact `main@ed1cea48e3b68bad8c30b7970cb2355cef94d02d`.

Implementation lineage:
- `c7fc3841bfd6852ee360fd85132f37f45b8ab3f1`: first same-component crossing implementation.
- `8edf6dd43a2150edb07eb54364126db95f4a2967`: initial rejected-bump and negative controls.
- `de89f17225e865519c7ad267561ba571f4fc5c97`: adversarial correction making censoring component-relative.
- `5bf05d4a0ab7fa901cbfca5ab1ee18db51cc8b43`: added component-relative censoring and genuine-censor controls.

Draft PR: #1250. Stable concern/comment added to existing #1059 as `CCB-1059-COMPONENT-CROSSING-BINDING-001`; no duplicate issue opened.

## Executed exact-blob local discriminator

The final implementation/test blobs were fetched from GitHub and reconstructed byte-for-byte in an isolated execution directory. Before running the tests, `git hash-object` was required to reproduce the repository blob identities exactly:

- `scripts/digital_cfd.py` expected and observed Git blob SHA-1: `4aa845e2cb41c96cf70f010f135758e8fb94f5ae`;
- `tests/test_cfd_component_binding.py` expected and observed Git blob SHA-1: `00a686df5a83690caabb51751bd8ace9d72d0c50`.

Execution environment: Python `3.13.5`, NumPy `2.3.5`, pytest `9.0.2`, Linux `6.18.35-x86_64-with-glibc2.41`. Exact focused command:

`python -m pytest -q /tmp/ccb_exact/tests/test_cfd_component_binding.py`

Result: `5 passed in 0.07s`.

This validates only the deterministic component-binding software oracle on the exact two repository blobs. It is not a replacement for protected repository CI and is not detector/beam validation.

Protected exact-final-head CI is still required before merge; no CI PASS is claimed unless the final PR head completes every required context.

## Four sequential review passes

### 1. Timing/estimator lead — detector timing, digital CFD and censoring semantics
Evidence: merged #1239 implementation, canonical `scripts/digital_cfd.py`, existing Lane05 tests, #1059 contract.
Strongest counter-hypothesis: changing only the amplitude reference is sufficient to define a prompt-component CFD.
Falsifier: Fixture A shows the time still came from a rejected earlier component.
Residual uncertainty: whether the selected first local maximum corresponds to the desired detector component on real waveforms.
Vote: `ACCEPT` same-component estimator contract / `BLOCK` detector-truth interpretation.

### 2. Adversarial waveform-mechanism reviewer — multi-pulse, noise, baseline and pile-up stress tests
Evidence: first repair draft plus Fixtures A/B.
Strongest counter-hypothesis: the original `y[0]>=T` left-censor rule can be reused unchanged.
Falsifier: Fixture B has early above-threshold activity followed by a below-threshold valley and an observed selected rise.
Residual uncertainty: overlapping components without a below-threshold valley are not resolved by this reduced model.
Vote: first draft `REVISE`; corrected component-relative draft `ACCEPT` bounded algorithm semantics conditional on CI.

### 3. Independent statistics/validation reviewer — estimator identifiability and held-out validation
Evidence: deterministic equations, exact-blob five-test execution, and negative controls; no real-data population or detector simulation involved.
Strongest counter-hypothesis: synthetic closure is sufficient to validate precision timing.
Falsifier: synthetic fixtures establish software semantics only; they contain no run clustering, waveform-domain transfer, or detector truth.
Residual uncertainty: real-data component-transition prevalence and timing bias, plus held-out MC/injection transfer.
Vote: `ACCEPT` deterministic oracle / `BLOCK` timing-resolution inference.

### 4. Claims/provenance reviewer — scientific traceability and claim-ledger governance
Evidence: #1059 remains open with unmet real-data acceptance criteria; #1239 changed the canonical timing primitive.
Strongest counter-hypothesis: this leaf can close #1059 because component switching is now reduced.
Falsifier: peak-selection identifiability, real-data transition decomposition, ambiguous-component handling and downstream result regeneration remain unresolved.
Residual uncertainty: which reports/figures have already consumed the post-#1239 `first_local_peak` estimator.
Vote: `ACCEPT` bounded software repair / `BLOCK` #1059 completion and public timing-claim promotion.

## Cross-scale compatibility and claim consequences

Micro/algorithm: selected threshold and crossing are now designed to reference one selected peak.
Waveform/meso: unresolved when multiple components overlap without a below-threshold separator, and the 5%-of-global peak-selection law is not calibrated.
Event/study: no immutable CCB waveform population was processed in this atom.
Claim: no timing resolution, pile-up rate, B2 mechanism, WLS response, PID, or detector-performance value is regenerated or promoted. Any downstream result using `first_local_peak` must be regenerated after the algorithm changes and must remain gated by #1059/#968 and timing-selection parents.

## Child atoms

- `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001`: the 5%-of-global local-peak acceptance rule is itself an unvalidated component selector and is not a topographic-prominence estimator.
- `ARU-TIMING-CFD-OVERLAP-BASIN-001`: define behavior when component rises overlap and no below-threshold valley separates them.
- `ARU-TIMING-CFD-REALDATA-TRANSITION-001`: measure component/fraction-transition matrices by run, stave, amplitude and topology on immutable real data.
- `ARU-TIMING-CFD-TRUTH-TRANSFER-001`: quantify component assignment and timing bias on held-out digitized MC/injections with known component identity.
- downstream regeneration leaf for every report/claim that consumed the post-#1239 first-local-peak estimator.

Next highest-value atom after exact-head CI: `ARU-TIMING-CFD-PEAK-SELECTION-IDENTIFIABILITY-001`.
