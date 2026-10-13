# Publication figure physics + rendering audit — 2026-08-17

Scope: current GitHub-canonical publication mirrored to Overleaf project `6a82ba2104642dd4fd0f62b6`.

Principle: a publication figure is a scientific measurement/model visualization, not a provenance dashboard. Evidence status, issue IDs, SHA bindings, caveats and historical correction details remain in source tables, `result.json`, the claim ledger and manuscript captions unless they are needed to understand the plotted quantity itself.

## Non-negotiable figure rules

1. Geometry drawings use one explicit coordinate unit and convert all BOM quantities before plotting.
2. Any figure advertised as to-scale must preserve physical aspect ratios within each view. Schematic elements must not masquerade as measured dimensions.
3. No issue IDs, `GATED`, `MC_MODEL_DEPENDENT`, claim IDs, SHA strings, audit statuses or long provenance paragraphs inside the plotting canvas.
4. Do not use boxed text annotations for values already encoded by axes/legends/source tables.
5. Plot labels state physical observable + unit. Captions carry interpretation/evidence boundaries.
6. Conditional means are never stacked unless the plotted terms are mathematically additive under a common denominator.
7. DATA and MC must not share visual semantics that imply calibration/equality when one axis is ADC amplitude and the other is MeV truth.
8. Primary figures show current science. Superseded historical values belong in provenance/appendix diagnostics, not overlaid on the primary result unless the comparison itself is the scientific question.
9. Uncertainty shown on a figure must be real. Never draw zero-sized error bars as placeholders.
10. Dense event clouds should use transparency/density representation appropriate to occupancy; legends must remain readable at journal column width.

## P0 findings fixed on `fix/publication-figure-physics-style`

### #1317 stave geometry: mm/cm rendering bug

Producer: `scripts/issue_1317_setup_figures.py`

Confirmed defect: stave coordinates are in cm, but `fibre_hole_diameter=2.0 mm` and `WLS_fibre_outer_diameter=1.8 mm` were passed directly as numeric radii/diameters in the cm coordinate system. The cross-section therefore drew the hole/fibre about 10x too large in diameter.

Fix:
- unit-aware conversion to cm before any geometry is drawn;
- fail-closed physical hierarchy `fibre < hole < thickness < width < length`;
- transverse cross-section uses 5.18 cm x 2.0 cm body, 0.20 cm hole diameter, 0.18 cm fibre diameter, 2.0 cm hole-centre separation;
- longitudinal view preserves 50 cm : 5.18 cm aspect ratio;
- provenance status tags removed from visible artwork and retained in `annotations.json/source_table.csv`;
- channel-parity alternative rendered compactly rather than repeated text under every layer;
- trigger hardware not geometrically invented when its location is not source-bound.

Regression tests: `tests/test_issue_1317_setup_figures.py`.

### #1319 MC depth profile: non-additive stacked conditional means

Producer: `scripts/issue_1319_mc_depth_profile.py`

Confirmed defect: proton/deuteron/other *conditional mean* layer profiles were stacked as bars. Conditional means have different denominators and their sum is not the all-event mean; stacked height therefore has no well-defined physical interpretation.

Fix:
- separate species-conditional curves;
- independently computed all-event mean shown explicitly;
- sparse parity hypotheses retained without treating either as canonical;
- Sample-I/II proxy profiles retain bootstrap bands;
- long issue/provenance/ESS footer removed from plot and retained in `result.json`/caption;
- rendering contract recorded in schema v2.

Regression tests: `tests/test_issue_1319_mc_depth_profile.py`.

### #1303 optical figures: repeated waterfall/textbox clutter

Producer: `scripts/single_stave/paper_1303_optical_stage_accounting.py`

Confirmed presentation defect: five mini-waterfall panels each printed values above every bar plus an efficiency textbox, while issue/status text occupied the title. The current-model PE/MeV plot also overlaid superseded July points although historical correction is not the primary scientific question.

Fix:
- stage accounting becomes one response-chain survival plot, each operating point normalized to its own scintillation-photon mean;
- exact absolute counts/efficiencies remain in the source table;
- no per-panel textboxes;
- current PE/MeV plot contains current model only; July values stay in JSON/table provenance;
- calibration fit metrics remain in returned data/caption rather than legend/title;
- no issue/status prose inside plot.

Regression tests: `tests/test_paper_1303_optical_figure_rendering.py`.

## Remaining P0/P1 graphics work

### P0 — held-out energy reconstruction plot has fake zero error bars

Producer: `scripts/single_stave/paper_a09_heldout_edep_reconstruction.py`, `make_figure()`.

Current code draws `yerr=[[0],[0]]` for median bias and no uncertainty on sigma68 despite the producer calculating bootstrap intervals. This is scientifically misleading: the plotted point appears exact while uncertainty exists in `summary['bootstrap']`.

Required fix:
- propagate per-heldout-point bootstrap intervals into the figure source table, or explicitly state that only pooled uncertainty is available and omit error bars rather than draw zeros;
- preferred: compute bootstrap CI for bias and sigma68 separately for each heldout run/energy point using the frozen resampling contract;
- plot genuine asymmetric intervals;
- remove `MODEL-DEPENDENT OPTICAL MC` from suptitle; caption carries that evidence class;
- keep E_vis primary and E_raw negative control visually unmistakable.

### P1 — #618 figure family is redundant and too large for main narrative

Producer: `scripts/single_stave/paper_618_species_penetration.py`.

Current main-paper surface can render six MC figures:
- full dE-E I/II;
- sparse 4-layer dE-E I/II;
- penetration I/II.

Each dE-E figure repeats proton-only, deuteron-only, p+d and all-particle panels. This is useful as an analysis report but excessive for a paper and visually fragments the argument.

Required redesign:
- one compact full-vs-sparse dE-E comparison with Sample I/II on consistent axes;
- one species-separated panel or contours rather than four repeated scatter panels per sample;
- one penetration comparison with p/d and Sample I/II in the minimum number of panels;
- retain full report figures as supplementary diagnostics;
- ensure sparse readout explanation reflects alternating physical planes and does not imply a source-unbound parity is hardware truth.

### P1 — DATA depth profile

Producer: `scripts/real_data/analyze_depth_profile_8x16.py`.

Review publication rendering after regeneration:
- one primary physical message per panel;
- report absolute event population outside normalized-share plot/caption rather than inside boxes;
- threshold dependence should be a compact sensitivity panel, not multiple repeated main figures;
- preserve measured-polarity-v2 and duplicate-channel nuisance envelope.

### P1 — timing residual

Producer: `scripts/issue_1320_timing_residual.py`.

Primary figure should show:
- residual distribution and robust central interval;
- median offset visibly but without turning the plot into a calibration claim;
- optional compact method/fraction stability panel;
- no text box listing every cut, issue, provenance token or interpretation caveat.

Caption must state pair residual, not intrinsic stave resolution.

### P2 — global plot style

Create/adopt a small common publication plotting helper after the physics-specific fixes are merged:
- consistent figure widths/font sizes;
- top/right spines off for ordinary Cartesian plots;
- subtle grid only where useful;
- consistent proton/deuteron and Sample-I/II visual identities;
- no hard-coded scientific values in the style layer;
- SVG/PDF vector output for line/scatter/geometry graphics;
- rasterization only for dense point clouds inside vector PDF.

Do not let a shared style helper override scientifically meaningful axis scaling, bins, normalization or uncertainty representation.

## Regeneration requirement

Script changes alone do not update the paper binaries. Regenerate affected artifact bundles from their existing immutable inputs, refresh figure/source hashes in the publication manifest, rebuild `paper.pdf`, and sync GitHub -> Overleaf. Numerical tables/claims must remain unchanged unless a producer-science correction explicitly requires otherwise.
