# Stopping-power simulation-input integrity audit

## Scope

This audit reviews the event-CSV ingestion path used before the repository's PSTAR
comparison. It is an engineering validation of input integrity, not a stopping-power
closure and not detector data.

## Confirmed defect

The current `compare_stopping_power.py` ingestion path silently discards noncomment
rows when any of the following is absent or unusable:

- `particle`;
- a supported energy value;
- a supported energy-deposit value;
- a supported track-length value;
- a strictly positive track length.

It also chooses the first populated alias and can therefore hide simultaneously
populated aliases. A malformed middle row can be omitted while the surviving rows
continue into aggregation and a numerical tolerance result.

An exact extraction of the current `read_sim` control flow was exercised with three
CSV rows. The middle row had a missing energy. The old behavior returned two rows,
reported `UNQUENCHED_RAW`, and recorded no failure:

```json
{"input_data_rows": 3, "returned_rows": 2, "basis": "UNQUENCHED_RAW", "skipped_rows": 1}
```

## Validated mitigation

`tools/audit/validate_stopping_power_sim_table.py` v1.0.0 provides a mandatory
fail-closed preflight. It validates every noncomment row and records exact input
provenance. It rejects:

- missing, unsupported, nonnumeric, nonfinite, or nonpositive particle/energy fields;
- missing, nonnumeric, nonfinite, or negative energy deposits;
- missing, nonnumeric, nonfinite, or nonpositive track lengths;
- duplicate/empty headers and excess CSV fields;
- multiple populated aliases for one quantity;
- simultaneous raw and quenched deposit fields in one row;
- mixed raw/quenched semantics across rows;
- quenched-only input unless explicitly enabled as a non-accepting diagnostic.

The JSON output records path, byte size, SHA-256, header, validated row count,
particle counts, energy range, energy-deposit basis, and whether raw PSTAR comparison
is permitted.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_table.py

python -m pytest tests/test_validate_stopping_power_sim_table.py -q
17 passed in 1.31s
```

Changed Python files had no lines longer than 100 characters.

## Acceptance boundary

The validator itself is validated for the covered synthetic cases. The legacy
comparison entry point has not yet been modified to invoke it automatically, so
scientific use must run this preflight explicitly and preserve its JSON output.
This work does not validate PSTAR transcription, Geant4 energy-loss physics,
secondary escape, material/cut/physics-list provenance, deuteron scaling, or any
numerical agreement claim.
