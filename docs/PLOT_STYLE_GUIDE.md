# CCB publication-plot style contract

## Scope

This contract governs figures shown in `WIKI.md`, staged GitHub Wiki pages and the paper registry. Historical diagnostic plots remain auditable, but they are not publication figures unless they are regenerated through the controlled pipeline.

The governing principle is **evidence before decoration**: one scientific question per figure, one source table per figure, an explicit evidence class, and no visual element that implies more certainty than the underlying result supports.

## External guidance used

The implementation follows the parts of the following guidance that are compatible with the CCB analysis and its target journals:

- [Nature Portfolio final artwork guidance](https://www.nature.com/nature-portfolio/for-authors/final-submission/final-artwork): size artwork near its publication dimensions, retain vector graphics when possible, and ensure labels remain readable after reduction.
- [Matplotlib style sheets and `rcParams`](https://matplotlib.org/stable/users/explain/customizing.html): centralize visual defaults rather than hand-tuning each script.
- [mplhep style documentation](https://mplhep.readthedocs.io/en/latest/guide/): useful HEP conventions and experiment-style patterns; CCB uses its own neutral experiment label rather than copying a collaboration identity.
- [Okabe–Ito colour-universal-design palette](https://jfly.uni-koeln.de/color/): use colour-blind-safe categorical colours and never encode a conclusion by colour alone.

Journal requirements differ. The exact target-journal artwork specification takes precedence at submission time, but changes must preserve the scientific and provenance rules below.

## Mechanical requirements

| Property | Contract |
|---|---|
| Single-column width | 89 mm |
| Double-column width | 183 mm |
| Maximum normal height | 170 mm |
| Default text | 7 pt |
| Minimum rendered text | 5 pt |
| Primary line width | 0.8–1.0 pt |
| Axes/spines | 0.5–0.7 pt; top and right spines absent unless scientifically needed |
| Raster delivery | PNG at exactly 600 dpi |
| Vector delivery | PDF and SVG beside every PNG |
| SVG text | Editable text, not path-converted glyphs |
| Background | White; no dark theme |
| Grid | Light, on at most the value axis, and only when it improves quantitative reading |
| Export | Deterministic metadata, atomic writes and SHA-256 hashes |

The generator must fail if dimensions, formats, source tables or hashes are missing. A visually attractive plot that lacks source evidence is a failed build.

## Information design

1. **One question per panel.** The title is a short noun phrase. The full scientific interpretation belongs in the external caption.
2. **No dashboard prose inside the axes.** Do not put status paragraphs, caveat boxes, sample descriptions or conclusions in the plotting region.
3. **No overlapping legends.** Prefer direct encodings, short legends in unused space, or legends outside the data region. A legend may not obscure a point, uncertainty bar, curve or bin.
4. **No redundant labels.** Axis labels contain the variable and unit. Avoid repeating the same quantity in a title, annotation and legend.
5. **Do not connect categorical observations.** Independent folds, methods and detector categories are dots or intervals, not lines suggesting continuity.
6. **Show the relevant uncertainty.** Use intervals for proportions and estimates. State in the caption whether they are statistical, systematic, heuristic or model spread.
7. **Preserve support.** Curves must be accompanied by actual scan points or bin support when the reader might otherwise infer untested interpolation.
8. **Do not hide failures.** Tensions and null results use the same visual quality as successful closure results. Styling cannot promote `GATED`, `BLOCKED`, `TENSION`, `FLAWED`, `SUPERSEDED` or simulation-only evidence.
9. **Colour is secondary.** Shape, position, line style or text must also distinguish categories. Avoid rainbow maps and red–green-only contrasts.
10. **No fabricated examples on quantitative surfaces.** Mock waveforms and random illustrative data are separated from result figures and labelled `ILLUSTRATIVE` when retained at all.

## Plot-family decisions

| Scientific question | Selected form | Why |
|---|---|---|
| Exact selected-pulse composition | Horizontal stacked bars | Shows total and stave composition without eight value labels |
| Claim-governance state | Ordered horizontal bars | Long categorical labels remain readable; status count is the only encoded value |
| Timing estimators | Dot/lollipop comparison | Methods are categorical and share one physical scale |
| Grouped-fold PID stability | Independent points plus full-sample reference | A line between folds would imply an ordering or trajectory that does not exist |
| ADC gain closure | Species dots plus configured reference | Emphasizes agreement and scale without a decorative fit panel |
| Birks alternatives | Dot/lollipop comparison | Makes model dependence visible without presenting the spread as a confidence interval |
| Pile-up criterion | Analytic curve plus stored scan points | Shows the Poisson model and the actual 5.06%/10.31% support points |
| B8 data/MC tension | Proportion intervals | Displays exact fractions and counting intervals on one comparable scale |
| Early-peak truth-MC rates | Proportion intervals | Avoids a mock waveform and answers the scientifically supported rate question |
| PCA compression | Cumulative curve at source-backed components | Shows compression behaviour without stale hand-entered explained-variance values |
| Sensitivity inputs | Log-scale dot plot | Handles three orders of magnitude without a misleading mixed-unit budget |

## Captions and evidence labels

Every manifest record contains:

- figure ID and question;
- caption;
- scientific status and evidence class;
- input path(s);
- generated source-table path and hash;
- PDF/SVG/PNG paths and hashes;
- exact width and height;
- file-level QA results.

Captions must distinguish at least these evidence boundaries where applicable:

- real detector data versus Monte Carlo;
- truth-level versus reconstructed quantities;
- validation versus method closure;
- confidence interval versus heuristic envelope or model spread;
- accepted result versus gated, blocked, tension or superseded history.

## Commands

```bash
make plots
make plots-check
make plots-docs
pytest -q tests/test_paper_grade_plots.py
```

The canonical implementation is `src/ccb_plotting/`. Legacy public entry points are wrappers around the same generator; parallel styling stacks are prohibited.
