# Student timing-study handoff

## What is complete

- A beginner-facing derivation from waveform samples to pair residuals and stave inference.
- A 29-plot evidence contract with explicit stop conditions.
- An executable synthetic known-answer lane that reaches a clean B4--B6 `sigma68` of about 0.100 ns and recovers injected stave terms.
- A correct-frame lane in which only B2 has pulses, demonstrating the required pulse-identity stop.
- A watermarked deliberate 8x18-to-8x16 truncation lane that reaches a central B4--B6 width of about 0.097 ns while retaining an approximately 4 ns RMS.
- A raw ROOT mode with per-event width validation, file hashes, composite event-key checks, held-out run splits and fail-closed claim gates.
- Tests for known-answer closure, artifact tails, retracted-map refusal, duplicate event identities and strict JSON.
- Fixes for both automated review findings on the historical audit: live `core_chi2_ndf` parsing and live `n_finite` row/event accounting.

## Mandatory reading order for the next session

1. `README.md`
2. `STUDENT_RAW_TIMING_WALKTHROUGH.md`
3. `student_plot_atlas.csv`
4. `student_timing_config.example.yaml`
5. `configs/channel_polarity_v2.json`, including its retraction object
6. `tools/audit/validate_hrd_waveform_contract.py`
7. `scripts/digital_cfd.py`, especially the component-identity authorization state
8. the generated raw report and `analysis_summary.json`

## Four-reviewer sign-off

For every promoted finding, record one sentence from each role:

- **DAQ/waveform:** frame, channel, polarity and sampling-time interpretation.
- **Detector timing:** physical pulse identity, TOF and timewalk interpretation.
- **Statistics:** estimand, tails, dependence, covariance and uncertainty.
- **Software/reproducibility:** event keys, provenance, tests and exact commands.

A finding remains diagnostic when any role records an unresolved blocker.

## Atomic next tasks

### S1 — Run the raw producer on the immutable 144-word source

Record file hashes, event counts and word-count distributions. Do not point the producer at a converted 128-word staging file. Save the exact YAML and software commit.

**Acceptance:** every event has 144 words; no truncation/padding; requested runs are complete; composite event keys are unique.

### S2 — Close physical pulse identity

Generate waveform atlases and duplicate-channel correlations for all eight channels and each run family.

**Acceptance:** B4, B6 and B8 each show localized, duplicate-supported pulse morphology. When the correct source shows only B2/B2-duplicate pulses, stop and mark downstream pair timing unavailable for that dataset.

### S3 — Replace heuristic component authorization

Use waveform/duplicate evidence to validate a component selector or implement a source-specific selector with tests. Keep the canonical first-local-peak status non-authorising until this closes.

**Acceptance:** selected/global amplitude and peak-sample plots show one physical component family; known multi-pulse counterexamples are rejected or classified.

### S4 — Freeze train/validation/test runs

Choose baseline window, CFD fraction, amplitude cuts and timewalk model without touching final test metrics.

**Acceptance:** the split and objective are committed before final evaluation; no event-IID bootstrap is used when run/block dependence is present.

### S5 — Produce full pair diagnostics

For every connected physical pair, save linear/log/core residuals, tails, fit diagnostics, amplitude/slope/phase dependencies and run stability.

**Acceptance:** constant corrections move medians only; event populations remain identical between stages; all plot-atlas stop conditions pass.

### S6 — Determine whether stave inference is identifiable

Use at least three connected physical staves or an independently calibrated reference. Add a covariance/common-mode model and held-out pair closure.

**Acceptance:** non-negative parameters, small pair closure residual, sensitivity to covariance assumptions, and no use of `sigma68/sqrt(2)` without a validated generative law.

### S7 — Injection/recovery and uncertainty coverage

Run bounded toy studies locally. Submit heavy optical/Geant4 studies to LUNARC only, with seeds, job manifests and immutable outputs.

**Acceptance:** recovered values and intervals close over a grid spanning jitter, common mode, timebase, timewalk, tails and run drift.

### S8 — Correct the paper and wiki

Replace the stale v2-polarity narrative with the retraction boundary and link the validated raw producer once S1--S7 close.

**Acceptance:** no 0.096/0.146 ns beam-performance statement appears without `RETRACTED ANALYSIS ARTIFACT`; no individual-stave value appears without covariance and closure evidence.

## Current authorization state

```json
{
  "historical_issue_1320_pair_timing_authorized": false,
  "historical_issue_1320_single_stave_resolution_authorized": false,
  "synthetic_student_method_closure_authorized": true,
  "raw_beam_pair_timing_authorized": false,
  "raw_beam_single_stave_resolution_authorized": false
}
```
