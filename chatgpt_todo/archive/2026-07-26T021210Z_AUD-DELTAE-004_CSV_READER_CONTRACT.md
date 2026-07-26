# AUD-DELTAE-004 — DeltaE-E CSV provenance reader contract

## Session

- Stamp: `2026-07-26T021210Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `303da4b0d96b703de002d53abd98f0ca9c964250`
- Destination: direct contents-API commits to `main`
- Policy: `DELTAE_CSV_IDENTIFIERS_MUST_USE_AN_EXPLICIT_TEXT_READER_CONTRACT`
- Focused acceptance: `VALIDATED`
- Repository-wide integration: `NOT_RERUN`

## Start-of-run inspection

Reviewed current `main`, recent commits, PR #933, closed PR #868, the repository-wide workflow,
its exact failing job log, the strict DeltaE runner and regression, and the mandatory coordination
records. PR #933 remained draft, open, unmergeable, and unmerged. PR #868 remained closed and
untouched.

## Demonstrated defect

Workflow run `30181818642`, job `89739575939`, used Python 3.11 and pandas 3.0.5. The exact
repository-wide failure loaded the all-digit synthetic commit
`1111111111111111111111111111111111111111` from `deltaE_E_events_data.csv` as an integer. The
regression expected the exact string.

The producer stores the commit as a string in authoritative `result.json` and writes the same token
into the CSV. The defect is the lack of an explicit CSV reader contract. Post-read string casting is
insufficient because numeric inference can irreversibly remove leading zeros.

## Work delivered

- `docs/contracts/deltae_event_csv_reader.json`
- `tests/test_deltae_csv_reader_contract.py`
- `tests/test_deltae_data_bridge_strict.py` reader-contract integration
- `tools/audit/render_deltae_csv_reader_evidence.py`
- `docs/validation/deltae_csv_reader_contract_validation.json`
- `docs/validation/deltae_csv_reader_contract.svg`
- `docs/validation/deltae_csv_reader_contract_audit.md`

The contract marks nine provenance columns as text and identifies `result.json` as the authoritative
typed bundle metadata. Regressions preserve both all-digit and leading-zero commit identifiers.

## Validation

```text
python -m py_compile \
  tests/test_deltae_csv_reader_contract.py \
  tools/audit/render_deltae_csv_reader_evidence.py

pytest -q tests/test_deltae_csv_reader_contract.py
3 passed in 0.03s
```

Environment: Python 3.13.5, pandas 2.2.3. The JSON parsed and the SVG parsed as XML. Changed Python
lines are at most 89 characters in the renderer and 85 characters in the focused test.

The exact observed pandas 3.0.5 behavior is retained from the content-addressed CI log; no local
pandas 3 environment was claimed. No push-triggered workflow run was visible through the available
connector at publication time, so repository-wide success is not claimed.

## File provenance

- Contract blob `3721a06aca5c228dbd38ba502c6b5a5bdd521f0d`, 991 bytes,
  SHA-256 `f6c07e245ce2fdd83f7190f9c2aa2bb0b633f9e5c61cd437ba01cb32d1934fbb`.
- Focused-test blob `3e580de8a3b29ab1950fd6e4bbea94ee9c59f681`, 2,003 bytes,
  SHA-256 `a5c8b68a203d6e3beb46f513a937efd115246f7358ce144933e68e2cb154461f`.
- Integrated strict-test blob `8e85937fec304aa801c5da6527495f80b56976e9`.
- Producer blob `76f7ffda2c2af92b400ca61f2f12c2b34fff7dba` was inspected and not changed.

## Direct-main sequence before final handoff

- `bf4ffcbe1395baca2b48e5717d6e6a1e3f82fb33` — task claim
- `d0a90ba1bbec7690b827a7e43e3e03e54ad6b4b9` — strict regression reader contract
- `63a267edabd773b46300be4b74d2258d0e3e4c58` — reader schema
- `167b5fe240a186e4f00bdb6cf48c008583236852` — focused contract tests
- `0a586af65587ecd738073697c97569b8471e710d` — evidence renderer
- `50893871187728d3cb1c9a02e099147ffa0d48d2` — validation JSON
- `2b72a03a209070b24bf87b43cbfd4cdca1cea3ad` — visual evidence
- `fdc85e6bb25580a590a4c8203a8286d688383f33` — audit report

## Scientific boundary

No A-002 pulse bytes were processed. No amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID, calibration, uncertainty budget, or detector-performance result was produced.
`BLK-AMP-001`, `AUD-DELTAE-001`, and `AUD-DELTAE-002` remain open for the physics result.

## Next action

Run the exact full repository gate on the current integration head. Separately audit every downstream
CSV consumer for contract use; do not infer from this unit that all consumers are safe.
