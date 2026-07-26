# Immutable session record — AUD-FIG-004

## Session identity

- Stamp: `2026-07-26T160640Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `cd4c299dbd67e285950a69610e4b27caed4413e1`
- Task: prevent duplicate YAML figure IDs or nested registry fields from silently replacing earlier scientific evidence.
- Policy: `FIGURE_REGISTRY_YAML_KEYS_MUST_BE_UNIQUE_AT_EVERY_MAPPING_DEPTH`

## Repository review

Inspected current `main` history, the completed Cluster E handoff, open PR #939,
current-main status checks, `chatgpt_todo/README.md`, `ACTIVE_TASK.md`, `HANDOFF.md`,
`BACKLOG.md`, `MASTER_INDEX.md`, the paper figure registry, figure-registry loader,
builder, package exports, focused registry tests, and prior figure-registry audit
records. PR #868 remained closed and unmerged; PR #939 remained open, non-mergeable,
and unmerged. No pull request was merged or modified.

## Confirmed defect

The former loader used `yaml.safe_load`. PyYAML silently retained the final value for
duplicate mapping keys. The later `validate_registry` duplicate-ID counter therefore
could not detect duplicate top-level figure IDs because the earlier entry had already
been discarded. Duplicate nested keys such as `status`, `result`, `kind`, `caption`,
or `source_figure` were likewise last-definition-wins.

Deterministic controls:

- duplicate top-level `Q`: legacy loader retained only the second entry (`BLOCKED`,
  `two.json`);
- duplicate nested `status`: legacy loader retained only `BLOCKED`.

Both ambiguous inputs were accepted without an exception by the former algorithm.

## Remediation

`tools/figure_registry/registry.py` now:

1. reads registry bytes exactly once;
2. decodes strict UTF-8;
3. parses through a SafeLoader mapping constructor that rejects duplicate keys at
   every depth and reports both source positions;
4. exposes `RegistrySnapshot` with exact bytes, SHA-256, byte count, entries, and
   `SINGLE_READ_STRICT_UTF8_DUPLICATE_KEY_REJECTING_YAML` policy;
5. preserves the public `load_registry(path) -> list[Entry]` API.

The package exports the new snapshot and format-error contracts. Programmatically
constructed duplicate `Entry` objects remain covered by `validate_registry`.

## Validation

Commands:

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tests/test_figure_registry_duplicate_keys.py \
  tools/audit/render_figure_registry_duplicate_key_evidence.py

PYTHONPATH=. pytest -q tests/test_figure_registry_duplicate_keys.py
```

Results:

- first focused run: `6 passed in 0.07s`;
- final rerun after lint cleanup: `6 passed in 0.04s`;
- corrected duplicate controls: 2/2 rejected;
- invalid UTF-8: controlled `RegistryFormatError`;
- replacement-after-read control: entries, SHA-256, and size remained bound to the
  retained original bytes;
- JSON parse: passed;
- SVG XML parse: passed;
- Python 3.13.5, PyYAML 6.0.3, pytest 9.0.2;
- maximum changed Python line length: 94.

Local SHA-256 identities:

- registry implementation:
  `5b99253798be22c289b4ce268b3f47b28b2e3830d7534beebc84e8ffa277ce13`;
- focused tests:
  `641350db6391ce787d5632f12e1a5097e28343440affc18f70f64bb6f1e5d16a`;
- evidence renderer:
  `765aa33331461b903ffbc0954d1820505b9db0dd375736b101f7ef811c1ecb0b`.

Git blobs on remote `main` after publication include:

- registry implementation: `b1412b82219fd37649107fd4452e5f859450ca82`;
- focused tests: `ed603890f0a503a44f75d7245e443ffccac9ac92`;
- evidence renderer: `865adedabcf56436ac7aefda0b29079ed70e6b36`;
- visual evidence: `789ca373c87e8ac43c537c050349b9d7be83c233`.

## Direct-main sequence through evidence publication

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
- `4842a9fe29707838030e8e03f6d9b54195c82226` — refreshed visual evidence.

GitHub contents writes returned successful direct-main commit SHAs rather than a
conventional terminal `git push` transcript. No force update or history rewrite was
used.

## Scientific boundary and unrun checks

This is software/schema integrity evidence. No registry entry's scientific content,
source result, input table, uncertainty, caption, or figure was independently
validated. No paper figure was regenerated. Repository-wide pytest, ruff, the
complete paper build, full shipped-registry build, link inventory, and GitHub Actions
were not run and are not claimed as passing. No calibration, timing, PID, stopping,
pile-up, or detector-performance quantity was produced or changed.

## Coordination limitation

The connector supports paged reads and whole-file replacement, not byte-safe append.
`SESSION_LOG.md` and the long aggregate matrices could not be safely reconstructed
without risking existing append-only provenance. This immutable record and the latest
handoff retain the complete append-equivalent session record. The unmet aggregate
synchronization requirement is explicit and is not reported as completed.
