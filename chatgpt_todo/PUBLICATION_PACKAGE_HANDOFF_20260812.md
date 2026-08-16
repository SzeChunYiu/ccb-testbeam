# Canonical publication-package handoff — 2026-08-12

The CCB test-beam paper now has one canonical submission workspace:

- master TeX: `publication/main.tex`
- chapterized TeX: `publication/chapters/`
- generated working PDF: `publication/paper.pdf`
- references: `publication/references/`
- figures separated by scientific role: `publication/figures/final/`, `gated/`, `model_diagnostics/`, `illustrative/`, `source_data/`
- analysis/plotting script index: `publication/scripts/`, with invalidated current producers under `scripts/gated/`
- paper tables: `publication/tables/final/` and `publication/tables/gated/`, with live links to the canonical hardware BOM and claim ledger
- data/provenance notes: `publication/data/`
- previous Markdown manuscript retained only for provenance under `publication/source/`
- build: `publication/build.sh` / `make -C publication`
- structural gate: `publication/scripts/validate_publication.py`
- machine build receipt: `publication/BUILD_RECEIPT.json`

`docs/latex/` remains the older broader technical/academic report and must not be treated as the canonical source for this paper.

## Scientific status

The package is deliberately fail-closed: `publication/STATUS.md` is `NOT_SUBMISSION_READY`. Figures invalidated by the Cycle-3 audit (#956 DeltaE-E and #1297/#1302/#1303 energy/optical results) remain in `publication/figures/gated/` for forensic review. The TeX `GatedFigure` path renders a publication-hold placeholder instead of the invalidated image.

A successful TeX/PDF build is a typography/reproducibility check, not scientific authorisation.

## Mandatory synchronization workflow

Every publication-facing analysis atom must complete the chain:

`physics/provenance contract -> result + manifest + source table -> docs/claim_ledger.csv -> publication figure/table -> affected chapter TeX -> publication/paper.pdf -> adversarial review -> issue close`

Negative or blocked results must be propagated into the paper rather than leaving stale optimistic wording or figures.

PR coordination: #1312. Submission gates: #1301/#1305. Publication-governance gate: #1304.
