# figure_registry — validated paper-figure builder

Binds every CCB test-beam paper figure to a **validated result file** so that no
quantitative figure ever reads a hand-entered constant. Replaces the pattern in
`scripts/generate_publication_figures.py`, which embedded headline values as
Python constants and mixed illustrative schematics with quantitative figures
(KNOWN_CODE_DEFECTS.md + v2 governance finding #10).

## Registry format (`paper/figures.yaml`)

Top-level mapping of `id -> entry`:

```yaml
TIME-01:
  result: reports/mv4_timing_1782678162/result.json   # required: result JSON
  table:  reports/mv4_timing_1782678162/tables/residual_source.csv  # optional
  input_sha256: <hex>          # optional: pinned sha256 of `table`
  uncertainty_key: sigma68_ns_ci95   # optional, default 'uncertainty'
  value_key: sigma68_ns        # optional: which JSON key is the central value
  status: VALIDATED            # required
  kind: quantitative           # required: 'quantitative' | 'illustrative'
  caption: >-                  # required: conclusion-bearing caption
    B6 single-stave timing resolution (sigma68) with 95% CI.
```

Field notes:

| field             | required | meaning                                                        |
|-------------------|----------|----------------------------------------------------------------|
| `result`          | yes      | path to the result JSON that drives the figure                 |
| `status`          | yes      | one of the allowed statuses (below)                            |
| `kind`            | yes      | `quantitative` (built from the result) or `illustrative`       |
| `caption`         | yes      | conclusion-bearing caption printed on the figure               |
| `table`           | no       | source table (`.csv`/`.parquet`) plotted / hashed              |
| `input_sha256`    | no       | recorded sha256 of `table`; mismatch is a hard failure         |
| `uncertainty_key` | no       | key holding the uncertainty (default `uncertainty`)            |
| `value_key`       | no       | key holding the central value (else inferred)                  |

The central value and uncertainty are read from the result JSON at build time
(top-level or one level of nesting, e.g. inside a `winner_metrics` block). A CI
pair `[lo, hi]` is accepted for the uncertainty (half-width is used).

## Allowed statuses

```
VALIDATED, PRELIMINARY, TENSION, EXTERNAL_BLOCKER, ILLUSTRATIVE
```

* **VALIDATED / TENSION** — built into a quantitative figure. `TENSION` figures
  must state the tension in their caption.
* **PRELIMINARY** — excluded from the paper build (reported BLOCKED) unless
  `--allow-preliminary` is passed.
* **EXTERNAL_BLOCKER** — result compute-blocked / not yet on disk. Reported
  **BLOCKED**, never a hard failure.
* **ILLUSTRATIVE** — a schematic. Requires `kind: illustrative`, is rendered into
  a **separate** `illustrative/` sub-directory, clearly labelled "SCHEMATIC —
  not quantitative evidence", and is never counted among the quantitative
  figures.

`kind: illustrative` implies `status: ILLUSTRATIVE` and vice-versa — schematics
are structurally kept apart from quantitative figures.

## Failure conditions (nonzero exit / `FigureRegistryError`)

The build **fails** (writes a `build_report.json`, then raises) when:

1. a referenced **result file is missing** (for a build-eligible status);
2. the **uncertainty key is missing or null** on a quantitative entry;
3. the source-table **sha256 disagrees** with the recorded `input_sha256`;
4. a figure **status is not in the allowed set** (or the registry is otherwise
   structurally malformed: duplicate id, missing `result`/`caption`/`kind`,
   ILLUSTRATIVE/illustrative mismatch, `input_sha256` without a `table`).

`EXTERNAL_BLOCKER` (missing result) and default-gated `PRELIMINARY` are reported
**BLOCKED**, not FAIL.

## Outputs

Into `--out`:

* `<id>.png` — one figure per built quantitative entry (matplotlib Agg), driven
  only by values read from the result JSON / source table;
* `<id>_source_data.csv` — the exact numbers + provenance used for that figure;
* `illustrative/<id>.png` (+ `_source_data.csv`) — schematics, kept separate;
* `build_report.json` — per-entry `PASS` / `FAIL` / `BLOCKED` + reason, plus a
  summary (counts, `quantitative_figures`, `illustrative_figures`).

## Build command

```bash
python -m tools.figure_registry.builder --registry paper/figures.yaml --out paper/figures
# include PRELIMINARY figures:
python -m tools.figure_registry.builder --registry paper/figures.yaml --out paper/figures --allow-preliminary
python -m tools.figure_registry.builder --help
```

## Python API

```python
from tools.figure_registry import build, validate_registry, load_registry, FigureRegistryError
report = build("paper/figures.yaml", "paper/figures", paper_only=True)
```
