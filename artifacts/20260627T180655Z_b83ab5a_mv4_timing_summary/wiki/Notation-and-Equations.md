# Notation and equations

Notation registry status: `PASS`; final notation status: `DRAFT`.

| ID | Symbol | Equation | Meaning |
|---|---|---|---|
| EQ-PID-EFF | `\\epsilon(t)` | `$\\epsilon(t)=N_{\\mathrm{true\\,signal}}(s(x)\\ge t)/N_{\\mathrm{true\\,signal}}` | Signal efficiency at score threshold t. |
| EQ-PID-PURITY | `P(t)` | `$P(t)=N_{\\mathrm{true\\,signal}}(s(x)\\ge t)/N_{\\mathrm{selected}}(s(x)\\ge t)` | Purity among selected candidates at score threshold t. |
| EQ-R68 | `R_68` | `$R_{68}=\\frac{1}{2}(Q_{84}[r]-Q_{16}[r])` | Robust central 68% residual scale. |
| EQ-ERESID | `r` | `$r=(E_{\\mathrm{reco}}-E_{\\mathrm{truth}})/E_{\\mathrm{truth}}` | Relative reconstructed-energy residual. |
| EQ-STOP-SUPPORT | `N_{\\mathrm{Sample\\,I}}, N_{\\mathrm{Sample\\,II}}` | `$N_{\\mathrm{Sample\\,I}},\\;N_{\\mathrm{Sample\\,II}}` | Frozen support counts for stopping-depth samples. |

These equations are used for artifact-summary interpretation and do not replace the final thesis derivations or systematic uncertainty treatment.
