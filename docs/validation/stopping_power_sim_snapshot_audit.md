# Stopping-power simulation input snapshot audit

## Scope

This review checks whether the simulation rows consumed by the canonical stopping-power parser and the reported byte provenance are derived from the same immutable in-memory byte snapshot. It is a synthetic software/provenance validation, not detector data and not a Geant4/PSTAR physics closure.

## Confirmed defect

Version 1.1.0 parsed text through `Path.read_text()`, then later measured `Path.stat().st_size` and streamed the path again through `sha256_file()`. Those operations were not one atomic snapshot. If the path was replaced between parsing and provenance measurement, normalized rows could describe the earlier bytes while `input_bytes` and `input_sha256` described the later bytes.

The same parser also allowed an invalid UTF-8 byte sequence to escape as an uncaught `UnicodeDecodeError`, producing an uncontrolled traceback instead of the documented status-2 input failure.

## Correction

Version 1.2.0 reads the exact file bytes once. The parser:

1. decodes and parses that byte string;
2. computes byte count from `len(input_bytes)`;
3. computes SHA-256 from the same byte string;
4. records `input_snapshot_method=SINGLE_READ_EXACT_BYTES`;
5. converts invalid UTF-8 into `SimulationTableError` so the CLI exits 2 without a success record.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py

python -m pytest \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py -q

19 passed in 2.01s
```

The mutation regression intercepts the parser after it has formed data lines, replaces the path bytes, and verifies that returned rows, byte count, and SHA-256 still correspond to the original single-read snapshot. The exact former algorithm fails both new tests: its provenance follows the replacement file, and invalid UTF-8 raises an uncaught decoder exception.

## Acceptance and limitations

Accepted for `AUD-G4-019`: the canonical simulation-table validator now binds normalized rows and provenance to one exact byte snapshot and fails invalid UTF-8 in a controlled way.

Not established: validity of any real Geant4 export, projectile total-energy-loss semantics, statistical/systematic uncertainty, or Geant4/PSTAR agreement.
