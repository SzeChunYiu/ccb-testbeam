# AUD-G4-009 — Stopping-power simulation-input integrity

## Session

- **UTC:** 2026-07-23T15:02:28Z
- **Owner:** scheduled ChatGPT audit session
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **First observed remote main:** `e6dd97da2d50cc81e9f49f8dab7cb2c8395fa6eb`
- **Concurrent current-main handoff observed before writes:** `abb8a34ec47b6d62fae2ec07b837b71d2077bece`
- **Implementation/evidence head:** `28345eb2417fdbd87d595984a82a513cfa26af2e`
- **Acceptance:** PARTIAL — standalone fail-closed input preflight, focused regression, provenance record, and visual evidence are validated; canonical comparison integration and real-table validation remain open.

## Start-of-run review

- Direct Git clone/fetch failed because the runtime could not resolve `github.com`; authenticated GitHub connector reads and direct-main writes were used.
- Inspected current `main` history, PR #868, issue #885 handoff, mandatory `chatgpt_todo/` records, `compare_stopping_power.py`, PSTAR validation history, and the existing stopping-power blocker.
- PR #868 was confirmed closed, unmerged, and non-mergeable and was not modified.
- Concurrent issue #885 work was detected. This session did not duplicate it and selected the unresolved stopping-power simulation-input path.
- No force-push, branch rewrite, pull request, source-data modification, or unrelated-file deletion was used.

## Confirmed defect

The current simulation reader in `scripts/single_stave/compare_stopping_power.py`:

- silently continues past rows with missing particle values;
- silently continues past rows with no usable energy deposit;
- silently continues past rows with missing energy or track length;
- silently continues past nonpositive track lengths;
- selects the first populated alias without rejecting multiple populated aliases.

This allows an incomplete or ambiguous simulation sample to reach aggregation without a row-accounting failure.

An exact extraction of the reviewed `read_sim` control flow was exercised with three noncomment event rows. The middle row had a missing energy. Measured legacy behavior:

```json
{"input_data_rows": 3, "returned_rows": 2, "basis": "UNQUENCHED_RAW", "skipped_rows": 1}
```

This is synthetic parser evidence, not detector data and not a Geant4 stopping-power result.

## Validated implementation

Added `tools/audit/validate_stopping_power_sim_table.py` v1.0.0. It:

- validates every noncomment event row;
- requires one recognized particle (`p|proton|d|deuteron`);
- requires exactly one populated energy alias, energy-deposit alias, and track-length alias;
- requires finite positive kinetic energy;
- requires finite nonnegative energy deposit;
- requires finite positive track length and validates centimetre-to-millimetre conversion;
- rejects simultaneous raw and quenched deposits within a row;
- rejects mixed raw/quenched semantics across rows;
- rejects quenched-only input by default;
- permits explicit quenched proxy input only as `DIAGNOSTIC_ONLY` with exit status 1;
- rejects empty/duplicate headers and excess CSV fields;
- records exact path, bytes, SHA-256, header, validated row count, particle counts, energy range, deposit basis, and comparability state;
- returns status 2 without writing validation JSON for invalid input.

Added `tests/test_validate_stopping_power_sim_table.py` with 17 focused tests covering valid provenance, particle/energy/deposit/track failures, nonfinite and nonphysical values, alias ambiguity, same-row and cross-row semantic mixing, quenched diagnostic status, malformed-middle-row CLI behavior, and centimetre track-length support.

Added reproducible evidence:

- `docs/validation/stopping_power_sim_input_integrity_audit.md`
- `docs/validation/stopping_power_sim_input_integrity_validation.json`
- `docs/validation/stopping_power_sim_input_integrity.svg`

The SVG is a deterministic synthetic schematic and explicitly states that it is not detector data.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_table.py

python -m pytest tests/test_validate_stopping_power_sim_table.py -q
17 passed in 1.31s
```

Additional checks:

- validation JSON parsed successfully;
- SVG parsed as XML;
- changed Python lines were no longer than 100 characters;
- the committed tool and test were re-read from `main` after writes.

Local SHA-256 identities used during validation:

- tool: `198a06459d6eb2c143dc850c1f5f5e48f54b89ce40ef382fc6b6c18b06e09dd2`
- test: `a878d5240faaed55fe67bce054975dbf709ee9e31cda4aae3ec5ab49596db9db`
- audit Markdown: `0d65d512a25c93c29e01c74d3c52c008d485b0adb2c187d03c9514b8c03eb8dd`
- validation JSON: `fefbf127a5bd5594398877dfae3e276842fc3517569cbffbf5e51c27cebfe63e`
- SVG: `09be4c16e4bca9f3a58e99959a9628d00723b012fa3182c6fcde5df90ad01ac7`

Not run:

- full repository pytest;
- ruff;
- Geant4 build/CTest;
- ROOT or real simulation processing;
- GitHub Actions.

## Direct-to-main commits before archive

- `442ff0c68c16564cc9bdd4ab3476718d2b5f2acd` — `feat(audit): validate stopping-power simulation inputs`
- `b8f9e2873028ca0e1ef31b64eb6e6ec6afc2dc60` — `test(audit): cover stopping-power simulation input integrity`
- `4f3a41e4f4131fccfcf2eb6a515614723b63b6ac` — `docs(validation): record stopping-power simulation input audit`
- `028814362354c1c559a490b63220d2d2fa1a6667` — `docs(validation): add stopping-power simulation input record`
- `28345eb2417fdbd87d595984a82a513cfa26af2e` — `docs(validation): visualize stopping-power input integrity gate`
- `3e527bba859f0255738aa30cc231af454b94ea64` — `docs(audit): track stopping-power simulation input integrity`
- `2c76750f0c55ec0d726356b51cad9ba8d78881e3` — `docs(audit): claim stopping-power simulation input integrity`
- `aa2ea366857d59bb8d63d9867bf896670b435f4b` — `docs(audit): map stopping-power simulation input preflight`
- `4d2ad16dec7e136f2886cadfd139bf2b315085ce` — `docs(audit): refine stopping blocker with sim-input preflight`
- `dfe5812a343e7da30e750dbfb2525ab25867cc0f` — `docs(audit): register stopping-power input-integrity visual`
- `7c96aad83aab29ab86b1ef9f33bde48dbdd8c8f4` — `docs(audit): record stopping-power input-integrity study`
- `a65f29554ec556be43f23209c0a966e8033ba25d` — `docs(audit): classify stopping-power simulation input integrity`
- `b421ece6867c6dc3dd5182d1c00910484df90078` — `docs(audit): index stopping-power simulation input integrity`

## Scientific boundary and next action

The new tool prevents a malformed simulation table from silently becoming a smaller analysis sample when the preflight is run. It does not establish Geant4/PSTAR agreement, validate the committed PSTAR transcription, quantify secondary escape, validate the deuteron approximation, or produce detector data.

The canonical comparison CLI still contains the legacy reader. Next:

1. integrate the validated row parser into `compare_stopping_power.py` without duplicating schema logic;
2. run the existing reference-path, domain, reference-integrity, quenched-proxy, and new input-integrity suites together;
3. validate and hash exact real exported event CSVs;
4. retain the validation JSON beside each comparison output;
5. pursue the separate accepted proton stopping-power closure under `AUD-G4-005`.

`SESSION_LOG.md` was not replaced because the connector lacks a safe append operation and only complete-file replacement is available. Replacing an append-only file from partial retrieval could destroy prior provenance. This immutable archive is the complete session record.
