# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-004`
- **Stamp:** `2026-07-26T160640Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `cd4c299dbd67e285950a69610e4b27caed4413e1`
- **Validated implementation/evidence main after:** `2e9d6788b6854207ad041b344e9ea6d7e8d1e528`
- **Destination:** sequential authenticated commits directly to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push output:** each GitHub contents write returned a successful direct-main commit SHA; the connector does not provide a conventional terminal `git push` transcript.
- **Remote-main confirmation:** post-write commit history and exact file reads confirmed the implementation, tests, evidence, archive, and completed active-task record on `main`.
- **Acceptance:** focused software/schema remediation `VALIDATED / COMPLETE`.

## Confirmed defect

The paper-figure registry loader used `yaml.safe_load`, which silently applies
last-definition-wins semantics to duplicate YAML mapping keys. A duplicate top-level
figure ID was therefore collapsed before the later duplicate-ID counter could see it.
Duplicate nested fields such as `status`, `result`, `kind`, `caption`, or
`source_figure` could likewise silently replace earlier scientific evidence or build
dispositions.

Deterministic controls showed:

- duplicate top-level `Q` retained only the later `BLOCKED` / `two.json` entry;
- duplicate nested `status` retained only the later `BLOCKED` value;
- the former `yaml.safe_load` raised no error for either input.

## Remediation

Policy:

`FIGURE_REGISTRY_YAML_KEYS_MUST_BE_UNIQUE_AT_EVERY_MAPPING_DEPTH`

`tools/figure_registry/registry.py` now reads registry bytes exactly once, decodes
strict UTF-8, and parses with a SafeLoader mapping constructor that rejects duplicate
keys at every mapping depth while reporting both source positions. `RegistrySnapshot`
binds the exact bytes, SHA-256, byte count, entries, and snapshot method:

`SINGLE_READ_STRICT_UTF8_DUPLICATE_KEY_REJECTING_YAML`

The public `load_registry(path) -> list[Entry]` API is preserved, and the package
exports the new snapshot and format-error contracts.

## Validation

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tests/test_figure_registry_duplicate_keys.py \
  tools/audit/render_figure_registry_duplicate_key_evidence.py

PYTHONPATH=. pytest -q tests/test_figure_registry_duplicate_keys.py

6 passed in 0.07s
final rerun: 6 passed in 0.04s
```

Additional results:

- corrected duplicate controls: 2/2 rejected;
- invalid UTF-8: controlled `RegistryFormatError`;
- replacement-after-read control: entries, hash, and size remained bound to retained original bytes;
- JSON parse: passed;
- SVG XML parse: passed;
- Python 3.13.5, PyYAML 6.0.3, pytest 9.0.2;
- maximum changed Python line length: 94.

Exact published Git blobs include:

- registry implementation: `b1412b82219fd37649107fd4452e5f859450ca82`;
- focused tests: `ed603890f0a503a44f75d7245e443ffccac9ac92`;
- evidence renderer: `865adedabcf56436ac7aefda0b29079ed70e6b36`;
- visual evidence: `789ca373c87e8ac43c537c050349b9d7be83c233`.

## Files delivered

- `tools/figure_registry/registry.py`
- `tools/figure_registry/__init__.py`
- `tests/test_figure_registry_duplicate_keys.py`
- `tools/audit/render_figure_registry_duplicate_key_evidence.py`
- `docs/validation/figure_registry_duplicate_key_validation.json`
- `docs/validation/figure_registry_duplicate_key.svg`
- `docs/validation/figure_registry_duplicate_key_audit.md`
- `chatgpt_todo/archive/2026-07-26T160640Z_AUD-FIG-004_DUPLICATE_KEYS.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this handoff.

## Direct-main sequence

- `5b93717cffd5763bd81608ac39fdd5f7cd258f25` — task claim;
- `9ed2d099c2120be8d3ddf96885812591e999b88a` — duplicate-key-safe loader;
- `dddab6968870f3f50c467fe93f375b2a6e697338` — package exports;
- `bba1b581e490e852abe13a890cffc59ca6cfa158` — focused regressions;
- `072540efb769f8e8f0f2f9a111e32a0999369633` — evidence renderer;
- `caca15b2d46c9860a4b52c3762162e366bf60387` — deterministic evidence paths;
- `6b48c35d77612268cf471c504c15138af1aff8c8` — machine-readable evidence;
- `0b9c276d886be46a432822fd59f22634e0ebe7f0` — initial visual evidence;
- `ff59e6616d319c1385aad233fe66dc0ac37fc0b5` — audit report;
- `4340fb9c213f7f993c4f935a21300a82ee5c6836` — lint-clean renderer;
- `4842a9fe29707838030e8e03f6d9b54195c82226` — refreshed visual evidence;
- `4adbd8139f0b40718f9b3df614dc9ecb27e5cab1` — immutable archive;
- `2e9d6788b6854207ad041b344e9ea6d7e8d1e528` — completed active-task record.

## Scientific boundary and unresolved coordination

This unit validates software/schema integrity only. No registry entry's scientific
content, source result, input table, uncertainty, caption, or figure was independently
validated. No paper figure or scientific quantity was regenerated. Repository-wide
pytest/ruff, the complete shipped-registry build, paper build, link inventory, and
GitHub Actions were not run and are not claimed as passing.

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and the long aggregate matrices were
reviewed but not partially reconstructed. Connector reads are paged or truncated
while writes replace the entire file; transcription could erase append-only or
concurrent provenance. The immutable archive above contains the complete
append-equivalent record. This unmet mandatory synchronization step is explicit and
is not reported as completed.

## Next action

Integrate `RegistrySnapshot` provenance into `build_report.json`, convert registry
format failures into a controlled `FigureRegistryError` CLI diagnostic, and run the
complete shipped registry plus paper build in a clean checkout. Scientific acceptance
of individual figures remains a separate item-level review.
