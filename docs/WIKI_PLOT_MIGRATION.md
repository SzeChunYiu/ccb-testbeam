# Wiki plot migration: legacy gallery to evidence-bound publication figures

## Decision

The former wiki/gallery strategy accumulated many heterogeneous study images, including dark-grid plots, repeated dashboard panels, low-resolution PNGs, copied artefacts and illustrative/mock plots adjacent to quantitative claims. The public surface is replaced by **eleven canonical plot families** built through one controlled generator.

This is a migration of the publication surface, not deletion of historical evidence. Old study artefacts remain available for audit in their original report directories. They are no longer treated as the visual definition of a current claim.

## Canonical public set

| ID | Figure | Evidence boundary | Replaces or prevents |
|---|---|---|---|
| FIG-WIKI-001 | Selected-pulse inventory | Exact fixed-input S00 count | Repeated count tables and decorative selection diagrams |
| FIG-WIKI-002 | Claim-status overview | Canonical ledger governance | Dashboards that visually imply all rows are equally accepted |
| FIG-WIKI-003 | Timing estimator closure | MC method closure only | Beam-data timing claims based on toy-digitizer output |
| FIG-WIKI-004 | Grouped-fold PID stability | Simulation result | Connected fold curves and the stale 0.986 truth ceiling as the headline |
| FIG-WIKI-005 | ADC gain closure | Simulation result | Generic single-point registry plot for a two-species closure question |
| FIG-WIKI-006 | Birks comparison | Model dependence on MC | A single fitted number without showing proxy/default dependence |
| FIG-WIKI-007 | Digitizer-domain overlap | Simulation-domain scan | The incorrect “0% quality gate” label and canonical-Rmax overclaim |
| FIG-WIKI-008 | B8 stopping tension | Legacy data/MC diagnostic | Styling a failed closure as a validated stopping result |
| FIG-WIKI-009 | Early-peak truth-MC rates | Truth-labelled MC only | Random mock C12 waveform and transfer of MC identity to the data anomaly |
| FIG-WIKI-010 | PCA compression | Synthetic-waveform MC only | Stale hand-entered 89%/99.7% values |
| FIG-WIKI-011 | Sensitivity inputs | Dimensionless sensitivity inventory | A blanket “systematic budget” mixing incompatible units |

## Scientific corrections coupled to the migration

- The cluster-C pile-up point at 0.605 MHz corresponds to **10.31%** Poisson overlap for the stored 180 ns window; it is the nearest stored point to a 10% criterion, not a “0% quality gate”. It is not the canonical detector `Rmax`.
- The MV0 data/MC proxy is **92 ADC/MeV** with a rounded **28 ADC/MeV heuristic systematic envelope**. The envelope is not a confidence interval and the result remains gated.
- The early-peak result is reported as source-backed truth-MC rates. The separate beam-data anomaly is not identified as C12.
- The sensitivity plot includes only dimensionless cluster-D ADC-response elasticities. Gain envelopes, Birks spans and material column densities are not combined on one numerical axis.
- The wiki no longer authorizes a numerical canonical pile-up rate. `CL-010` remains blocked and `CL-012` remains superseded history.

## Generation and review flow

1. `scripts/generate_paper_grade_wiki_figures.py` reads tracked CSV/JSON/ledger evidence and fails on missing, duplicate or non-finite fields.
2. Each renderer produces one Matplotlib figure and one exact plotted-data table.
3. `src/ccb_plotting/export.py` audits the live figure object and exports atomic PDF/SVG/600-dpi PNG files.
4. `scripts/check_plot_quality.py` independently checks dimensions, editable SVG text, source tables and hashes.
5. `scripts/update_wiki_plot_docs.py` generates the repository gallery, the controlled `WIKI.md` section, a machine-readable plot manifest and staged pages for the separate GitHub Wiki repository.
6. CI regenerates all outputs and fails if the committed artefacts differ.

## Scope boundary

This migration improves communication and prevents unsupported visual claims. It does **not** close missing detector calibration, raw-data timing, stopping-geometry, data/MC transfer or systematic-propagation work. Figure status is inherited from the evidence; publication styling never changes it.
