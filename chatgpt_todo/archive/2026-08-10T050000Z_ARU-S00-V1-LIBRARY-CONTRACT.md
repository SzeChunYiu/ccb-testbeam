# ARU-S00-V1-LIBRARY-CONTRACT

- **Session:** `2026-08-10T050000Z`
- **Base main:** `f2fb7dc24f38c838d1d30b4a6137bb6444c93180`
- **Issue:** #1135
- **Branch:** `fix/s00-selector-v1-semantic-contract`
- **Scope:** selector-library semantic identity and numerical input domain only.
- **Status:** `PARTIAL` until exact-head CI passes and the producer preflight child is closed.

## Atom contract

For the historical selector, one public identity must denote one map on one
closed numerical domain:

```text
selector_id = v1_first_four_median
B_v1 = (0,1,2,3)
b_v1(w) = median(w[B_v1])
A_v1(w) = max(w) - b_v1(w)
S_v1(w;T) = 1{A_v1(w) > T}
```

The library-level valid domain introduced here is:

```text
scalar: 1-D finite waveform, n_samples >= 4
batched: array with a sample axis, finite everywhere, n_samples >= 4
baseline_indices: None or exactly the integral tuple (0,1,2,3)
```

The full upstream product identity (16 versus 18 samples) remains outside this
leaf and is governed by the raw-waveform/schema atoms.

## Competing semantic worlds

1. **H1 — fixed historical map:** v1 always means first-four median.
2. **H2 — parameterized baseline family:** the baseline index tuple is a model
   parameter and therefore needs a different model identity.
3. **H3 — free tuple under v1 plus count closure:** rejected. Aggregate count
   equality is many-to-one and cannot establish record-level semantic identity.
4. **H4 — malformed/nonfinite inputs become ordinary rejected pulses:** rejected
   for canonical production; malformed numerical input is not a physics class.
5. **H5 — numeric equality is sufficient index identity:** rejected during
   adversarial review because Python has value aliases such as `False == 0`,
   `True == 1`, and `0.0 == 0`. A selector index is a typed discrete coordinate,
   not merely a number equal under Python comparison.

H1 is the narrow backward-compatible world for canonical S00. H2 remains
available only under a separately versioned sensitivity model.

## Implementation

`src/ccb_mc_validation/selector.py` now defines:

- `S00_SELECTOR_V1_ID = "v1_first_four_median"`;
- `S00_SELECTOR_V1_BASELINE_INDICES = (0, 1, 2, 3)`;
- `SelectorInputError` for controlled domain/identity failures;
- a strict typed baseline-tuple assertion;
- scalar/batched v1 waveform-domain validation;
- exact scalar/batch use of the frozen tuple.

The tuple validator accepts Python/NumPy integral values but rejects booleans,
floats, strings and other type-confused aliases even when they compare equal to
an integer. The historical formula on valid canonical inputs is unchanged.

## Adversarial tests added

`tests/test_selector_v1_contract.py` covers:

- the exact ID and fixed tuple;
- reordered, missing, extra, duplicate, negative and out-of-range indices;
- string, float and boolean type-confusion aliases;
- positive control for NumPy integral indices;
- `None`, canonical list and canonical tuple equivalence;
- scalar lengths 0, 1, 2, 3;
- scalar dimensionality failure;
- NaN, +Inf and -Inf anywhere in scalar or batched waveforms;
- missing batched sample axis;
- randomized scalar/batch exact parity;
- randomized equality to direct `median(..., 0:4)`;
- the exact #1135 selection-flip waveform, now rejected at the identity boundary
  for noncanonical baseline windows.

## Recursive adversarial finding

The first library patch compared `tuple(baseline_indices)` directly with
`(0,1,2,3)`. That was insufficient: `[False, True, 2, 3]` compares equal to the
canonical integer tuple in Python, while `[0.0,1.0,2.0,3.0]` can pass numerical
equality before failing later at NumPy indexing with the wrong exception type.
The branch was hardened before closure: only non-boolean `numbers.Integral`
values are accepted and then canonicalized to Python integers. This correction
is preserved rather than hiding the failed first attempt.

## Four sequential expert passes

### Detector/data-selection lead — ACCEPT library leaf / BLOCK physical pedestal claim

Evidence: current selector source, S00 producer, canonical config and #1135
counterexample. The software map can and should be frozen independently of the
still-open detector question of whether samples 0-3 are physically quiet.

### Adversarial mechanism reviewer — ACCEPT after typed tuple/domain controls

Strongest counter-hypotheses tested: noncanonical value tuple and type-confused
value-equivalent tuple. Both now fail at the library boundary. The remaining
producer-level concern is *when* that error occurs relative to raw access and
artifact staging.

### Statistics/validation reviewer — ACCEPT deterministic contract / pending CI

No beam statistics are required for formula identity. Randomized parity tests
are implementation controls, not detector-performance evidence. Exact-head CI
must still authorize integration with the full repository.

### Claims/provenance reviewer — REVISE parent #1135

The library now binds the selector name to one formula and finite typed domain.
The canonical producer still creates its staging directory before `scan_raw()`
and only reaches the strict baseline assertion inside the scan. Therefore issue
#1135 must remain open until config mismatch fails before raw access/staging and
manifest provenance serializes the fixed tuple/ID.

## Residual child atom

The next leaf is #1141, the canonical producer preflight transaction:

```text
load config
→ assert selector_id/baseline_samples contract
→ only then resolve/create output staging and access ROOT
```

Required negative control: mutate `baseline_samples` to `[2,3,4,5]` and prove
that no `uproot.open`, `Path.mkdir` for staging, or artifact write occurs.

Manifest/model identity must serialize both the stable selector ID and fixed
baseline tuple. CL-001 promotion governance must also include this selector
contract rather than treating only #952/#953/#954 as sufficient blockers. This
is a producer/provenance child, not a reason to weaken the library guard.

## Scientific boundary

No raw beam file was opened, no S00 population was rescanned, and no Geant4
simulation was run. The 640,737 historical count is not numerically changed by
this leaf. Hardware validity of samples 0-3 remains parent #1109.
