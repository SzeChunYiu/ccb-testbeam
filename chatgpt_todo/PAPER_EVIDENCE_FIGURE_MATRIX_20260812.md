# CCB test-beam paper evidence and figure matrix

**Date:** 2026-08-12  
**Branch base:** `main@4376a3f88c8e059a5c1a92c020856c98d31f538b`  
**Purpose:** make every manuscript claim traceable to a measured result, source-bound configuration, model-dependent MC result, external primary source, or explicit blocker.

## Status vocabulary

- `DATA_MEASURED`: calculated from real beam data with a declared observable and population. This does not by itself imply detector-level calibration.
- `SOURCE_BOUND_CONFIG`: directly present in source/configuration or in a supervisor hardware clarification, but not necessarily survey/metrology-grade.
- `MC_TRUTH`: Geant4 truth observable before response modelling.
- `MC_MODEL_DEPENDENT`: reproducible numerical simulation output whose physical parameters are not fully authorising.
- `GATED`: useful result exists but claim promotion is blocked by a named provenance/calibration/systematic gate.
- `BLOCKED`: required evidence is absent or current algorithm does not identify the intended measurand.
- `EXTERNAL_PRIMARY`: primary publication, official toolkit documentation or manufacturer technical data.

## Section-by-section matrix

| ID | Manuscript claim / object | Status | Evidence | Figure/table source | Remaining action |
|---|---|---|---|---|---|
| P-001 | HIBEAM/NNBAR searches neutron conversion processes and needs an annihilation detector | EXTERNAL_PRIMARY | Yiu et al. 2022, DOI `10.3390/sym14010076` | intro only | none |
| P-002 | Low-energy charged-particle calorimetry motivates a range stack of plastic scintillator layers | EXTERNAL_PRIMARY | Dunne et al. 2022, DOI `10.1088/1742-6596/2374/1/012014` | intro only | none |
| P-003 | CCB model beam energy is 190 MeV | SOURCE_BOUND_CONFIG | `reports/1781181864.166832.35d806b2__s21_geant4_source_review/REPORT.md`, reviewed macro `/ElGen/E 190. MeV` | Fig. 1 caption | final run-log citation if available |
| P-004 | CCB target model is 2.3 mm CD2 | SOURCE_BOUND_CONFIG | same S21 source review | Fig. 1 | verify against campaign logbook/hardware record before calling it measured thickness |
| P-005 | compact CCB geometry uses nominal 109 distance parameter, -38° B arm, +71.5° A arm, 8 and 4 bars | SOURCE_BOUND_CONFIG | `geant4/configs/krakow.geoconf`; S21 source review | Fig. 1 | do not call survey-grade without builder/survey source |
| P-006 | B stave is extruded polystyrene, 50 × 5.18 × 2.0 cm | SOURCE_BOUND_CONFIG + supervisor clarification | issue #796 comment; `docs/stave-geometry.md`; `paper/manuscript_outline.md` | Fig. 2 | reconcile stale BC-408 / ~100 cm academic chapter wording in docs |
| P-007 | two 2.0 mm holes, two 1.8 mm Y-11 fibres separated by 2 cm | SOURCE_BOUND_CONFIG + supervisor clarification | issue #796; `docs/stave-geometry.md` | Fig. 2 | verify installed fibre grade/end finish if publication needs construction provenance |
| P-008 | only one of four possible fibre/end measurements was read out in beam test | supervisor hardware clarification | issue #796 and #797 | Fig. 2 caption | none unless hardware channel map contradicts |
| P-009 | source-bound sensor model is Hamamatsu S13360-3050CS | SOURCE_BOUND_CONFIG | `paper/manuscript_outline.md`, `docs/stave-geometry.md`, optical sim | stave table | operating point remains separate |
| P-010 | S13360-3050CS has 3×3 mm² area, 50 µm pitch, 3600 pixels | EXTERNAL_PRIMARY | Hamamatsu official product page | stave table | none |
| P-011 | Y-11(200) representative emission 476 nm, absorption 430 nm, attenuation >3.5 m | EXTERNAL_PRIMARY | Kuraray official technical data | stave table | do not turn representative value into installed-fibre calibration |
| P-012 | Geant4 optical processes include scintillation, absorption, boundary transport and WLS | EXTERNAL_PRIMARY | Geant4 Physics Reference Manual / Book for Application Developers | simulation schematic | none |
| P-013 | current full CCB geometry is compact and not a full material model | SOURCE_BOUND_CONFIG / audit | S21 source review | methods / limitation | material-budget closure required before quantitative range efficiency |
| P-014 | historical CCB generator used weighted angular sampling; weights must propagate into estimands | GATED / audit | S21 source review; later weighted-estimand fixes including #958/#959/#960 family | MC captions | final paper must bind exact production MC revision and effective sample size |
| P-015 | Sample-I calibration runs are 31-37,39-42 and analysis runs 44-57 | SOURCE_BOUND_CONFIG | `configs/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.yaml` | Table 1 | cross-check run log / trigger hardware record |
| P-016 | Sample-II calibration run is 64; analysis runs 58-63,65 | SOURCE_BOUND_CONFIG | same config | Table 1 | cross-check run log / trigger hardware record |
| P-017 | MC Sample I/II uses a first-layer charged-hit trigger proxy, not validated hardware response | GATED | header gate in `reports/SAMPLE_I_II_DATA_MC_REPORT.md`; trigger hardware response contract | methods | keep `MC_TRIGGER_PROXY` label in all MC trigger figures |
| P-018 | canonical selected-pulse table has 640,737 B pulses | GATED | `docs/claim_ledger.csv`, CL-001 | data-flow table | waveform/raw-to-sorted lineage must remain visible in caption/status |
| P-019 | Sample-II analysis has 125,096 selected pulses: B2 88,213; B4 21,229; B6 11,148; B8 4,506 | SOURCE_BOUND_CONFIG / selected-population count | s03e config; sample report | depth table | regenerate dynamically for final figure |
| P-020 | Sample-I B2 mean 6090 ADC and saturation fraction 0.417; Sample-II B2 mean 3663 ADC and saturation fraction 0.061 | DATA_MEASURED in selected population, historical result file | `reports/SAMPLE_I_II_DATA_MC_REPORT.md` | Fig. 3 / table | final figure must read source result file; verify saturation definition/polarity gate on current code |
| P-021 | coincidence-like MC is deuteron enriched at first B layer and B-only sample penetrates more | MC_TRUTH with trigger-proxy caveat | `reports/SAMPLE_I_II_DATA_MC_REPORT.md` | Fig. 4 | bind exact event weighting and current layer map |
| P-022 | raw data product located by data-side study is 8 channels × 16 samples | DATA provenance observation | `reports/studies/data_side/REPORT.md`; issue #993 audit | timing methods | keep separate from 18-sample historical product |
| P-023 | historical canonical timing product declares 8 × 18 samples at 10 ns | SOURCE_BOUND_CONFIG, provenance unresolved | `configs/s00_reproduction.yaml`; s03e config; issue #993 | timing methods | authorising 16↔18 relationship still not established from cited evidence |
| P-024 | direct raw B4-B6 residual sigma68 ≈38.0 ns for n=5207 is format/sampling limited | DATA_MEASURED but NON-PERFORMANCE | `reports/studies/data_side/REPORT.md` | Fig. 5 | final caption must say `NOT DETECTOR RESOLUTION` |
| P-025 | historical ~0.54 ns combined and ~0.68-0.75 ns single-stave values are not authorising beam-data resolutions | GATED/BLOCKED | `docs/claim_ledger.csv` CL-002 to CL-006; current issue #1059; recent timing commits explicitly say no detector claim promoted | do not plot as detector result | possible appendix as historical/toy diagnostics only |
| P-026 | global-maximum CFD can switch timed pulse component in multi-component waveform as fraction changes | confirmed algorithmic flaw | issue #1059 deterministic counterexample | Fig. 6 diagnostic | production timing must define target component and stable class |
| P-027 | B2-B4 real-data amplitude sample has 33,966 events and corr +0.221 | DATA_MEASURED | `reports/studies/data_side/REPORT.md`, `VIS-DE-001-DATA_deltaE_E_real.png` | Fig. 7 | regenerate exact selection flow, uncertainty/bootstrap by run |
| P-028 | corresponding current MC truth correlation is -0.533 | MC_TRUTH, not same units | data-side report / MC comparison | Fig. 8 | apply data-matched segmentation and validated response before claiming quantitative closure |
| P-029 | B2 median data 3385 ADC; MC selected truth median ~101.0 MeV | DATA_MEASURED + MC_TRUTH on different scales | data-side report | Fig. 7/8 captions | never compare values as same energy scale |
| P-030 | sparse four-channel longitudinal readout limits classical ΔE-E / Bragg-curve granularity | interpretation supported by geometry and readout | P-005/P-008 plus calorimeter principle [2] | discussion | quantify information loss with 4-vs-8 layer MC ablation if possible |
| P-031 | old event-number-only joins corrupted a substantial fraction of ΔE-E associations; composite key is required | historical code/results flaw | issue #797 closing comment and composite-key rerun context | methods | final producer must assert `(file_id, run, event)` uniqueness |
| P-032 | optical campaign produced approximately 8.7-11.0 PE/MeV at selected p/d points | MC_MODEL_DEPENDENT | issue #796 closing comment; calibration artifacts | Fig. 9 | retain only with non-authorising optical-model label |
| P-033 | reported optical-campaign relative widths span roughly 8.9-20.8% for selected points | MC_MODEL_DEPENDENT | issue #796 closing comment / calibration report | Fig. 9 / Table 2 | define denominator and event-level resolution estimator before paper claim |
| P-034 | Geant4 default WLS one-secondary behaviour is not a measured Y-11 quantum yield | BLOCKED for absolute yield | `docs/adr/ADR-WLS-FLUORESCENCE-YIELD-UNVERIFIED.md` | Fig. 9 caption | source-bound/measured WLS fluorescence yield or explicit nuisance envelope |
| P-035 | absolute light-yield claims are currently disabled by gate | BLOCKED | ADR above; `scripts/sipm_waveC_gates.py` | text | do not publish total photon→PE efficiency yet |
| P-036 | SiPM recovery law, charge-domain normalisation, coupling footprint and correlated noise are not fully CCB-calibrated | BLOCKED | `docs/adr/ADR-SIPM-PHYSICS-BLOCKED-WAVEA-LANE01.md` | methods/systematics | bench/source-bound operating-point data |
| P-037 | heuristic gain 92 ADC/MeV ±28 is not precision calibration | GATED | `docs/claim_ledger.csv` CL-013 | energy section | do not use to relabel axes in MeV |
| P-038 | historical 246 ADC/MeV is obsolete | superseded | paper outline / historical reports | none | remove from production plots and text |
| P-039 | single-stave energy reconstruction can be evaluated against Geant4 Edep with held-out MC | method ready, result pending | optical MC campaign and digitizer framework | Fig. 11 / Table 2 | PAPER-A09 |
| P-040 | full stack incident-energy reconstruction is not yet calibrated in data | BLOCKED | material-budget and per-channel response gaps | discussion | PAPER-A06 + A09 + response calibration |

## Required figures and present readiness

### Figure 1: CCB test-beam layout

**Readiness:** `YELLOW`.  
Use source-bound values from `geant4/configs/krakow.geoconf` and S21 source review. A final figure can be generated now, but the caption must state that it represents the simulation/configuration geometry, not a survey drawing. If a campaign photograph or authoritative mechanical drawing exists, replace or supplement it.

### Figure 2: Stave geometry and readout

**Readiness:** `GREEN` for geometry schematic.  
Reuse source-generated figures under `figures/geometry/`. Explicitly show both WLS fibres, all four possible fibre/end readout locations, and mark the single physical CCB readout channel.

### Figure 3: Data depth profile, Sample I vs II

**Readiness:** `YELLOW`.  
The result exists. Regenerate from the current canonical selected-pulse/result registry with current polarity/saturation gates. Plot normalized selected-pulse fractions and include counts.

### Figure 4: MC depth profile and truth composition

**Readiness:** `YELLOW`.  
Must bind exact weighted estimator, effective sample size, layer mapping and `MC_TRIGGER_PROXY` status.

### Figure 5: Timing residual from located raw product

**Readiness:** `GREEN` as a **negative/format-limited result**, not as detector resolution.  
Use the data-side timing artifact. The title/caption must say `8×16 raw product`, `10 ns nominal sampling`, and `NOT DETECTOR RESOLUTION`.

### Figure 6: Production timing and time-walk closure

**Readiness:** `RED`.  
Blocked by PAPER-A04 and issue #1059. Required panels: pre/post correction residual; residual mean/width vs amplitude; CFD/component-stability; run-held-out closure; pair/covariance inference.

### Figure 7: Real-data amplitude ΔE-E

**Readiness:** `YELLOW/GREEN`.  
Existing real-data plot is useful. Regenerate with current composite-key producer and explicit saturation mask/overlay. Axes stay in ADC amplitude.

### Figure 8: MC ΔE-E

**Readiness:** `YELLOW`.  
Truth plot can be shown now only as a separate MeV panel. A quantitative data/MC closure panel requires the data-matched four-layer response and material budget.

### Figure 9: Single-stave Edep → detected PE

**Readiness:** `YELLOW`.  
Use existing Geant4 points/full event output, but mark it `MODEL-DEPENDENT OPTICAL MC`. Do not call the slope measured light yield or detector efficiency.

### Figure 10: Optical stage efficiencies

**Readiness:** `RED`.  
Requires event counters for generated scintillation photons, WLS absorptions, WLS re-emissions, sensor incidents and primary avalanches, all with source-bound parameter status.

### Figure 11: Energy reconstruction resolution

**Readiness:** `RED`.  
Requires a preregistered held-out simulation analysis. This is one of the highest-value remaining tasks because the raw MC inputs already exist.

## Stale or unsafe text that must not re-enter the paper

1. **Stave identity conflict:** `docs/academic_chapters/02_experimental_setup.md` contains an older ~100×10×1 cm BC-408 description. The paper uses the issue #796 / `docs/stave-geometry.md` 50×5.18×2.0 cm extruded-polystyrene stave unless an authoritative hardware source overturns it.
2. **Timing:** do not quote 0.54 ns, 0.68 ns or 0.75 ns as measured detector resolutions under the current evidence state.
3. **Optical yield:** do not quote `~10 PE/MeV` as an absolute measured light yield or as a validated real-detector calibration. It is a model-dependent optical-MC output.
4. **Analytical 0.56% efficiency:** `docs/stave_sim/STAVE_SIM_ENERGY_MODEL.md` constructs a total efficiency from assumed WLS capture and PDE. The later WLS/SiPM gates supersede this as an authorising result. Do not publish 0.56% as detector efficiency.
5. **Energy gain:** do not use 246 ADC/MeV. The 92±28 ADC/MeV value is itself only a gated heuristic envelope, not a precision conversion.
6. **MC trigger:** do not say the hardware trigger is reproduced by Geant4. Current sample membership is `MC_TRIGGER_PROXY`.
7. **MC truth vs data units:** never place ADC amplitudes and Geant4 EDep on one common numerical energy axis without a validated response transform.
8. **Generator weights:** unweighted MC distributions are unsafe unless the exact production generator samples the desired distribution directly or the event weights are proven irrelevant to that estimand.
9. **Raw/canonical waveform equivalence:** do not assert that the 16-sample and 18-sample products differ only by two trailing samples without an authorising producer-lineage proof.

## Reference audit status

The seven external references in `PAPER_DRAFT_CCB_TESTBEAM_20260812.md` were checked against primary or official sources on 2026-08-12:

- Yiu et al. title/journal/year/DOI: official publisher page, `10.3390/sym14010076`.
- Dunne et al. title/authors and related journal DOI: arXiv record, related DOI `10.1088/1742-6596/2374/1/012014`.
- Barrow et al. title/authors and related journal DOI: arXiv record, related DOI `10.1051/epjconf/202125102062`.
- Geant4 2003 and 2016 citations: official Geant4 citation page.
- Kuraray Y-11 properties: official manufacturer technical page; values are explicitly representative, not guaranteed specifications.
- Hamamatsu S13360-3050CS geometry/pixel count: official manufacturer product page.

No unverified literature citation should be added to the manuscript merely to decorate a statement. New citations should enter this matrix with the claim they support.
