# Publication-figure generator migration

`scripts/generate_publication_figures.py`: **embedded constants -> result registry**

Fixes KNOWN_CODE_DEFECTS.md (`generate_publication_figures.py`) + v2 governance
finding #10: headline values were hard-coded Python constants, and illustrative
schematics were mixed in with quantitative figures.

## What changed

- The script is now a **thin driver** over
  `tools.figure_registry.builder.build(...)`. It holds **no headline numbers**.
- Every quantitative figure's central value + uncertainty is read **only** from
  a validated result JSON / source table (never a literal). A missing result or
  a missing uncertainty on a build-eligible entry **FAILS** the build.
- Illustrative schematics are `kind: illustrative` in `paper/figures.yaml` and
  render into a **separate** `<out>/illustrative/` directory, clearly labelled
  "SCHEMATIC -- not quantitative evidence".
- The builder writes `<out>/build_report.json` with per-entry `PASS`/`FAIL`/
  `BLOCKED` + reason and a summary (counts, quantitative vs illustrative).

Registry backend + failure semantics: `tools/figure_registry/README.md`.

## CLI

```bash
python scripts/generate_publication_figures.py --registry paper/figures.yaml --out paper/figures
python scripts/generate_publication_figures.py --allow-preliminary   # include PRELIMINARY
python scripts/generate_publication_figures.py --strict              # nonzero unless all quant built
python scripts/generate_publication_figures.py --help
```

- **non-strict (default)**: exits 0 while quantitative results are compute-blocked
  (reported BLOCKED -- an honest default). A genuine hard failure (missing
  result/uncertainty, sha256 mismatch, malformed registry) still exits nonzero.
- **`--strict`**: exits nonzero if ANY quantitative entry is not built (any FAIL,
  or any BLOCKED quantitative entry).

## Before -> after: constants -> registry entries

Every removed constant block and where its numbers now come from:

| Old constant (removed)                | Old figure fn              | Registry entry(ies)     | Status now        |
|---------------------------------------|----------------------------|-------------------------|-------------------|
| `STAVE_TIMING`, `TIME_RES`            | `fig02_timing_resolution`  | `TIME-01`, `TIME-02`    | EXTERNAL_BLOCKER  |
| `MC_VS_DATA` (timing pull)            | `fig03_mc_vs_data`         | `TIME-03`               | EXTERNAL_BLOCKER  |
| `MC_VS_DATA` (pile-up Rmax/tau)       | `fig03_mc_vs_data`         | `PU-01`                 | EXTERNAL_BLOCKER  |
| `PCA_AE`                              | `fig04_pca_ae`             | `PS-01`                 | EXTERNAL_BLOCKER  |
| `STOPPING`                           | `fig05_stopping_depth`     | `MV3-01`                | EXTERNAL_BLOCKER  |
| `PID_DATA`                           | `fig06_pid_auc`            | `PID-01`                | EXTERNAL_BLOCKER  |
| `SYST_BUDGET`                        | `fig07_systematic_budget`  | `SYS-01`                | EXTERNAL_BLOCKER  |
| inline `d_frac_I` / `d_frac_II`      | `fig12_d_fraction_vs_layer`| `DE-01`, `DE-02`        | EXTERNAL_BLOCKER  |

Illustrative schematics (simulated / qualitative -- no measured numbers), kept
separate under `illustrative/`:

| Old figure fn        | What it draws                         | Registry entry | Kind         |
|----------------------|---------------------------------------|----------------|--------------|
| `fig01_setup`        | beamline / detector geometry          | `SCH-01`       | illustrative |
| `fig08_timewalk`     | timewalk correction (simulated)       | `SCH-02`       | illustrative |
| `fig09_waveform`     | annotated waveform (simulated pulse)  | `SCH-03`       | illustrative |
| `fig10_ml_landscape` | ML-advantage landscape (qualitative)  | `SCH-04`       | illustrative |
| `fig11_deltaE_E`     | Delta-E-E scatter analogue (simulated)| `SCH-05`       | illustrative |

The old bespoke matplotlib drawing code for the schematics was **removed** from
the driver (a thin driver holds no drawing code): illustrative entries are now
rendered by the registry's dedicated, clearly-labelled illustrative path, which
structurally guarantees they are never mistaken for quantitative evidence.

## Promoting `EXTERNAL_BLOCKER` -> `VALIDATED`

The analysis result JSONs live in external worker stores and are not in this
checkout, so quantitative entries are `EXTERNAL_BLOCKER` (reported BLOCKED, never
FAIL). Once a result file exists on disk:

1. **Sync the result** to the `result:` path in the entry (e.g.
   `reports/mv1_pid/result.json`). It must contain the entry's `value_key` and
   `uncertainty_key` (top-level or one level of nesting). If a `table:` is set,
   sync it too.
2. **(Optional) pin the source table**: compute
   `python -c "from tools.figure_registry import sha256_file; print(sha256_file('<table>'))"`
   and set `input_sha256:` on the entry. A later mismatch is a hard failure.
3. **Flip `status:`** from `EXTERNAL_BLOCKER` to `VALIDATED` (or `TENSION` for a
   stated data/MC tension -- its caption must name the tension; e.g. `TIME-03`).
4. **Rebuild**:
   `python scripts/generate_publication_figures.py --strict`.
   The entry now builds `<id>.png` + `<id>_source_data.csv`, and `--strict`
   passes once no quantitative entry remains blocked.

If a synced result is missing its uncertainty, the build **FAILS** (by design) --
add the uncertainty to the result JSON rather than hand-entering a number here.
