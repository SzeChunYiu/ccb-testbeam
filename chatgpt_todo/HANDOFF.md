# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-001`
- **Stamp:** `2026-07-26T061216Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `d046259666a08dbf9188e8a80d5a3b0cbced5765`
- **Validated delivery/handoff commit:** `2cb5bcb70461c66e04927945af564344db79de8b`
- **Remote main after validated delivery:** `2cb5bcb70461c66e04927945af564344db79de8b`
- **Destination:** direct commits to `main`; no task branch, force-push, history rewrite, or PR merge.
- **Focused acceptance:** audit tooling and evidence `VALIDATED / COMPLETE`.
- **Repository acceptance:** figure-registry schema remains `FLAWED / PARTIAL`.

## Work completed

Added a fail-closed audit for the paper figure registry's controlled vocabulary and structural contract.

Policy:

`FIGURE_REGISTRY_SCHEMA_MUST_ACCEPT_ITS_SHIPPED_VOCABULARY`

The current implementation accepts five statuses and two kinds. The shipped `paper/figures.yaml` uses ten statuses and three kinds. It uses six unsupported statuses and the unsupported kind `figure_sourced`. Five illustrative entries intentionally carry `source_figure` without `result`, but the validator requires `result` unconditionally. The existing test freezes the obsolete five-status set while separately asserting the shipped registry validates.

## Quantitative audit result

- Used statuses: 10.
- Allowed statuses: 5.
- Unsupported used statuses: 6.
- Used kinds: 3.
- Allowed kinds: 2.
- Unsupported used kinds: 1.
- Illustrative entries rejected by the false result requirement: 5.
- Current-like audit findings: 9.
- Corrected-contract findings: 0.

Finding families:

- `REGISTRY_STATUS_UNSUPPORTED`
- `REGISTRY_KIND_UNSUPPORTED`
- `ILLUSTRATIVE_RESULT_FALSE_REQUIREMENT`
- `TEST_FREEZES_OBSOLETE_STATUS_SET`

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_schema_alignment.py \
  tests/test_audit_figure_registry_schema_alignment.py \
  tools/audit/render_figure_registry_schema_evidence.py

pytest -q tests/test_audit_figure_registry_schema_alignment.py

5 passed
```

Also passed: corrected zero-finding fixture, controlled invalid UTF-8, destructive output alias rejection, atomic JSON publication, JSON parse, and SVG XML parse.

## Files

Added:

- `tools/audit/audit_figure_registry_schema_alignment.py`
- `tests/test_audit_figure_registry_schema_alignment.py`
- `tools/audit/render_figure_registry_schema_evidence.py`
- `docs/validation/figure_registry_schema_alignment_validation.json`
- `docs/validation/figure_registry_schema_alignment.svg`
- `docs/validation/figure_registry_schema_alignment_audit.md`
- `chatgpt_todo/archive/2026-07-26T061216Z_AUD-FIG-001_SCHEMA_ALIGNMENT.md`

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`

## Repository provenance

- `tools/figure_registry/registry.py` blob: `0828d42c50e697bdc793d46d8bd23c4a57e3054d`
- `paper/figures.yaml` blob: `5d03f284fd2e018fcda786313f46c64ea7a20105`
- `tests/test_figure_registry.py` blob: `1546b8b6896fdbbdce28cfb53fccc8d727479436`

The container could not resolve `github.com`. Current repository semantics were reconstructed from authenticated connector reads and labelled as a semantic excerpt, not a byte-identical local checkout.

## Direct-main commits

- `e51e06686069d0bc6db44fccbee4bbdd4cc83675` — audit gate;
- `312c312db89c3b8a790132fca3dee7a5043b9787` — focused tests;
- `a399d38dc345ebca92bf9d76387770b6bb607ff3` — evidence renderer;
- `b5dc555317df494f7e93af241f3873ce918d3747` — machine-readable evidence;
- `6cd783490d03559e84ac58452a75432b95251537` — visual evidence;
- `3b9ca56daea084f54bf05fa25e033541e8f94809` — audit report;
- `a117edc54fc04025d3ffb858f5c547d6e638fdcf` — immutable archive;
- `a8cc8edc031148dcef8129defb8b472bed6b8a60` — active-task update;
- `2cb5bcb70461c66e04927945af564344db79de8b` — validated delivery handoff.

GitHub returned successful direct-main commit SHAs for every write. Post-write history confirmed the handoff and all focused ancestors consecutively on remote `main`; no force update was used.

## Next exact unit

Remediate the registry and builder together:

1. define the complete status vocabulary;
2. map statuses explicitly to build dispositions;
3. support a source-figure-only kind;
4. make path requirements conditional on kind and disposition;
5. update tests without downgrading scientific states;
6. require the exact shipped registry to validate;
7. run focused builder tests and the repository-wide gate.

## Scientific boundary

No figure was regenerated. No source value, uncertainty, calibration, PID result, timing result, stopping profile, pile-up rate, or detector-performance claim was validated or changed.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were not replaced. Only whole-file replacement is available while their complete current contents are paged or truncated; a partial reconstruction could erase append-only or concurrent provenance. The immutable archive contains the append-equivalent record. This mandatory synchronization gap remains explicit.
