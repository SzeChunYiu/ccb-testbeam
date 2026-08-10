# ARU-S00-SELECTOR-EQUIVALENCE-CLOSURE

## Session identity

- Stamp: `2026-08-10T040000Z`
- Initial remote main: `f5ad219c03b51cb4a2e84f7620b8d9363a250fd6`
- Primary issue: #1136
- Parent: #1109
- Sibling blocker: #1135
- Branch: `fix/s00-selector-equivalence-contract`
- Evidence class: exact source algebra + deterministic synthetic/property tests; no beam-data or MC inference.

## Selected atom

`selector method names -> scalar amplitude maps -> validity policies -> candidate-model count -> robustness/multiplicity claims`.

The selector API exposes `dynamic_range` and `rolling_min` as separate method names. Both compute the same pedestal `min(w)` and the shared pipeline computes `max(w)-pedestal`. They are therefore one mathematical amplitude map with two diagnostic validity policies.

## Mathematical collapse

For finite waveform `w`,

```text
b_D(w) = min(w)
b_R(w) = min(w)
A_D(w) = max(w)-b_D(w)
A_R(w) = max(w)-b_R(w)
```

so identically

```text
A_D(w) = A_R(w) = max(w)-min(w)
S_D(w;T) = S_R(w;T)
```

for every threshold `T` when validity metadata is not used as a veto.

The apparent four-name candidate universe therefore contains three distinct amplitude maps:

1. `first_four_median_v1`: `max(w)-median(w[0:4])`;
2. `range_max_minus_min_v1`: `max(w)-min(w)`;
3. `full_window_p10_v1`: `max(w)-P10(w)`.

## Implementation

Added `src/ccb_mc_validation/selector_model_contract.py` with a machine-readable separation between:

- `amplitude_map_id` — unique scalar mathematical transformation;
- `validity_policy_id` — diagnostic/censoring interpretation;
- legacy/public selector method aliases.

`dynamic_range` and `rolling_min` both bind to `range_max_minus_min_v1`, while their validity-policy IDs remain distinct. The module provides stable unique amplitude-map enumeration and alias collapse for model-comparison/multiplicity consumers.

Added `tests/test_selector_model_contract.py` covering:

- registry coverage of every public selector method;
- exact three-map collapse;
- range alias identity;
- separation of validity policies;
- randomized finite-waveform equality of pedestal, amplitude and selected flag;
- bipolar fixture where amplitude is identical but validity intentionally differs;
- P10 distinct-map negative control;
- duplicate method names cannot inflate candidate count.

## Four sequential review passes

### Detector/waveform lead — ACCEPT local decomposition

The range statistic remains a useful comparator. The cautious rolling-min diagnostic remains useful, but it is represented as a validity policy layered on the same amplitude map rather than a second amplitude hypothesis.

### Adversarial mechanism reviewer — ACCEPT equivalence / REVISE downstream usage

No source-level scalar difference exists to falsify the equivalence. The hostile bipolar fixture intentionally demonstrates the only surviving difference: diagnostic state. Future state-gated selection must receive its own policy identity and denominator rather than masquerade as a new pedestal formula.

### Independent validation/statistics reviewer — ACCEPT local contract

Candidate counting can now operate on unique map IDs. Exact alias agreement cannot be counted as replication or robustness evidence. Beam data are unnecessary for this algebraic closure; data are required only for evaluating whether a validity-gated range policy is scientifically useful.

### Claims/provenance reviewer — ACCEPT local contract

The registry gives downstream reports a machine-readable way to state both mathematical amplitude identity and validity-policy identity. Historical method names are preserved as aliases rather than rewritten.

## Scientific boundary

This change does not validate any pedestal model physically. It does not decide whether `min(w)` is a quiet baseline, negative excursion, dropout, or other waveform feature. It changes no selected pulse count, timing value, penetration fraction, PID metric, calibration, MC result, or detector-performance claim.

## Remaining parent work

- #1135 still blocks canonical v1 semantic identity/domain closure.
- #1137 still blocks interpretation of the full-window P10 candidate.
- #1109 still requires real-waveform mechanism decomposition, threshold migration, held-out transfer, and downstream sensitivity.
- Any future state-gated range selector must be a separately named policy with explicit denominator/migration/provenance.
