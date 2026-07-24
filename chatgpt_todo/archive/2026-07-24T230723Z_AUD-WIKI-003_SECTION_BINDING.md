# AUD-WIKI-003 — MV3 public-WIKI section-binding gate

- **UTC stamp:** `2026-07-24T230723Z`
- **Initial remote main:** `4480ca889250e1915d963e7c646cd5ebf923a201`
- **Owner:** scheduled scientific-review session
- **Destination:** direct sequential commits to `main`
- **Acceptance:** COMPLETE for the validator/evidence unit

## Reviewed

Recent main history, repository metadata, open pull requests, current commit status,
coordination README, active task, latest handoff, root WIKI, canonical MV3 ledger
rows and tracked summary, existing MV3 validator and tests, and prior validation
artifacts.

## Finding

The existing MV3 validator checks exact tokens globally. A token appendix can satisfy
that predicate while the canonical public row remains rounded. This is a claim-binding
loophole.

## Work

Added:

- `tools/audit/validate_wiki_mv3_section_binding.py`;
- `tools/audit/render_wiki_mv3_section_binding_evidence.py`;
- `tests/test_validate_wiki_mv3_section_binding.py`;
- `docs/validation/wiki_mv3_section_binding_audit.md`;
- `docs/validation/wiki_mv3_section_binding_validation.json`;
- `docs/validation/wiki_mv3_section_binding.svg`;
- this archive.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`;
- `chatgpt_todo/HANDOFF.md`.

## Validation

```text
python -m py_compile   tools/audit/validate_wiki_mv3_section_binding.py   tools/audit/render_wiki_mv3_section_binding_evidence.py   tests/test_validate_wiki_mv3_section_binding.py

PYTHONPATH=. python -m pytest tests/test_validate_wiki_mv3_section_binding.py -q
5 passed in 0.03s
```

Current exact WIKI: `FLAWED`, seven findings.
Synthetic global-token/rounded-row fixture: `FLAWED`, two findings.
Corrected structured fixture: `VALIDATED`, zero findings.
JSON and SVG parsing passed.

## Boundary

No ROOT, Geant4, detector-data, or simulation rerun was performed. The MV3
diagnostic remains `FLAWED` under `BLK-MV3-LEGACY-001`.

`SESSION_LOG.md` and shared aggregate ledgers are not replaced because the connector
does not provide byte-safe append/patch semantics and their current contents are
long-lived and potentially concurrent. This immutable record and the latest handoff
provide the complete append-equivalent session record.
