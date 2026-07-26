# Figure-registry duplicate-key integrity audit

## Scope

Task `AUD-FIG-004` reviews the YAML ingestion boundary used by the paper-figure
registry. The software decides whether a figure is build-authorized, quarantined,
blocked, illustrative, or invalid. Ambiguity at this boundary can therefore change
which scientific evidence is published without changing any downstream validator.

Policy:

`FIGURE_REGISTRY_YAML_KEYS_MUST_BE_UNIQUE_AT_EVERY_MAPPING_DEPTH`

Initial remote `main`: `cd4c299dbd67e285950a69610e4b27caed4413e1`.
Former registry-loader Git blob:
`b1381ccc471eb4711251cb2d0471950f60610c68`.

## Confirmed defect

The former loader used `yaml.safe_load` and then attempted to detect duplicate figure
IDs in the already materialized Python mapping. Standard PyYAML mapping construction
uses last-definition-wins semantics. A duplicate top-level figure ID is therefore
collapsed before `validate_registry` sees it. The same applies to duplicate nested
fields such as `status`, `result`, `kind`, `caption`, or `source_figure`.

Two deterministic controls demonstrate the failure:

1. A second `Q:` figure definition silently replaced the first. The retained status
   became `BLOCKED` and the retained result became `two.json`.
2. A second nested `status:` silently replaced `VALIDATED` with `BLOCKED`.

In both cases `yaml.safe_load` returned a normal mapping and raised no error. The
post-load duplicate-ID counter cannot recover keys already discarded by the parser.
This is an input-integrity defect: a duplicate field could silently promote,
downgrade, redirect, or replace scientific evidence before build disposition is
evaluated.

## Remediation

`tools/figure_registry/registry.py` now provides a strict SafeLoader subclass whose
mapping constructor rejects duplicate keys at every depth and reports both source
locations. Registry bytes are read once, decoded as strict UTF-8, parsed from that
retained text, and exposed through `RegistrySnapshot` with exact bytes, SHA-256, byte
count, entries, and snapshot policy:

`SINGLE_READ_STRICT_UTF8_DUPLICATE_KEY_REJECTING_YAML`

The public `load_registry(path) -> list[Entry]` API is preserved. New snapshot and
format-error types are exported by the package. The existing programmatic duplicate
entry check remains useful for callers that construct `Entry` lists directly.

## Validation

Executed in the local validation environment:

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tests/test_figure_registry_duplicate_keys.py \
  tools/audit/render_figure_registry_duplicate_key_evidence.py

PYTHONPATH=. pytest -q tests/test_figure_registry_duplicate_keys.py

6 passed in 0.07s
```

Environment:

- Python 3.13.5
- PyYAML 6.0.3
- pytest 9.0.2

Regression coverage includes legacy last-key-wins behavior, duplicate top-level IDs,
duplicate nested status fields, replacement after byte acquisition, invalid UTF-8,
and a valid unambiguous registry. The corrected controls rejected 2/2 duplicate
fixtures before validation or build. JSON parsing and SVG XML parsing passed.

Changed-file local identities before publication:

- `registry.py`: 9,901 bytes; SHA-256
  `5b99253798be22c289b4ce268b3f47b28b2e3830d7534beebc84e8ffa277ce13`;
  maximum line length 94.
- focused test: 3,244 bytes; SHA-256
  `641350db6391ce787d5632f12e1a5097e28343440affc18f70f64bb6f1e5d16a`;
  maximum line length 92.

Machine-readable evidence:
`docs/validation/figure_registry_duplicate_key_validation.json`.
Visual evidence:
`docs/validation/figure_registry_duplicate_key.svg`.

## Better-method comparison

Post-load duplicate counting is simple but cannot observe discarded YAML keys. A
regex scan is format-fragile and cannot reliably distinguish mapping depth, quoted
keys, aliases, or comments. A duplicate-rejecting SafeLoader operates at the YAML
mapping-construction boundary, preserves safe-tag handling, reports exact locations,
and prevents ambiguous bytes from reaching scientific disposition logic. This is the
selected method.

## Acceptance boundary

This focused software/schema remediation is `VALIDATED / COMPLETE`. It does not
validate the scientific content of any current registry entry, source result, table,
caption, uncertainty, or generated figure. No paper build or figure was regenerated.
Repository-wide pytest, ruff, the complete shipped registry build, link inventory,
and GitHub Actions were not run and are not claimed as passing.
