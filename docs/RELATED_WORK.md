# Related work & references — CCB test-beam analysis

> Prepared with `nature-academic-search` + `nature-citation`. Every citation used below is a
> **verified** entry in `docs/references.bib` (title/authors/year/venue confirmed by web search on
> 2026-07-05; DOIs included only where confident). Candidate references that could not be fully
> verified are held in the `TO-CHECK` block at the foot of `references.bib` and are **not** cited here.
> Nothing in this file is fabricated; where the literature is thinner than our claim needs, that gap is
> flagged in Section 9.

This analysis measures **same-particle (proton) timing resolution** and **pile-up behaviour** in the
HIBEAM High-Resolution Detector (HRD) plastic-scintillator range staves, using ~190 MeV protons on a
CD2 target at the Cyclotron Centre Bronowice (CCB, Krakow), with a GEANT4 truth simulation and a
traditional-vs-ML methodology. The related work falls into eight groups.

## 1. Physics motivation: HIBEAM-NNBAR and the neutron-antineutron search

The HRD is a subsystem developed in the context of the HIBEAM/NNBAR program at the European Spallation
Source, whose goal is a search for free neutron→antineutron oscillation (and n→sterile-n conversion)
with sensitivity up to three orders of magnitude beyond previous limits [`Addazi2021HIBEAM`]. The
instrument design and its detector suite are described in the HIBEAM instrument paper
[`HIBEAM2025Instrument`], and the detector-simulation framework used for the program (the lineage of
our GEANT4 truth setup) in [`NNBAR2021Framework`]. These anchor *why* a scintillator range telescope
with well-characterised timing and pile-up response matters.

## 2. High-Resolution Detector (HRD) / scintillator range telescopes

The HRD operates as a **range telescope**: charged particles leaving the target deposit energy across a
depth-ordered stack of plastic-scintillator staves, and the penetration profile encodes particle
species and energy. The range-telescope / ΔE–E-stack concept and its detector-simulation treatment are
covered by the HIBEAM references above [`HIBEAM2025Instrument`, `NNBAR2021Framework`]; the underlying
proton stopping-power/range scale we validate against is the NIST PSTAR tabulation [`NISTPSTAR`].
*(A dedicated HRD instrument paper and a standalone scintillator range-telescope method paper are
weak points — see Section 9 and TO-CHECK [TC3].)*

## 3. Plastic-scintillator + SiPM/WLS timing-resolution methods

Our headline observable — sub-nanosecond timing from plastic-scintillator staves — sits in the
established plastic-scintillator + SiPM timing literature. The J-PET work on the time resolution of
long plastic-scintillator strips with multi-SiPM readout [`Moskal2016JPET`] provides directly
comparable coincidence-resolving-time methodology (timestamp combination, time-walk handling, and
achievable ~0.2–0.4 ns resolution) against which our per-stave σ values can be benchmarked.
*(Additional plastic+SiPM/WLS timing references exist but are held in TO-CHECK [TC4] pending
verification.)*

## 4. Birks' law / light quenching for protons, deuterons and heavy recoils

Converting scintillation light to deposited energy for heavily-ionising particles requires the
ionisation-quenching correction of Birks' law, dS/dr = (A dE/dr)/(1 + kB dE/dr) [`Birks1951`,
`Birks1964`]. This is load-bearing twice in our analysis: (i) the proton/deuteron ΔE–E separation and
the resulting energy scale (~60–80 ADC/MeV) are quenching-dominated, and (ii) the MV6b study uses a
*physical* Birks treatment to rule out C12 recoils as the source of the 4.4% early-peak class (0/1656
quenched C12 records survive the A>1000 selection). Birks' law is the reference that makes both
arguments quantitative.

## 5. Constant-fraction discrimination and amplitude (time-walk) correction

The timing pickoff comparison contrasts template/CFD methods with an analytic amplitude-walk
correction. The constant-fraction technique for amplitude-independent timing originates with Gedcke and
McDonald [`Gedcke1967CFD`]; its digital/FPGA realisation and the resulting time-resolution studies are
given by Fallu-Labruyère et al. [`FalluLabruyere2007DCFD`]. Together these support both the CFD pickoff
we test and the amplitude-timewalk correction that wins our timing bake-off (σ68 ≈ 1.49–1.55 ns
inclusive; ~0.85–1.1 ns per-stave at high amplitude). *(An explicit leading-edge/ToT time-walk-
correction citation is optional — see TO-CHECK [TC2].)*

## 6. Pile-up and dead-time: paralyzable vs non-paralyzable models

The pile-up characterisation (R_max ≤ 3.05 MHz one-sided bound; censoring-aware ≈2.1 MHz) rests on the
standard counting-loss framework. The paralyzable (type II) and non-paralyzable (type I) dead-time
models, and the count-rate regime where they diverge, are the textbook treatment in Knoll [`Knoll2010`];
the current status, limitations and correction models are reviewed by Usman and Patil [`Usman2018Deadtime`].
These frame our R_max as a dead-time/censoring statement rather than an ad hoc rate cut.

## 7. p + d elastic scattering kinematics at ~100–200 MeV

The two-body kinematics that populate the HRD — protons and recoil deuterons from p+d elastic
scattering off the CD2 target at ~190 MeV — are constrained by the systematic intermediate-energy
p–d elastic cross-section and analyzing-power datasets of Ermisch et al. [`Ermisch2003PD`,
`Ermisch2005PD`] (measured at 108–190 MeV, exactly our regime) and Sekiguchi et al. [`Sekiguchi2017DP`]
(complete observable set at 190 MeV/nucleon). These support the expected proton/deuteron angular and
energy distributions and the Sample-I deuteron enrichment we confirm (truth ratio 1.519, S21; data
ratio 3.45, S23).

## 8. ML vs. traditional methods in particle-detector signal processing

The project's methodological spine is a traditional-vs-ML head-to-head on every task. The weak-
supervision paradigm we lean on for data-side labelling is CWoLa (classification without labels)
[`Metodiev2017CWoLa`]; the traditional baselines and ML comparators are random forests [`Breiman2001RF`]
and ridge regression [`Hoerl1970Ridge`]. The GEANT4 toolkit that produces the truth labels for the
supervised ceiling (p/d PID AUC 0.986) is cited as [`Agostinelli2003Geant4`, `Allison2006Geant4`,
`Allison2016Geant4`]. *(Broader ML-pile-up/signal-reconstruction references exist but are held in
TO-CHECK [TC1], [TC5] pending verification.)*

---

## 9. Which manuscript/WIKI claims most need external citation support

Ranked by how exposed the claim is to reviewer challenge (most exposed first). Buckets refer to the
sections above; keys are the verified `references.bib` entries that cover them.

| # | Claim (as stated in WIKI/PROJECT_REPORT/README) | Bucket | Cite | Status |
|---|---|---|---|---|
| 1 | "p/d PID MC-closed at AUC 0.986" — deuterons stop early, protons penetrate; ΔE–E species separation | 4, 7 | `Birks1951/1964`, `Ermisch2003PD`, `Sekiguchi2017DP` | covered |
| 2 | Gain "≈60–80 ADC/MeV, dominated by trigger/quenching modelling" | 4 | `Birks1951/1964`, `NISTPSTAR` | covered |
| 3 | "C12 ruled out (MV6b): 0/1656 quenched C12 records pass A>1000" | 4 | `Birks1951/1964` | covered |
| 4 | "Analytic timewalk wins timing (σ68 ~1.49–1.55 ns; per-stave ~0.85–1.1 ns)" | 5, 3 | `Gedcke1967CFD`, `FalluLabruyere2007DCFD`, `Moskal2016JPET` | covered |
| 5 | "Pile-up R_max revised down 4.2 → ≤3.05 MHz (one-sided bound)"; censoring-aware ≈2.1 MHz | 6 | `Knoll2010`, `Usman2018Deadtime` | covered |
| 6 | HRD is a "range telescope"; "Sci_bar hits fall with depth (layers 0→7)" | 2 | `HIBEAM2025Instrument`, `NNBAR2021Framework`, `NISTPSTAR` | **thin** — no dedicated HRD/range-telescope method paper verified (TC3) |
| 7 | "190 MeV proton beam strikes a CD2 target … two independent HRD range stacks at conjugate angles" (CCB facility) | 1, 7 | `Addazi2021HIBEAM`, `HIBEAM2025Instrument`, `Ermisch2003PD` | covered for physics; **CCB-facility citation still needed** (see gap) |
| 8 | HIBEAM/NNBAR motivation (n→n̄ search, ESS) | 1 | `Addazi2021HIBEAM`, `HIBEAM2025Instrument` | covered |
| 9 | "ML wins shape-closure tasks" (AE/PCA basis beats median template; weak-label proxies) | 8 | `Metodiev2017CWoLa`, `Breiman2001RF`, `Hoerl1970Ridge` | covered; broader ML-DSP support in TC1/TC5 |
| 10 | "Sample-I D-enrichment confirmed (S21 truth 1.519; S23 data 3.45)" | 7 | `Ermisch2003PD`, `Sekiguchi2017DP` | covered |
| 11 | GEANT4 truth-tree production, energy-scale validation | 8/sim | `Agostinelli2003Geant4`, `Allison2006Geant4`, `Allison2016Geant4` | covered |

**Biggest remaining citation gaps (act before submission):**
- **HRD / range-telescope method paper (claims 6, 7).** The strongest single missing reference is a
  dedicated HRD or scintillator-range-telescope instrument/method paper. Current coverage is only the
  general HIBEAM instrument/framework papers. Verify TC3 (arXiv:2109.03452) or locate the HRD design
  note before relying on this in the methods section.
- **CCB (Cyclotron Centre Bronowice) beam-facility reference.** The 190 MeV proton beam / CCB facility
  is asserted with no citation; a CCB/IFJ-PAN facility paper should be added (not yet verified — do a
  targeted search for the CCB Proteus C-235 cyclotron facility paper).
- **ML-in-detector-signal-processing breadth (claims 9).** CWoLa/RF/ridge cover our specific methods,
  but a reviewer may want a domain review of ML pile-up/signal reconstruction; verify TC1/TC5 first.
</content>
