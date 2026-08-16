# AUD-FIG-005 — Figure-registry build-report snapshot provenance

## Scope and policy

Policy: `FIGURE_BUILD_REPORT_MUST_BIND_TO_EXACT_REGISTRY_SNAPSHOT`.

This focused unit reviews the boundary between `paper/figures.yaml`, the duplicate-key-safe registry loader, the paper-figure builder, and `build_report.json`. It does not review the scientific correctness of any registry entry.

## Confirmed defect

The registry layer already produced a `RegistrySnapshot` containing the exact bytes, SHA-256, byte count, parsed entries, and snapshot method. The builder nevertheless called `load_registry(path)`, received only a list of entries, and wrote only the registry path to `build_report.json`. A later reviewer could not prove which exact registry bytes authorized the report.

`RegistryFormatError` also sat outside the builder's `FigureRegistryError` boundary. Duplicate-key, invalid-UTF8, or malformed-YAML input could therefore escape the controlled CLI diagnostic caught by `main()`.

## Remediation

`tools/figure_registry/builder.py` now:

1. calls `load_registry_snapshot(path)` exactly once;
2. converts `RegistryFormatError` to `FigureRegistryError`;
3. derives entries from the retained snapshot;
4. records `path`, SHA-256, byte count, snapshot method, and entry count under `registry_provenance` in every valid or structurally invalid `build_report.json`;
5. preserves the existing top-level `registry` path for compatibility.

Format-invalid inputs do not produce a misleading build report because no trustworthy parsed entry set exists. The CLI returns status 1 with one `FigureRegistryError:` diagnostic and no traceback.

## Independent controls

A quarantined one-entry registry was 76 bytes with SHA-256 `bc4a5a1552f098c89b11f12a1bf29b8442b32f44cb7e1caa4afe3c143a321345`; all five provenance fields matched exactly.

A replacement-after-snapshot control parsed an 83-byte `ORIGINAL` registry with SHA-256 `7cf6295508bdca2d085fc4799c2bcd8da0a6c9ac2b7d1bf8fe1607b31ca4baef`, then replaced the path with an 86-byte `REPLACEMENT` registry whose SHA-256 was `ba5ccd85b1e665c470da7fb1488edc5bfc6ece7887a8f4a74b13a8f124046841`. The report retained the original entry, hash, and size.

Duplicate top-level YAML keys and invalid UTF-8 both returned controlled status 1 without a traceback. A structurally invalid but unambiguous 66-byte registry still produced an `INVALID_REGISTRY` report bound to SHA-256 `03cee6353b6d18dd2fcde3f1900a2e5db78a8c62206deaed5ad8227c3694efcd`.

## Validation

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tools/figure_registry/builder.py \
  tests/test_figure_registry_duplicate_keys.py \
  tests/test_figure_registry_build_report_provenance.py

PYTHONPATH=. pytest -q \
  tests/test_figure_registry_duplicate_keys.py \
  tests/test_figure_registry_build_report_provenance.py

12 passed in 0.28s
```

Environment: Python 3.13.5, pytest 9.0.2, Matplotlib 3.10.8, PyYAML 6.0.3.

Exact identities:

- builder Git blob `39dcd3b13d3886c43f3e9111291d420f86cc7c85`, 18,264 bytes, SHA-256 `78feca87c3693f4ccabc319043531b7b6b5d767f4270471d3d939a258d75ae76`;
- focused-test Git blob `f242097b78f812327f846e942b8eb0f589675d4b`, 4,779 bytes, SHA-256 `486abf6a3f7eabb4f4883515c3a9ac61db0a9f79ef0419a754486468cdfab046`;
- maximum changed Python line length: 93 characters;
- validation JSON parsed;
- SVG parsed as XML.

## Acceptance and limitations

The focused provenance/error-boundary remediation is `VALIDATED / COMPLETE`.

Repository-wide pytest and ruff, the complete shipped-registry build, paper build, link inventory, and GitHub Actions were not run. No registry entry, paper figure, numerical result, uncertainty, calibration, timing, PID, stopping profile, pile-up rate, or detector-performance claim was independently validated or changed.
