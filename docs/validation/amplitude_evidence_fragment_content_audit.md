# Amplitude evidence-fragment content audit

## Scope

This unit reviewed the line-fragment gate in `tools/audit/validate_amplitude_evidence_map.py`. The gate already required canonical `#L<start>[-L<end>]` syntax, verified the complete supporting-file SHA-256, and required the selected line numbers to exist.

## Confirmed defect

Validator v1.3.0 treated any in-range line selection as verified, including a range containing only spaces or tabs. A hash-bound record could therefore cite a blank line and still authorize an `ABSOLUTE` or `NET` amplitude convention. The validator also retained no digest of the exact selected fragment, so later reports could not identify the precise supporting bytes independently of the whole-file digest.

The exact old implementation failed the new regression with:

```text
2 failed, 6 passed in 0.10s
```

The failures demonstrated that a whitespace-only `#L2` fragment was accepted and that exact fragment byte metadata was absent.

## Correction

Validator v1.4.0 now reads the supporting artifact once for fragment verification, selects the exact requested line bytes, and rejects a selection with zero nonblank lines. A verified line fragment records:

- complete supporting-file line count;
- selected fragment size in bytes;
- number of nonblank selected lines;
- SHA-256 of the exact selected bytes;
- start and end line numbers;
- `evidence_reference_fragment_verified=true` only after all checks pass.

Whole-file references remain supported and unchanged.

Policy: `EVIDENCE_LINE_FRAGMENT_MUST_CONTAIN_NONWHITESPACE_CONTENT`.

## Validation

Executed against exact local reconstructions of the current source and focused tests:

```text
python -m py_compile \
  tools/audit/validate_amplitude_evidence_map.py \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_reference_fragments.py

python -m pytest \
  tests/test_validate_amplitude_evidence_map.py \
  tests/test_amplitude_evidence_reference_fragments.py -q

23 passed in 0.05s
```

The changed Python files contain no line longer than 100 characters. The representative accepted fragment is 29 bytes, contains two nonblank lines, and has SHA-256 `2574a91c9368c20f6ae926794a5a37285b264197d248084c3b63306f8cadfa5a`.

## Scientific boundary

This is synthetic software and provenance evidence. It does not determine whether the A-002 `amplitude_adc` field is absolute or net, validate pedestal data, regenerate stopping or DeltaE-E outputs, or establish any detector-performance claim. Real-data acceptance remains blocked pending an exact table hash and exact supporting evidence bytes.
