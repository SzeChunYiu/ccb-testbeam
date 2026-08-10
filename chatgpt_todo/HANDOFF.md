# Latest Handoff

## Session

- **Task ID:** `ARU-S00-SELECTOR-EQUIVALENCE-CLOSURE`
- **Stamp:** `2026-08-10T040000Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial remote main:** `f5ad219c03b51cb4a2e84f7620b8d9363a250fd6`
- **Branch:** `fix/s00-selector-equivalence-contract`
- **PR:** #1140
- **Primary issue:** #1136
- **Parent:** #1109
- **Sibling blockers:** #1135, #1137
- **Acceptance:** local mathematical/model-accounting repair implemented; exact-head CI required before merge/closure.

## Selected atom

`selector method names -> scalar amplitude map -> validity policy -> candidate-model count -> robustness/multiplicity interpretation`.

## Exact result

Current source defines both `dynamic_range` and `rolling_min` with

```text
b(w)=min(w)
A(w)=max(w)-b(w)=max(w)-min(w)
```

Therefore, on every finite waveform and finite threshold `T` when validity metadata is not a veto,

```text
A_dynamic(w)=A_rolling(w)
S_dynamic(w;T)=S_rolling(w;T)
```

Their only surviving distinction is diagnostic validity-state policy. Agreement between these two names is tautological and cannot be counted as independent model support.

## Implementation on PR #1140

Added `src/ccb_mc_validation/selector_model_contract.py` with separate identities for:

- `amplitude_map_id` — the unique scalar mathematical transformation;
- `validity_policy_id` — diagnostic/censoring interpretation;
- legacy/public selector method names — retained as aliases for provenance.

Unique scalar maps are now represented as:

1. `first_four_median_v1`: `max(w)-median(w[0:4])`;
2. `range_max_minus_min_v1`: `max(w)-min(w)`;
3. `full_window_p10_v1`: `max(w)-P10(w)`.

Both `dynamic_range` and `rolling_min` map to `range_max_minus_min_v1`; their validity-policy IDs remain distinct.

Added `tests/test_selector_model_contract.py` with eight regressions:

1. every public selector method is registry-bound;
2. the four method names collapse to exactly three amplitude maps;
3. dynamic-range/rolling-min share one map ID;
4. validity policies remain separate;
5. randomized finite waveforms give exactly equal pedestal, amplitude and selected flag for the aliases;
6. bipolar fixture gives equal amplitude but intentionally different validity state;
7. P10 is a genuinely distinct negative-control amplitude map;
8. duplicate method names cannot inflate candidate count.

Repository search found no current model-selection/reporting consumer outside selector/tests using both aliases as independent scalar models. The new registry is the forward contract for future comparison/multiplicity code.

## Four sequential review passes

- **Detector/waveform lead — ACCEPT local decomposition:** keep the range statistic and keep the cautious diagnostic, but as separate layers.
- **Adversarial mechanism reviewer — ACCEPT equivalence / REVISE future gated use:** any validity-veto version must receive its own policy identity, denominator, migration table and provenance.
- **Independent validation/statistics reviewer — ACCEPT local contract pending exact-head CI:** candidate counting can operate on unique map IDs; alias agreement cannot be replication evidence.
- **Claims/provenance reviewer — ACCEPT local contract:** historical method names are preserved without being treated as independent mathematical hypotheses.

## Repository actions

1. Reviewed PR #1138 diff and exact-head MC Validation CI (`success`).
2. Squash-merged #1138 to main as `f5ad219c03b51cb4a2e84f7620b8d9363a250fd6`.
3. Created implementation branch `fix/s00-selector-equivalence-contract`.
4. Added the machine-readable equivalence contract and property/negative-control tests.
5. Added immutable archive `chatgpt_todo/archive/2026-08-10T040000Z_ARU-S00-SELECTOR-EQUIVALENCE-CLOSURE.md`.
6. Opened PR #1140.
7. Updated issue #1136 with implementation evidence and expert votes.

## CI state

PR #1140 head changed after coordination updates, so only the workflow associated with the **current exact head** may authorize merge. Do not reuse the earlier workflow result from an older branch commit. Verify `GitHub.fetch_commit_workflow_runs` on the latest head before merging.

## Scientific boundary

No raw beam data, Geant4 simulation, selected-pulse count, timing resolution, PID metric, penetration fraction, pile-up rate, energy calibration, or detector-performance value was produced or changed. This is exact mathematical/model-accounting closure only.

## Next

If exact-head CI for #1140 succeeds, review the final diff, merge #1140, and close #1136. Then return to **P0 #1135** to mechanically freeze `v1_first_four_median` to `(0,1,2,3)`, reject short/nonfinite inputs, and fail config mismatch before raw-data access or artifact staging.
