# Internal rough paper build

The collaboration-review build is intentionally separate from the canonical publication PDF.

```bash
cd publication
make rough
```

This writes `publication/rough-paper.pdf`. The canonical `make pdf` / `publication/paper.pdf` behavior is unchanged.

## Purpose

The rough build exists for internal paper-layout and content review when collaborators need to see the expected visual footprint before all analysis gates are closed. It therefore:

- renders an existing `\GatedFigure` artifact when the file is present;
- labels every such rendering `PRELIMINARY / GATED` immediately beneath the image;
- omits genuinely unavailable artifacts instead of inserting an empty figure box;
- adds Appendix C with a mixed-status numbers-at-a-glance table plus additional gated, simulation-diagnostic, truth-MC, sensitivity and illustrative figures that are not already part of the main chapter flow;
- includes the currently available timing/PID/ADC/Birks/pile-up/anomaly/PCA/stopping/sensitivity diagnostics so the paper meeting sees the likely main-text + supplementary footprint rather than only promoted figures;
- does **not** alter claim status, evidence boundaries, manifests or the canonical submission build.

The main chapters and machine-readable source tables remain the authority for numerical context. Inclusion in `rough-paper.pdf` is not scientific promotion and must not be used as a citation or submission decision.

## Pull-request artifact

PRs that touch this rough-paper surface run `.github/workflows/publication_rough_pdf.yml`. The workflow is read-only: it runs the focused rough/A09 contract tests, installs TeX, compiles the rough paper, and uploads the result as the **`ccb-rough-paper`** Actions artifact. It does not commit a generated PDF back to the branch.

For the current paper-inventory work, use PR **#1621** and its `Publication Rough PDF` check to obtain the compiled meeting PDF.
