# Latest Handoff

## Session

- **UTC:** 2026-07-23T02:05:18Z
- **Task:** AUD-AMP-006 (PARTIAL)
- **Initial remote main:** `5e00ec10368a893d3ae4d92398f18dc777e4f044`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed scientific/provenance defect

`tools/audit/amplitude_convention_audit.py` v2.9.0 hash-binds convention records to input-table bytes and validates the convention and evidence-basis category, but a record containing only `convention` and `evidence_basis` can still authorize physics use. It need not identify the schema metadata, producer code, pedestal study, commit, or report supporting the convention. The existing loader also accepts any 64-character key rather than requiring canonical lowercase hexadecimal SHA-256 text.

Hash binding therefore protects table identity but does not by itself make the convention assertion reviewable or reproducible.

## Work pushed directly to main

Added `tools/audit/validate_amplitude_evidence_map.py` v1.0.0. It rejects an evidence map unless every record has:

- a canonical lowercase hexadecimal 64-character SHA-256 key;
- `convention` equal to `ABSOLUTE` or `NET`;
- an accepted evidence-basis category;
- a non-empty `evidence_reference` identifying the supporting artifact or source;
- an optional embedded `sha256` exactly matching the map key.

When `--output` is supplied, the validator writes normalized JSON containing the tool version, evidence-map path, record count, and canonicalized records.

Added regression coverage:

- `tests/test_validate_amplitude_evidence_map.py`

Immutable session record:

- `chatgpt_todo/archive/2026-07-23T020518Z_AUD-AMP-006_EVIDENCE_REFERENCE_GATE.md`

## Validation

Executed on exact local files before GitHub writes:

```text
python -m py_compile tools/audit/validate_amplitude_evidence_map.py tests/test_validate_amplitude_evidence_map.py
python -m pytest tests/test_validate_amplitude_evidence_map.py -q
7 passed in 0.06s
```

The focused suite covers valid normalization, missing evidence references, uppercase/nonhex/wrong-length digest keys, mismatched embedded digests, and invalid evidence-basis values.

## Main progression

- `5e00ec10368a893d3ae4d92398f18dc777e4f044` — initial remote main.
- `20f06b94f7f7e5dc26c9d42acaf9ffee6641cb28` — `feat(audit): validate traceable amplitude evidence maps`.
- `a2f9091daf19263d87c514d84aa2e0d385bad27c` — `test(audit): cover traceable amplitude evidence maps`.
- `82eae911f21355ac425da8fa6e2a443375d0c389` — `docs(audit): archive amplitude evidence-reference gate`.
- `dea2482ed13a0403706fc7911b7fe990647e7ee6` — `docs(audit): claim amplitude evidence-reference gate`.
- This handoff update is the final session commit and must be verified on remote `main`.

## Evidence boundary and blockers

- No real pulse table or real amplitude evidence map was available.
- The new validator is currently a standalone preflight gate; v2.9.0 of `amplitude_convention_audit.py` does not yet import it directly.
- No amplitude convention, stopping count, stopping fraction, event CSV, DeltaE-E plot, calibration, or detector-performance result was regenerated.
- Historical A-002 outputs remain quarantined.
- A direct clone failed because this runtime could not resolve `github.com`; authenticated connector reads and writes were used.
- The complete repository test suite and CI were not run.
- `SESSION_LOG.md` was not replaced because safe append semantics were unavailable; the immutable archive preserves the complete run.

## Acceptance status

- Standalone evidence-map traceability validator: VALIDATED by focused synthetic regression.
- Direct integration into the amplitude convention auditor: PARTIAL / OPEN.
- Real-table amplitude convention: BLOCKED on exact data and traceable reviewed evidence.
- A-002 regenerated outputs: BLOCKED.

## Next action

Import or otherwise enforce `validate_payload` inside `amplitude_convention_audit.py` so direct auditor invocation cannot bypass the evidence-reference requirement. Create a real map for the exact A-002 input with an immutable `evidence_reference`, validate it, run the convention auditor without `--max-rows`, review every non-acceptable state and malformed-value warning, and regenerate A-002 only after all gates pass.
