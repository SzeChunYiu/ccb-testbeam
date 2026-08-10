# ARU-S00-SELECTOR-IDENTITY-REAUDIT

## Session identity

- Stamp: `2026-08-10T030000Z`
- Initial remote main: `37ed6aa792fd409d1b2abdcf830ad76f4e7a52f2`
- Audited selector-producing commit: `381c02d814cc85852fab8b8f3f999df269e13780`
- Parent issue: #1109 (reopened this session)
- Child issues: #1135, #1136, #1137
- Related cross-atom issue updated: #1073
- Evidence class: deterministic source semantics + algebraic equivalence + synthetic known-answer calculations; no beam-data or MC inference.

## Selected atom

`waveform -> named selector identity -> pedestal map -> amplitude map -> threshold membership -> selected population -> CL-001/downstream claims`.

The merged selector module describes `S00_selector_v1` as a frozen historical map, but the production batched boundary still permits configuration to change the baseline index set without changing selector identity.

## Confirmed defect A: frozen v1 is parameterized at the batch boundary

The scalar documented rule is

```text
B_v1=(0,1,2,3)
b_v1(w)=median(w[B_v1])
A_v1(w)=max(w)-b_v1(w)
S_v1=1{A_v1>T}
```

`estimate_pedestal_v1_batched(waveforms, baseline_indices=None)` instead computes the median on any supplied indices. `scan_raw()` obtains those indices from `config["baseline_samples"]` and forwards them.

The canonical YAML currently says `[0,1,2,3]`, so this audit does not change the historical 640,737 count. The defect is semantic identity: the same `v1_first_four_median` path can execute a different map.

### Executed known-answer counterexample

For

```text
w=[100,100,100,100,1500,1600,1800,100,100,100,100,100,100,100,100,100,100,100]
T=1000 ADC
```

we computed:

```text
(0,1,2,3): pedestal=100,  amplitude=1700, selected=True
(2,3,4,5): pedestal=800,  amplitude=1000, selected=False
(4,5,6,7): pedestal=1550, amplitude=250,  selected=False
```

Thus changing only the allowed baseline index argument changes selected membership under the same named v1 implementation.

The scalar implementation also accepts fewer than four samples by taking the median of the shorter slice, and nonfinite samples can propagate NaN pedestal/amplitude into ordinary `selected=False` behavior. These inputs require a typed failure boundary.

## Confirmed equivalence B: dynamic_range == rolling_min as amplitude maps

Current source defines both candidate pedestal values as

```text
b_D(w)=min(w)
b_R(w)=min(w)
```

and `select_amplitude()` computes

```text
A_m(w)=max(w)-b_m(w)
```

Therefore exactly

```text
A_D(w)=A_R(w)=max(w)-min(w)
S_D(w;T)=S_R(w;T)
```

for finite inputs when the validity state is not separately used as a veto.

A 10,000-waveform randomized numerical control gave maximum absolute amplitude difference `0.0`; the stronger evidence is the source-level algebraic identity.

The two methods differ only in diagnostic validity classification. Model comparison must therefore separate `amplitude_map` from `validity_policy`; agreement between D and R is tautological, not independent robustness evidence.

## Confirmed semantic gap C: `early_robust_p10` is not early-window

The function/documentation labels this candidate as an early robust pedestal, but the implementation computes the 10th percentile of the entire waveform. This full-window order statistic is permutation-invariant and therefore cannot use temporal evidence to distinguish pre-trigger baseline from late undershoot.

For quiet symmetric noise, raw P10 is a lower noise quantile rather than the baseline location unless calibrated. Negative undershoot/dropout/bipolar samples directly contaminate the lower tail. Issue #1137 owns this child atom.

## Cross-atom update D: saturation classifier inherits unresolved DAQ code world

The new selector helper `_is_saturated(..., code_max=16383)` embeds the same unresolved 14-bit/full-scale assumption already owned by #1073. The lower-rail condition is structurally different (`all samples <=1`) from the upper condition (`any sample >=16383`). #1073 was updated; no new duplicate issue was created.

## Four sequential review passes

### Detector/data-selection lead — REVISE
Current checked-in YAML preserves historical behavior, but a frozen selector ID must mechanically bind its formula/domain. Hardware validity of samples 0-3 remains unresolved in parent #1109.

### Adversarial mechanism reviewer — BLOCK closure
Baseline-index mutation flips membership at fixed waveform/threshold. Short/nonfinite inputs expose an unclosed domain. Candidate aliasing proves apparent method multiplicity can be artificial.

### Independent validation/statistics reviewer — BLOCK closure
Required regressions: scalar/batch parity, hostile index/config mutations, short/nonfinite input failures, exact alias property tests, and separate state-policy tests. No beam data are required for these software/mathematical contracts.

### Claims/provenance reviewer — BLOCK closure
CL-001 can reference a fixed historical selector only when selector ID, formula, fixed baseline tuple, input domain, and source hash are bound in provenance. Candidate-model reports must not count exact aliases as independent evidence.

## Repository actions

- Reopened parent #1109 after #1133 automatically closed it.
- Opened #1135: frozen v1 selector identity/input-domain contract.
- Opened #1136: exact dynamic_range/rolling_min equivalence collapse.
- Opened #1137: full-window P10 semantic/identifiability gap.
- Added post-merge correction comment to PR #1133.
- Added cross-atom saturation-contract comment to #1073.
- Reviewed PR #1134 diff and exact-head CI; MC Validation CI was successful.
- Squash-merged PR #1134 to main as `37ed6aa792fd409d1b2abdcf830ad76f4e7a52f2`.

## Required implementation sequence

1. Fix #1135 first: one constant fixed baseline tuple, fail closed on any mismatch, enforce finite/valid domain, add scalar/batch parity and config-preflight tests.
2. Resolve #1136 by separating unique amplitude maps from validity policies before selector model comparison.
3. Resolve #1137 naming/statistical semantics before treating P10 as a physical pedestal candidate.
4. Continue parent #1109 with real raw-waveform mechanism decomposition and held-out selector migration after data/DAQ dependencies close.
5. Keep #1073 as authority for ADC rail/saturation semantics; selector code must consume the eventual typed DAQ contract rather than hard-code the unresolved world.

## Scientific boundary

No raw ROOT bytes, Geant4 simulation, timing resolution, PID metric, penetration fraction, pile-up rate, or detector performance number was generated in this run. The historical 640,737 S00 count is not numerically invalidated; its implementation identity remains incompletely enforced.
