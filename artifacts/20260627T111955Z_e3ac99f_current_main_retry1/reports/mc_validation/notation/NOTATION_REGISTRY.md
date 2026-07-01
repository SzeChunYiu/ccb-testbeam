# MC validation notation and equation registry

- **Status:** `PASS`
- **Final notation status:** `DRAFT`
- **Record count:** `5`

| ID | Symbol | Equation | Meaning | Scope |
|---|---|---|---|---|
| EQ-PID-EFF | `\\epsilon(t)` | `$\\epsilon(t)=N_{\\mathrm{true\\,signal}}(s(x)\\ge t)/N_{\\mathrm{true\\,signal}}$ | Signal efficiency at score threshold t. | MV1 artifact-summary interpretation |
| EQ-PID-PURITY | `P(t)` | `$P(t)=N_{\\mathrm{true\\,signal}}(s(x)\\ge t)/N_{\\mathrm{selected}}(s(x)\\ge t)$ | Purity among selected candidates at score threshold t. | MV1 artifact-summary interpretation |
| EQ-R68 | `R_68` | `$R_{68}=\\frac{1}{2}(Q_{84}[r]-Q_{16}[r])$ | Robust central 68% residual scale. | MV2 artifact-summary interpretation |
| EQ-ERESID | `r` | `$r=(E_{\\mathrm{reco}}-E_{\\mathrm{truth}})/E_{\\mathrm{truth}}$ | Relative reconstructed-energy residual. | MV2 artifact-summary interpretation |
| EQ-STOP-SUPPORT | `N_{\\mathrm{Sample\\,I}}, N_{\\mathrm{Sample\\,II}}` | `$N_{\\mathrm{Sample\\,I}},\\;N_{\\mathrm{Sample\\,II}}$ | Frozen support counts for stopping-depth samples. | MV3 artifact-summary interpretation |
