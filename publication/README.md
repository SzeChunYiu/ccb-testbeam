# CCB test-beam publication package

This is the **canonical submission workspace** for the CCB range-stave paper.

The older `docs/latex/` tree is a broader technical/academic report and is **not** the canonical source of this paper. The original 2026-08-12 Markdown draft is retained under `publication/source/` for provenance; active editing is chapterised under `publication/chapters/`.

## Layout

```text
publication/
├── main.tex                     # master TeX document
├── paper.pdf                    # compiled working PDF
├── chapters/                    # one TeX file per paper section/chapter
├── references/                  # references section
├── figures/
│   ├── final/                   # authorising figures only
│   ├── gated/                   # quarantined/non-authorising current figures
│   ├── model_diagnostics/       # explicitly simulation/method diagnostics
│   ├── illustrative/            # schematics carrying no measured claim
│   └── source_data/             # figure source-table index/links
├── scripts/
│   ├── gated/                   # current producers invalidated by publication audit
│   ├── utilities/               # plot/build utilities
│   └── validate_publication.py  # structure/status validator
├── tables/
│   ├── final/                   # authorising publication tables
│   └── gated/                   # quarantined current tables
├── data/                        # data provenance/index only; no raw beam ROOT copied
├── source/                      # previous working manuscript/audit provenance
├── build.sh                     # deterministic-ish local build entry point
└── Makefile
```

## Scientific status

**NOT SUBMISSION READY.** The Cycle-3 audit invalidated promotion of the current #956 ΔE-E bundle and #1297/A09 energy-reconstruction headline and classified the July optical grid as a superseded model diagnostic. The TeX build therefore uses publication-hold blocks and the `figures/gated/` namespace rather than presenting those artifacts as final.

The current source of truth for claim status remains `docs/claim_ledger.csv` until #1304 replaces the parallel status surfaces with one fail-closed publication mechanism.

## Build

```bash
cd publication
./build.sh
```

or

```bash
make -C publication
```

The build writes `publication/paper.pdf`. Intermediate LaTeX files remain under `publication/build/` and are ignored.

## Editing rule

A result update is not complete until this package is synchronized:

`result/manifest/source table -> claim ledger -> publication figures/tables -> chapter TeX -> paper.pdf -> adversarial review`.
