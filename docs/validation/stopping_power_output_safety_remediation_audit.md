# Stopping-power report publication safety remediation

## Scope

This validation covers only the report-publication path in
`scripts/single_stave/compare_stopping_power.py`. It is software/provenance evidence, not detector data and not a stopping-power closure.

## Confirmed pre-change defect

The prior source blob `360f3e46db664f4eead48021536f210e2f7a85c9` opened the requested final path directly with `out_path.open("w")`. It did not reject output paths that resolved to either validated input and did not serialize through a same-directory temporary file plus atomic replacement.

A report invocation could therefore overwrite the exact simulation/reference bytes needed for reproduction. A serialization or publication failure could also leave a partial artifact under the requested final filename.

## Corrected method

The reporter now enforces `NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE`:

1. Resolve the requested report path and both input paths without requiring the report to exist.
2. Reject equality after resolution and existing-file identity through `os.path.samefile`.
3. Serialize the complete CSV to a uniquely named temporary file in the destination directory.
4. Flush and `fsync` the temporary file.
5. Measure its byte size and SHA-256 before publication.
6. Publish only with `os.replace`.
7. Remove the temporary file on every failure path and leave any previous final report unchanged.
8. Return and print the final report path, bytes, SHA-256, alias-check state, atomic-publication state, and policy.

The CSV records the publication policy. Its own final SHA-256 is returned in the in-memory result and printed after publication; embedding a file's final digest inside the same file would be self-referential.

## Validation

Exact locally validated source:

- bytes: `23541`
- SHA-256: `aa9b2f854f2eb2cb9120399e045969b5b8b4dadf939fc186afbcd2650cb397f7`

Focused regression:

```text
PYTHONPATH=. python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/audit_stopping_power_output_safety.py \
  tests/test_compare_stopping_power_output_safety.py \
  tests/test_compare_stopping_power_report_reproducibility.py

PYTHONPATH=. python -m pytest \
  tests/test_compare_stopping_power_output_safety.py \
  tests/test_compare_stopping_power_report_reproducibility.py \
  tests/test_compare_stopping_power_report_precision.py -q

12 passed in 0.07s

PYTHONPATH=. python tools/audit/audit_stopping_power_output_safety.py \
  scripts/single_stave/compare_stopping_power.py \
  --output docs/validation/stopping_power_output_safety_remediation_validation.json

OUTPUT-SAFETY AUDIT: status=VALIDATED
```

Covered failure modes:

- direct CLI output equal to the simulation input;
- direct CLI output equal to the PSTAR reference input;
- resolved symlink output alias;
- injected `os.replace` failure with a pre-existing final report;
- injected serialization failure with a pre-existing final report;
- temporary-file cleanup after failure;
- final report byte-size/SHA-256 provenance;
- AST confirmation that the canonical path has an alias guard, no direct final-path write, and an atomic helper.

The existing self-contained-report regression also passed with the new publication path.

## Interpretation and boundary

This resolves the report-artifact integrity blocker. It does not validate a real Geant4 event export, local deposited energy as projectile total energy loss, uncertainty coverage, deuteron velocity scaling, Geant4/PSTAR agreement, calibration, or detector performance.
