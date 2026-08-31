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
- adds Appendix C with additional gated, simulation-diagnostic and illustrative figures that are not already part of the main chapter flow;
- does **not** alter claim status, evidence boundaries, manifests or the canonical submission build.

The main chapters remain the source of numerical context. Inclusion in `rough-paper.pdf` is not scientific promotion and must not be used as a citation or submission decision.
