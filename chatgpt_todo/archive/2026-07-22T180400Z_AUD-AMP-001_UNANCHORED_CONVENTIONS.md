# AUD-AMP-001 — Unanchored amplitude-convention gate

- **UTC:** 2026-07-22T18:04:00Z
- **Initial main:** `df73792f871073cf716c137ee0810717395a5abf`
- **Task:** prevent raw-median-only `amplitude_adc` convention labels from being accepted as physical semantics.

## Observed evidence

The historical 19-table audit labels several tables `ABSOLUTE` at medians 3096.5, 3122, 3191, and 3419 ADC, while current defaults label medians at or below 3500 ADC as `NET` and 3500–5000 ADC as `AMBIGUOUS`. The raw median therefore does not uniquely identify whether legacy `amplitude_adc` is an absolute peak code or a net amplitude.

## Change

`tools/audit/amplitude_convention_audit.py` version 2.6.0 now records `convention_evidence` and `convention_acceptance`. A convention is accepted only when exactly one pedestal-level column independently anchors the interpretation. Median-only labels remain visible as `RAW_MEDIAN_HEURISTIC` but are `UNANCHORED`, emit `UNANCHORED_AMPLITUDE_CONVENTION`, increment `n_unanchored_conventions`, and force a nonzero exit. `subtract_baseline_correct` remains null for unanchored labels.

Added `tests/test_amplitude_convention_anchor_gate.py` covering unanchored NET, unanchored ABSOLUTE, and uniquely pedestal-anchored acceptance.

## Validation

```text
python -m py_compile /tmp/amp26/tools/audit/amplitude_convention_audit.py /tmp/amp26/tests/test_amplitude_convention_anchor_gate.py
python -m pytest /tmp/amp26/tests -q
3 passed in 0.08s
```

A direct clone failed because the runtime could not resolve `github.com`; authenticated GitHub connector reads and writes were used.

## Evidence boundary

No real pulse table was accessed. The historical 17/2 classification was not reproduced and should not be treated as accepted convention evidence until rerun with pedestal anchors or independent schema provenance. No A-002 stopping result was regenerated.
