# Nature-aligned quantitative figure standard

## Fixed layout

- 89 mm single-column and 183 mm double-column widths;
- maximum 170 mm height;
- editable embedded sans-serif text at 5–7 pt;
- lowercase bold panel labels at 8 pt;
- final line weights 0.25–1 pt;
- white background and no decorative grid, icons, shadows or rainbow maps;
- accessible color palette with marker/line redundancy.

## Required outputs

Every quantitative figure produces:

- PDF and SVG vector output;
- 600-dpi PNG;
- exact plotted source CSV;
- input/source/output SHA-256;
- evidence class and claim status;
- exact n and independence unit;
- error-bar/interval definition;
- transformations, selections and units;
- spike/outlier/clipping/duplicate/missing-data scan.

## Statistical display

- show raw points, ECDFs, distributions or quantile summaries for sampled data;
- use bars only for genuine counts/compositions;
- include residual/ratio panels for comparisons;
- do not connect estimates when a line would imply unsupported interpolation;
- group discrete variables by exact value rather than quantile bins when testing discrete formulas;
- distinguish event SEM, between-seed variation, device uncertainty and model discrepancy.

## Fail-closed behavior

The plot system may not guess a scientific plot from arbitrary columns or substitute literal fallback values. It must fail when:

- the result/source bundle is missing;
- required columns/units are absent;
- hashes disagree;
- claim status is not approved for the target surface;
- an invalid/truncated run is included;
- exact n or error definition is missing.

## Anomaly classification

- `FAIL`: physical or data-integrity violation;
- `REVIEW`: unexplained or model-sensitive structure;
- `EXPECTED`: classified model/acquisition structure.

No flagged row is removed automatically. Exclusion requires a recorded cause and sensitivity result.

## Repository migration

1. quarantine `scripts/generate_all_figures.py` for quantitative publication;
2. retain the figure registry provenance gate;
3. replace its generic emitter with declared plot-type plugins;
4. migrate timing, gain, pile-up, PID, stopping, anomaly and systematics figures first;
5. do not redraw blocked claims as accepted results.
