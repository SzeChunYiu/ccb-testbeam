# DeltaE-E CSV provenance identifier contract audit

## Scope

Task `AUD-DELTAE-004` reviews one demonstrated repository-CI failure in the strict A-002
DeltaE-E rerun bundle. This is a software and provenance audit. It does not reinterpret pulse
amplitudes or authorize a detector result.

Policy:

`DELTAE_CSV_IDENTIFIERS_MUST_USE_AN_EXPLICIT_TEXT_READER_CONTRACT`

## Demonstrated defect

GitHub Actions run `30181818642`, job `89739575939`, installed Python 3.11 and pandas 3.0.5.
The repository-wide test
`tests/test_deltae_data_bridge_strict.py::test_valid_bundle_is_content_addressed_and_reconstructable`
failed because default `pandas.read_csv` inference loaded the all-digit synthetic Git commit
`1111111111111111111111111111111111111111` as an integer. The test expected the exact text
identifier.

This is not evidence that the producer wrote an incorrect commit. The producer stores the commit as
text in `result.json` and writes the same token to the event CSV. The failure demonstrates that an
untyped CSV consumer can reinterpret provenance. A leading-zero hexadecimal identifier would be
more serious because numeric inference can destroy the original token rather than merely change its
Python type.

## Remediation

The repository now contains `docs/contracts/deltae_event_csv_reader.json`. It identifies
`result.json` as the authoritative typed metadata member and declares nine provenance columns as
text for `pandas.read_csv`:

- policy and runner version;
- input, bridge, and runner SHA-256 identifiers;
- repository commit;
- generation command;
- Python and pandas versions.

The strict bundle regression loads the contract and applies its dtype map before comparing
identifiers. `tests/test_deltae_csv_reader_contract.py` independently verifies that the contract is
complete and preserves both an all-digit commit and a commit beginning with zero.

## Alternative methods considered

1. **Cast after default CSV loading.** Rejected because converting an inferred integer back to text
   cannot restore leading zeros.
2. **Prefix identifiers in every CSV cell.** Robust, but it would change the published artifact
   schema and duplicate type tags already supplied by the reader contract.
3. **Use only JSON or Parquet.** Typed formats are preferable for machine processing, but the CSV is
   retained for human review and established downstream use. The accepted approach keeps JSON
   authoritative and makes the CSV reading contract explicit.

## Focused validation

Executed in the available local environment:

```text
python -m py_compile \
  tests/test_deltae_csv_reader_contract.py \
  tools/audit/render_deltae_csv_reader_evidence.py

pytest -q tests/test_deltae_csv_reader_contract.py
3 passed in 0.03s
```

Environment:

- Python 3.13.5;
- pandas 2.2.3.

The test intentionally checks semantics that are independent of whether the local pandas release
would have inferred the all-digit token numerically. The exact CI failure remains the evidence for
pandas 3.0.5 behavior. The validation JSON parsed, the generated SVG parsed as XML, and changed
Python lines are at most 89 characters in the renderer and 85 characters in the new focused test.

## Version-controlled evidence

- `docs/contracts/deltae_event_csv_reader.json`
  - Git blob `3721a06aca5c228dbd38ba502c6b5a5bdd521f0d`
  - 991 bytes
  - SHA-256 `f6c07e245ce2fdd83f7190f9c2aa2bb0b633f9e5c61cd437ba01cb32d1934fbb`
- `tests/test_deltae_csv_reader_contract.py`
  - Git blob `3e580de8a3b29ab1950fd6e4bbea94ee9c59f681`
  - 2,003 bytes
  - SHA-256 `a5c8b68a203d6e3beb46f513a937efd115246f7358ce144933e68e2cb154461f`
- `tests/test_deltae_data_bridge_strict.py`
  - Git blob `8e85937fec304aa801c5da6527495f80b56976e9`
- `scripts/single_stave/deltaE_E_data_bridge_strict.py`
  - Git blob `76f7ffda2c2af92b400ca61f2f12c2b34fff7dba`

## Acceptance and limitations

The focused reader-contract remediation is `VALIDATED`. It does not establish that every repository
consumer uses the contract; consumers that use automatic CSV inference remain outside this unit.
No push-triggered GitHub Actions result was visible through the available connector at evidence
publication time, so repository-wide CI success is not claimed.

No exact A-002 pulse table was processed. No amplitude convention, pulse polarity, stopping
fraction, DeltaE-E particle-identification result, uncertainty budget, calibration, or detector
performance is established. Those remain governed by `BLK-AMP-001`, `AUD-DELTAE-001`, and
`AUD-DELTAE-002`.
