# Stopping-power report output safety audit

## Scope

This is a software/provenance audit of `scripts/single_stave/compare_stopping_power.py`.
It does not evaluate detector data, Geant4 physics, or agreement with PSTAR.

## Confirmed defect

The current `run_compare()` implementation reads and validates the simulation and PSTAR
inputs, then writes the requested report directly with `out_path.open("w")`. It does not
reject an output path that resolves to either input path, and it does not publish the report
through an atomic temporary-file replacement.

Two failure modes follow:

1. `--out` equal to `--sim` or `--reference` can destructively replace validated scientific
   input bytes with a derived report.
2. A process, filesystem, encoding, or serialization failure after opening the final path can
   leave a truncated report that has the canonical requested filename.

Reading the inputs before the write does not make this safe: the current invocation may finish,
but the immutable provenance needed for reproduction is destroyed or the output artifact is
left incomplete.

## Better method

Apply policy `NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE`:

1. Resolve `sim_path`, `ref_path`, and `out_path` without requiring the output to exist.
2. Reject `out_path` when it aliases either validated input path, including symlink-resolved
   equality where supported.
3. Serialize the complete CSV to a temporary file in the output directory.
4. Flush and close the temporary file successfully.
5. Replace the final path atomically with `os.replace` only after complete serialization.
6. Remove the temporary file on any failure and retain any pre-existing final report.
7. Record the output byte size and SHA-256 after publication in a sidecar or terminal result.

The alias check preserves raw/reference inputs. Atomic publication distinguishes a complete
report from a failed attempt; it does not make the scientific calculation valid by itself.

## Audit implementation

`tools/audit/audit_stopping_power_output_safety.py` parses Python through the AST and checks the
canonical `run_compare()` path for:

- direct writes to `out_path`;
- an explicit `_validate_output_path(...)` gate;
- an atomic `_write_report_atomically(...)` or `os.replace(...)` publication path.

The tool returns:

- `0` for a source satisfying the registered policy;
- `1` for a confirmed safety flaw;
- `2` for source read, UTF-8, parse, or entry-point errors.

## Validation

Executed in the reconstructed audit workspace:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_stopping_power_output_safety.py \
  tests/test_audit_stopping_power_output_safety.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_stopping_power_output_safety.py -q

5 passed in 1.63s
```

The regression covers the vulnerable direct-write pattern, a complete fixed helper contract,
an alias-only partial fix, invalid UTF-8, and CLI JSON output. Maximum changed Python line
lengths were 91 characters for the tool and 92 for the test.

## Repository evidence and boundary

Authenticated GitHub inspection of current `main` identified:

- source path: `scripts/single_stave/compare_stopping_power.py`;
- Git blob SHA-1: `360f3e46db664f4eead48021536f210e2f7a85c9`;
- direct final-path write: `with out_path.open("w", newline="")`;
- no explicit output/input alias rejection in `run_compare()`;
- no atomic replacement in the report-write path.

The exact repository source was inspected through complete ranged GitHub reads, but a network
checkout was unavailable, so the new AST audit was executed against synthetic vulnerable and
fixed controls rather than the exact full source bytes. The confirmed source pattern and this
execution boundary are separately recorded in the validation JSON.

## Acceptance state

`AUD-G4-021` is `PARTIAL`: the flaw, audit tool, regression, remediation contract, and visual
evidence are validated, but the canonical reporter is not yet changed. Until remediation,
report output must be directed to a new path that cannot alias either input, and generated CSVs
must not be treated as complete if the process failed.
