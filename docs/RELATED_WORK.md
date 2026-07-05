# Related work & references — CCB test-beam analysis

> Prepared with `nature-academic-search` + `nature-citation`. Every citation used below is a
> **verified** entry in `docs/references.bib` (title/authors/year/venue confirmed by web search on
> 2026-07-05; DOIs included only where confident). Candidate references that could not be fully
> verified are held in `references.bib` and cited here only once confirmed. As of the 2026-07-05 pass,
> the former `TO-CHECK` stubs [TC1]–[TC6] have all been verified (authors + venue + DOI via Crossref)
> and promoted to live entries, and the CCB facility and scintillator range-telescope method gaps are
> now closed. Nothing in this file is fabricated; residual thin spots are flagged in Section 9.

This analysis measures **same-particle (proton) timing resolution** and **pile-up behaviour** in the
HIBEAM High-Resolution Detector (HRD) plastic-scintillator range staves, using ~190 MeV protons on a
CD2 target at the Cyclotron Centre Bronowice (CCB, Krakow), with a GEANT4 truth simulation and a
traditional-vs-ML methodology. The ~190 MeV beam is the IBA Proteus C-235 research beam (continuously
variable 70–230 MeV) in the CCB physics experimental hall, documented in the CCB facility paper
[`Maj2024CCB`], with the IFJ PAN proton programme's founding eye-therapy facility described in
[`Swakon2010CCB`]; scintillator detector test beams at this facility are exemplified by [`Briz2022ProtonRad`].
The related work falls into eight groups.

## 1. Physics motivation: HIBEAM-NNBAR and the neutron-antineutron search

The HRD is a subsystem developed in the context of the HIBEAM/NNBAR program at the European Spallation
Source, whose goal is a search for free neutron→antineutron oscillation (and n→sterile-n conversion)
with sensitivity up to three orders of magnitude beyond previous limits [`Addazi2021HIBEAM`]. The
instrument design and its detector suite are described in the HIBEAM instrument paper
[`HIBEAM2025Instrument`], and the detector-simulation framework used for the program (the lineage of
our GEANT4 truth setup) in [`NNBAR2021Framework`]. The broader ESS particle-physics programme into
which HIBEAM/NNBAR fits is reviewed in [`Abele2023ESS`]. These anchor *why* a scintillator range
telescope with well-characterised timing and pile-up response matters.

## 2. High-Resolution Detector (HRD) / scintillator range telescopes

The HRD operates as a **range telescope**: charged particles leaving the target deposit energy across a
depth-ordered stack of plastic-scintillator staves, and the penetration profile encodes particle
species and energy. The established plastic-scintillator range-telescope method — a depth-ordered
scintillator stack read out to reconstruct proton energy/range — is given by the ASTRA range-telescope
work of Granado-González et al. [`GranadoGonzalez2022ASTRA`], and a scintillator range/energy detector
tested at exactly the CCB proton beam is reported in [`Briz2022ProtonRad`]. The HIBEAM-program lineage
of the HRD and its detector-simulation treatment are covered by the HIBEAM references above
[`HIBEAM2025Instrument`, `NNBAR2021Framework`]; the underlying proton stopping-power/range scale we
validate against is the NIST PSTAR tabulation [`NISTPSTAR`]. *(No HIBEAM-NNBAR-specific HRD instrument
paper exists; `GranadoGonzalez2022ASTRA` is used as the closest established scintillator range-telescope
method reference — see Section 9.)*

## 3. Plastic-scintillator + SiPM/WLS timing-resolution methods

Our headline observable — sub-nanosecond timing from plastic-scintillator staves — sits in the
established plastic-scintillator + SiPM timing literature. The J-PET work on the time resolution of
long plastic-scintillator strips with multi-SiPM readout [`Moskal2016JPET`] provides directly
comparable coincidence-resolving-time methodology (timestamp combination, time-walk handling, and
achievable ~0.2–0.4 ns resolution) against which our per-stave σ values can be benchmarked. A
complementary single-strip benchmark — the intrinsic time resolution of a BC422 plastic scintillator
read out by a SiPM — is given by Stoykov and Rostomyan [`Stoykov2021BC422`].

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
inclusive; ~0.85–1.1 ns per-stave at high amplitude). An explicit event-by-event leading-edge time-walk
correction (threshold-crossing vs. energy) is demonstrated for PET detectors by Du et al.
[`Du2017TimeWalk`], directly supporting our amplitude-walk approach.

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
`Allison2016Geant4`]. Broader domain support for ML in detector signal processing comes from neural-
network pulse-shape discrimination and pile-up recovery in organic scintillators [`Fu2018ANNpileup`]
and real-time deep-learning signal reconstruction under high pile-up on FPGAs [`Ortiz2019FPGApileup`].

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
| 6 | HRD is a "range telescope"; "Sci_bar hits fall with depth (layers 0→7)" | 2 | `GranadoGonzalez2022ASTRA`, `Briz2022ProtonRad`, `HIBEAM2025Instrument`, `NNBAR2021Framework`, `NISTPSTAR` | covered — scintillator range-telescope method now cited (no HIBEAM-specific HRD paper exists) |
| 7 | "190 MeV proton beam strikes a CD2 target … two independent HRD range stacks at conjugate angles" (CCB facility) | 1, 7 | `Maj2024CCB`, `Swakon2010CCB`, `Briz2022ProtonRad`, `Ermisch2003PD` | covered — CCB Proteus C-235 facility now cited |
| 8 | HIBEAM/NNBAR motivation (n→n̄ search, ESS) | 1 | `Addazi2021HIBEAM`, `HIBEAM2025Instrument` | covered |
| 9 | "ML wins shape-closure tasks" (AE/PCA basis beats median template; weak-label proxies) | 8 | `Metodiev2017CWoLa`, `Breiman2001RF`, `Hoerl1970Ridge`, `Fu2018ANNpileup`, `Ortiz2019FPGApileup` | covered; broader ML-DSP support now cited |
| 10 | "Sample-I D-enrichment confirmed (S21 truth 1.519; S23 data 3.45)" | 7 | `Ermisch2003PD`, `Sekiguchi2017DP` | covered |
| 11 | GEANT4 truth-tree production, energy-scale validation | 8/sim | `Agostinelli2003Geant4`, `Allison2006Geant4`, `Allison2016Geant4` | covered |

**Citation gaps — status after the 2026-07-05 verification pass:**
- **HRD / range-telescope method paper (claims 6, 7) — CLOSED (with caveat).** No HIBEAM-NNBAR-specific
  HRD instrument paper exists in the literature. The established scintillator range-telescope *method* is
  now cited via the ASTRA range telescope [`GranadoGonzalez2022ASTRA`] and a scintillator range/energy
  detector operated at the CCB proton beam [`Briz2022ProtonRad`]. The remaining (optional) improvement is
  an internal HIBEAM HRD design note, which is a collaboration document rather than a citable paper.
- **CCB (Cyclotron Centre Bronowice) beam-facility reference — CLOSED.** The 190 MeV Proteus C-235
  research beam is now cited via the CCB facility paper [`Maj2024CCB`], with [`Swakon2010CCB`] for the
  IFJ PAN proton-therapy heritage and [`Briz2022ProtonRad`] for a detector test beam at this facility.
- **ML-in-detector-signal-processing breadth (claim 9) — CLOSED.** Domain support added via
  [`Fu2018ANNpileup`] (NN PSD / pile-up recovery) and [`Ortiz2019FPGApileup`] (real-time DL signal
  reconstruction under pile-up).
</content>
