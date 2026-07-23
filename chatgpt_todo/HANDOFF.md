# Latest Handoff

## Session

- **UTC:** 2026-07-23T15:02:28Z
- **Task:** `AUD-G4-009`
- **First observed remote main:** `e6dd97da2d50cc81e9f49f8dab7cb2c8395fa6eb`
- **Concurrent current-main handoff before writes:** `abb8a34ec47b6d62fae2ec07b837b71d2077bece`
- **Validated implementation/evidence head:** `28345eb2417fdbd87d595984a82a513cfa26af2e`
- **Coordination/archive head before this handoff:** `f893a859e42c028775560afb8c1c28af26b349c3`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** PARTIAL — fail-closed standalone event-table preflight, 17 focused tests, provenance output, and synthetic visual evidence are validated and delivered directly to `main`; canonical comparison integration and validation on real exported simulation tables remain open.

## Start-of-run and concurrent-work review

- Direct Git clone/fetch failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and direct writes were used.
- Inspected current `main`, recent history, PR #868, the latest issue #885 handoff, stopping-power code/history, validation records, and mandatory `chatgpt_todo/` files.
- Concurrent issue #885 work was detected and not duplicated. The selected unit was the unresolved simulation-event CSV ingestion path feeding the PSTAR diagnostic.
- PR #868 remains closed, unmerged, and non-mergeable; it was not modified.
- No task branch, pull request, force-push, history rewrite, source-data modification, or unrelated deletion was used.

## Confirmed defect

The current `scripts/single_stave/compare_stopping_power.py` reader can silently omit noncomment rows when:

- `particle` is missing;
- no supported energy-deposit value is populated;
- energy or track length is missing;
- track length is nonpositive.

Its alias helper also uses the first populated alias and does not reject multiple simultaneously populated aliases. Therefore, an incomplete or ambiguous simulation sample can reach aggregation without a row-accounting failure.

Exact synthetic reproduction of the reviewed control flow used three event rows with a missing energy in the middle row:

```json
{"input_data_rows": 3, "returned_rows": 2, "basis": "UNQUENCHED_RAW", "skipped_rows": 1}
```

This is parser-regression evidence, not detector data and not a Geant4/PSTAR agreement result.

## Validated implementation

Added `tools/audit/validate_stopping_power_sim_table.py` v1.0.0. It:

- validates every noncomment row;
- requires one supported particle (`p|proton|d|deuteron`);
- requires exactly one populated alias for energy, deposit, and track length;
- requires finite positive energy, finite nonnegative deposit, and finite positive track length;
- validates centimetre-to-millimetre track conversion;
- rejects simultaneous raw and quenched deposits in one row;
- rejects mixed raw/quenched semantics across rows;
- rejects quenched-only input by default;
- permits explicit quenched proxy input only as `DIAGNOSTIC_ONLY` with nonzero exit;
- rejects empty/duplicate headers and excess fields;
- records exact input path, byte size, SHA-256, header, row count, particle counts, energy range, basis, and comparability;
- returns input-error status 2 without writing validation JSON when validation fails.

Added `tests/test_validate_stopping_power_sim_table.py` with 17 focused tests for valid provenance, malformed/missing/nonfinite/nonphysical values, unsupported particles, ambiguous aliases, raw/quenched mixing, non-accepting quenched mode, malformed-middle-row CLI behavior, and supported centimetre track lengths.

Added reproducible evidence:

- `docs/validation/stopping_power_sim_input_integrity_audit.md`
- `docs/validation/stopping_power_sim_input_integrity_validation.json`
- `docs/validation/stopping_power_sim_input_integrity.svg`

The SVG explicitly states `synthetic regression evidence — not detector data` and shows the former three-to-two-row silent path versus the new status-2 rejection.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_table.py

python -m pytest tests/test_validate_stopping_power_sim_table.py -q
17 passed in 1.31s
```

Additional completed checks:

- validation JSON parsed;
- SVG parsed as XML;
- changed Python lines were no longer than 100 characters;
- committed tool and test were re-read from `main` after writes.

Validated local SHA-256 identities:

- tool: `198a06459d6eb2c143dc850c1f5f5e48f54b89ce40ef382fc6b6c18b06e09dd2`
- test: `a878d5240faaed55fe67bce054975dbf709ee9e31cda4aae3ec5ab49596db9db`
- audit Markdown: `0d65d512a25c93c29e01c74d3c52c008d485b0adb2c187d03c9514b8c03eb8dd`
- validation JSON: `fefbf127a5bd5594398877dfae3e276842fc3517569cbffbf5e51c27cebfe63e`
- SVG: `09be4c16e4bca9f3a58e99959a9628d00723b012fa3182c6fcde5df90ad01ac7`

Not run:

- full repository pytest;
- ruff;
- Geant4 build or CTest;
- ROOT or real simulation processing;
- GitHub Actions.

No broader CI, stopping-power closure, or detector-performance result is claimed.

## Direct-to-main commits

Implementation, tests, and evidence:

- `442ff0c68c16564cc9bdd4ab3476718d2b5f2acd` — `feat(audit): validate stopping-power simulation inputs`
- `b8f9e2873028ca0e1ef31b64eb6e6ec6afc2dc60` — `test(audit): cover stopping-power simulation input integrity`
- `4f3a41e4f4131fccfcf2eb6a515614723b63b6ac` — `docs(validation): record stopping-power simulation input audit`
- `028814362354c1c559a490b63220d2d2fa1a6667` — `docs(validation): add stopping-power simulation input record`
- `28345eb2417fdbd87d595984a82a513cfa26af2e` — `docs(validation): visualize stopping-power input integrity gate`

Coordination and provenance:

- `3e527bba859f0255738aa30cc231af454b94ea64` — `docs(audit): track stopping-power simulation input integrity`
- `2c76750f0c55ec0d726356b51cad9ba8d78881e3` — `docs(audit): claim stopping-power simulation input integrity`
- `aa2ea366857d59bb8d63d9867bf896670b435f4b` — `docs(audit): map stopping-power simulation input preflight`
- `4d2ad16dec7e136f2886cadfd139bf2b315085ce` — `docs(audit): refine stopping blocker with sim-input preflight`
- `dfe5812a343e7da30e750dbfb2525ab25867cc0f` — `docs(audit): register stopping-power input-integrity visual`
- `7c96aad83aab29ab86b1ef9f33bde48dbdd8c8f4` — `docs(audit): record stopping-power input-integrity study`
- `a65f29554ec556be43f23209c0a966e8033ba25d` — `docs(audit): classify stopping-power simulation input integrity`
- `b421ece6867c6dc3dd5182d1c00910484df90078` — `docs(audit): index stopping-power simulation input integrity`
- `f893a859e42c028775560afb8c1c28af26b349c3` — `docs(audit): archive stopping-power simulation input integrity`

Every write above returned a successful direct-main commit SHA. Remote history was checked during the sequence. This handoff update follows directly on `main`; its returned commit SHA is verified as remote head after creation.

## Repository-local records

Updated:

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `MASTER_INDEX.md`
- `CODE_RESULT_MAP.md`
- `STUDY_REVIEW_LEDGER.md`
- `CLAIM_EVIDENCE_MATRIX.md`
- `VISUALIZATION_MATRIX.md`
- `BLOCKERS.md`
- `HANDOFF.md`

Added immutable provenance:

- `archive/2026-07-23T150228Z_AUD-G4-009_SIM_INPUT_INTEGRITY.md`

`SESSION_LOG.md` was not replaced because the connector exposes complete-file replacement but no safe append primitive, and only a partial read of the long append-only file was available. Replacing it from incomplete bytes could destroy earlier provenance. The immutable archive above is the complete session record.

## Scientific boundary and next action

The standalone preflight prevents malformed simulation tables from silently becoming smaller analysis samples when it is run. It does not validate:

- any real exported Geant4 event table;
- the PSTAR source transcription;
- local deposition as projectile total energy loss;
- escaping-secondary accounting;
- material, production-cut, or physics-list systematics;
- the deuteron `S_d(E) ≈ S_p(E/2)` approximation;
- any detector calibration or performance claim.

Next:

1. integrate the validated parser into `compare_stopping_power.py` without duplicating schema logic;
2. run the reference-path, domain, reference-integrity, quenched-proxy, and input-integrity suites together;
3. validate and hash exact real exported event CSVs and retain validation JSON beside comparison output;
4. pursue the separate accepted proton closure under `AUD-G4-005`.
