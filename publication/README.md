# CCB test-beam publication package

This is the **canonical submission workspace** for the CCB range-stave paper.

The older `docs/latex/` tree is a broader technical/academic report and is **not** the canonical source of this paper. The original 2026-08-12 Markdown draft is retained under `publication/source/` for provenance; active editing is chapterised under `publication/chapters/`.

The current-head section-by-section scientific audit and dependency-ordered finish queue are maintained in [`chatgpt_todo/PAPER_COMPLETION_AUDIT_20260814.md`](../chatgpt_todo/PAPER_COMPLETION_AUDIT_20260814.md).

## Layout

```text
publication/
├── main.tex                     # master TeX document
├── paper.pdf                    # compiled working PDF (generated/committed by CI)
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
│   └── validate_publication.py  # working-package structure/status validator
├── tables/
│   ├── final/                   # authorising publication tables
│   └── gated/                   # quarantined current tables
├── data/                        # data provenance/index only; no raw beam ROOT copied
├── source/                      # previous working manuscript/audit provenance
├── build.sh                     # local build entry point
└── Makefile
```

## Scientific status

**NOT SUBMISSION READY.** The Cycle-3 audit invalidated promotion of the current #956 DeltaE-E bundle and #1297/A09 energy-reconstruction headline and classified the July optical grid as a superseded model diagnostic. The TeX build therefore uses publication-hold blocks and the `figures/gated/` namespace rather than presenting those artifacts as final.

The 2026-08-14 current-head audit additionally confirms that `figures/final/`, `figures/source_data/` and `tables/final/` contain no non-README authorising scientific artifacts. The deterministic direct-CDF source-sampler defect tracked by #1178 is repaired/closed, but the historical paper MC remains gated by legacy event-measure, source-uncertainty and exact-production-provenance requirements.

The current source of truth for claim status remains `docs/claim_ledger.csv` until #1304 replaces the parallel status surfaces with one fail-closed publication mechanism. Current-facing WIKI text must not override a gated or blocked ledger row.

## Build

```bash
cd publication
./build.sh
```

or

```bash
make -C publication
```

The build writes `publication/paper.pdf`. Intermediate LaTeX files remain under `publication/build/` and are ignored. On the publication working branch, the `Publication PDF` GitHub Actions workflow rebuilds the PDF and commits `paper.pdf` plus `BUILD_RECEIPT.json` back to the branch when configured to do so.

`publication/scripts/validate_publication.py` is intentionally a **working-package structure/hold-state validator**. A green invocation or a green PDF build does not establish scientific submission readiness. Before submission, the stronger Chapter-12 contract must be enforced: final figures/tables and source data present, result/input hashes bound, claim status authorised, units/estimands explicit, uncertainty and MC event measure recorded, and the exact reviewed source head recorded in the build receipt.

## Editing rule

A result update is not complete until this package is synchronized:

`result/manifest/source table -> claim ledger -> publication figures/tables -> chapter TeX -> paper.pdf -> adversarial review`.

A script returning `PASS`, a PDF compiling, or an issue closing is not by itself physics closure.
