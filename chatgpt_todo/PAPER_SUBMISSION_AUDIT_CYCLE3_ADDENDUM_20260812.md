# Cycle-3 submission audit addendum — recursive documentation/timing review

**Date:** 2026-08-12  
**Parent:** `PAPER_SUBMISSION_AUDIT_CYCLE3_20260812.md`  
**Umbrella:** #1301

This addendum records defects discovered after recursively auditing current-facing WIKI/setup chapters and the timing implementation. These findings are part of the same publication gate.

## A. Current-facing documentation is not a safe evidence source

### A-P0-001 — WIKI overrides the canonical ledger with stale accepted claims

`WIKI.md` currently labels the selected-pulse inventory `VALIDATED · DATA_MEASUREMENT`, calls CL-001 the single VALIDATED data row, and `paper/figures.yaml` repeats that status. `docs/claim_ledger.csv` instead has CL-001 = `GATED`, `allowed_status_validated=NO`.

The WIKI also still calls the old B2-vs-B4 `n=33,966, r=+0.221` result DeltaE-E and states `Rmax 2.92 MHz` is data-derived/corroborates a canonical value, while the canonical ledger withholds Rmax.

**Action:** #1299 must make current-facing docs generated from the canonical ledger or fail CI when statuses disagree.

### A-P0-002 — academic Chapter 2 contains invented/unsourced beam and DAQ facts despite its warning banner

Examples in `docs/academic_chapters/02_experimental_setup.md` include:

- actual beam energy/energy spread and beam spot stated as hardware facts even though paper BOM currently has beam/target/layout only as `SIM_CONFIG` or `UNKNOWN_EXTERNAL`;
- specific beam currents (`2–5 nA`, `0.5–1 nA`) and an independent capacitive beam-current monitor without a source-bound run record;
- cyclotron RF microstructure around 50 ns and duty-factor interpretation asserted without run/hardware evidence;
- exact trigger latency, 15 ns hardware coincidence, pretrigger configuration and clean-baseline claim while the trigger hardware contract is `UNKNOWN_EXTERNAL`;
- custom PCB transimpedance gain/bandwidth, CAEN DT5533N bias module, bias equalisation and temperature behaviour without a construction/electronics record.

These must be `UNKNOWN_EXTERNAL` until primary collaboration evidence exists, not retained as plausible narrative.

### A-P0-003 — Chapter 2 reproduces an internally impossible V1742/100-MS/s/7000-ADC world

The chapter correctly inserts a warning that V1742 identity is BLOCKED, then immediately states false V1742 specifications: 100 MS/s determined by the DRS4 clock, 10 ns samples, 18-sample/180-ns readout, and a 7000-code ceiling interpreted with a 12-bit 0–4095 converter.

A 7000 code cannot be a native unsigned 12-bit V1742 code. Official CAEN specifications separate V1742 (12-bit DRS4, selectable 0.75–5 GS/s) from V1724 (14-bit, 100 MS/s). #1014/#1073 therefore remain decisive.

**Action:** after the BLOCKED banner, remove all board-specific numbers not source-bound to the actual CCB acquisition transform. Use only the observed product schema (8x16 words, nominal analysis spacing) and mark hardware conversion unknown.

### A-P0-004 — Chapter 2 kinematics contains arithmetic/relativistic errors

For a 190 MeV proton:

- gamma = 1 + 190/938.272 ≈ 1.2025;
- beta ≈ 0.5554, not 0.565;
- momentum ≈ 626.6 MeV/c, not 602.5 MeV/c.

The chapter's invariant-mass expression for p+d uses the projectile kinetic energy where the total projectile energy is required. For a deuteron target at rest, `s = mp^2 + md^2 + 2 md E_p,total`; using T alone is wrong.

All downstream range/TOF/scattering calculations depending on these values require recomputation from a verified model, not hand algebra copied into publication prose.

### A-P0-005 — NIST PSTAR is incorrectly cited for a deuteron range

NIST PSTAR provides stopping/range tables for **protons**; ASTAR is for helium ions. It does not supply deuteron CSDA ranges. Chapter 2 states a deuteron range “from NIST PSTAR,” which is invalid sourcing.

**Action:** source deuteron stopping/range from an appropriate validated transport calculation/dataset (e.g. Geant4/ICRU/experimental data) with model uncertainty; do not reuse a proton PSTAR curve by particle-name relabelling.

### A-P0-006 — Chapter 2 claims a material-budget root cause while the project says causal attribution is blocked

The chapter states missing upstream material is the **root cause** of the MV3/B8 mismatch and presents precise but unsourced material layers (Kapton window, metres of air, Al/G10, support frames, Mylar, optical grease) with “included/missing” statuses.

This conflicts with #844/#956 scientific policy: material-budget attribution requires source-bound geometry and controlled nuisance scans. The compact Geant4 source review explicitly says several real supports/wrapping/electronics components are not survey-grade known.

The table also contains a unit error: 3000 mm of air is listed as `362 g/cm^2`; at ordinary air density the intended value is of order `0.36 g/cm^2`, consistent with the table's own radiation-length fraction. The claimed `8–10 g/cm^2` missing total is not supported by the listed component areal densities.

**Action:** remove this table from current-facing evidence until #1296/#844 produce a source-bound material BOM; retain historical hypotheses only as such.

### A-P0-007 — physical B-stack narrative is more definite than the mapping evidence

Chapter 2 states particular uninstrumented/passive stave identities and gives a physical reason why only B2/B4/B6/B8 are read out, despite the geometry/readout contract still blocking the exact deployed mapping. It even refers to “odd-numbered staves” while listing B0/B10/B12/B14, which are even labels.

**Action:** separate detector labels, electronics channels, Geant4 copy numbers and physical passive layers. Do not infer a mechanical layer inventory from naming parity.

### A-P1-008 — chapter contains unsupported optical/scintillation microphysics as installed-detector facts

The chapter retains detailed BC-408 fast/slow/ultraslow fractions, ~10,000 photons/MeV, attenuation/timing/systematic numbers, Y-11 ±0.5 m manufacturing/radiation-damage uncertainty and SiPM temperature drift as though they define the CCB stave. The installed material is only source-bound as extruded polystyrene, not BC-408, and #1088/A07/A08 explicitly block absolute response.

Generic literature values may be cited as examples, but must not enter CCB uncertainty budgets or performance calculations without a source-bound material/operating-point contract.

### A-P1-009 — “well-characterised” / “complete truth-level description” language is scientifically incompatible with the listed blockers

The chapter summary calls the setup well-characterised and the Geant4 model a complete truth-level description while hardware trigger, DAQ identity, material budget, geometry mapping and optical response are explicitly unresolved. Replace with bounded language.

### A-P1-010 — `docs/01_setup_and_detector.md` is also stale and internally conflicts with Chapter 2

It states most runs were at 20 nA (runs 46/47 at 2 nA), while Chapter 2 gives different current ranges. It still declares 18 samples/pulse and a 180-ns record despite #993's distinct 8x16 authorising schema. It quotes sample-level energy scales from an analytic range model and refers to NIST PSTAR in a way that needs particle-specific validation.

No paper author should use this file as an evidence source until #1299 reconciles it.

## B. Timing implementation findings

### B-P1-001 — current TOF geometry proxy conflicts with the detector-map spacing used elsewhere

`real_data_cfd_timing.py` defaults `SPACING_CM=2.0` and constructs B6/B8 TOF offsets of 4 and 6 cm, i.e. only 2 cm pair separation. S12b's analysed B readout positions are approximately 0, 4.0, 8.1, 12.1 cm, implying B6–B8 separation ~4 cm for that simulation/data-map contract.

The timing producer correctly labels its TOF model `UNVALIDATED_SPECIES_ENERGY_PRIOR`, so this does not invalidate the ~38 ns negative format-limited conclusion, but it **does block any future sub-ns A04 result**. TOF geometry must come from the same versioned detector mapping/hardware truth surface as the rest of the paper.

### B-P1-002 — fixed `TOF_PER_CM_NS=0.078` is not a mixed p/d event model

A fixed ns/cm conversion assumes a particle beta. Sample I/II contain different p/d/energy mixtures and the exact track path is angle-dependent. For precision timing, compute event- or species/energy-conditional TOF from a justified kinematic/track model or propagate the mixture uncertainty. Do not fit it away with per-stave offsets.

### B-P1-003 — default peak offsets use the evaluation population unless calibration runs are explicitly supplied

The code labels this `SAME_POPULATION_MEDIAN_DIAGNOSTIC` and `authorising=false`, which is good. Any publication timing run must require non-empty frozen calibration runs rather than relying on the default. Add a fail-closed A04 production mode if the paper ever promotes a precision timing value.

### B-P1-004 — nominal 10 ns must not be called native digitizer sampling until #1014 closes

The code correctly calls it a configurable analysis parameter. Paper/docs should follow that convention. Hardware-native timing, aperture jitter and possible transformation/decimation remain unverified.

## C. Publication action

- Keep `docs/academic_chapters/02_experimental_setup.md` and `docs/01_setup_and_detector.md` out of the citation/evidence chain until #1299's stale-claim map is complete.
- Add automated scans for prohibited stale claims: V1742@100MS/s, 7000 as hardware saturation, B2-vs-B4 as DeltaE-E, accepted 2.92/3.05 MHz Rmax, CL-001 VALIDATED, 18 samples as the authorising raw schema, PSTAR deuteron range.
- Any setup number moved into the paper must originate in `paper/hardware_bom.csv` with a primary evidence path/status.
- Any timing geometry/TOF correction must originate in the same versioned mapping/kinematics contract used for the MC/data figures.
