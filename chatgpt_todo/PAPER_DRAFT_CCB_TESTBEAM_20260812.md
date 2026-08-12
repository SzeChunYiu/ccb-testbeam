# Test-beam topology and response-model studies of scintillator range staves for HIBEAM/NNBAR

**Working manuscript draft, revised 2026-08-12**  
**Status:** complete prose for collaboration review; not yet submission-authorising for detector timing, absolute light collection, or detector energy resolution.  
**Repository base audited:** `main@4376a3f88c8e059a5c1a92c020856c98d31f538b`, with later issue-state corrections recorded in #993 and #1088.  
**Companion files:** `paper/hardware_bom.csv`, `PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md`, `PAPER_OPEN_ATOMS_20260812.md`, and `PAPER_PRE_SUBMISSION_REVIEW_20260812.md`. Refs #1296.

## Abstract

The HIBEAM/NNBAR programme is developing an annihilation detector for neutron-conversion searches, including free neutron-antineutron oscillation. One proposed detector element is a range stack of plastic-scintillator staves intended to sample the stopping pattern and energy loss of low-energy charged particles. We report a test-beam and simulation study of this concept using a 190 MeV proton-beam configuration with a deuterated target at the CCB facility in Krakow. The B arm contains eight physical scintillator layers in the source-bound detector model, while the analysed beam data provide four B-stack readout channels, conventionally labelled B2, B4, B6 and B8. The current stave specification is a 50 cm × 5.18 cm × 2.0 cm extruded-polystyrene element with two longitudinal Kuraray Y-11 wavelength-shifting fibres. The beam-test readout used only one fibre at one end, out of four possible fibre-end measurements.

The strongest beam-data result is a trigger-dependent stopping topology. The coincidence-selected Sample-I population is concentrated near the entrance of the B stack and contains a larger high-amplitude and saturated B2 population than the B-only Sample-II population, which penetrates more often to downstream readout channels. The proper amplitude analogue of a ΔE-E telescope is defined as ΔE = A(B2) and E = A(B4)+A(B6)+A(B8). Sparse longitudinal sampling limits this observable because the energy-loss maximum can occur in an uninstrumented physical layer; the pointing direction and apparent separation can therefore change with the readout-layer phase. An existing B2-versus-B4 study, based on 33,966 real-data coincidences, gives a Pearson correlation of +0.221 compared with -0.533 for a truth-level MC two-layer diagnostic. We retain that comparison as a response-model diagnostic only; B2 versus B4 is not labelled ΔE-E, and the data and truth-MC axes do not share an absolute energy scale.

A standalone Geant4 optical model predicts an order-10 detected-photoelectron response per deposited MeV at selected proton and deuteron calibration points, with campaign-reported relative spreads of about 9-21%. These numbers describe the implemented optical hypothesis, not an absolute calibration of the CCB stave. The current Y-11 model lacks a source-bound fluorescence-yield contract, and the SiPM operating point, coupling footprint and charge-domain response are not yet constrained well enough to authorise an absolute photon-to-ADC efficiency. A detector timing resolution is likewise withheld. The located 8×16-sample beam waveform product gives a B4-B6 residual central width of about 38 ns, dominated by 10 ns sampling and unstable pulse-window structure; it is not an intrinsic stave timing resolution. The test beam therefore establishes a measured stopping topology and a reproducible data-to-Monte-Carlo framework, while identifying the remaining waveform, material-budget and optical-response measurements required for quantitative timing and energy performance.

## 1. Introduction

The HIBEAM/NNBAR programme at the European Spallation Source is designed to search for neutron conversion processes, including neutron-antineutron oscillation. A free neutron-antineutron transition would violate baryon number by two units and would probe physics beyond the Standard Model [1]. The annihilation detector must identify the products of an antineutron interaction in a thin target and reconstruct a low-energy hadronic final state containing pions, nuclear fragments and secondary interactions [1].

The detector operates under constraints that differ from those of a collider spectrometer. The neutron flight region must remain magnetically quiet, limiting the use of a conventional magnetic momentum measurement. Many charged annihilation products also lie below the energy range in which a standard high-energy sampling calorimeter is most effective. HIBEAM/NNBAR detector studies therefore proposed a range measurement based on multiple layers of plastic scintillator followed by an electromagnetic calorimeter [2]. The range stack can provide the depth reached by a charged particle, the pattern of energy loss along its path and an inter-layer timing observable.

The CCB test beam was used to study this range-stack concept with charged particles whose stopping behaviour is accessible in both data and Geant4. The paper asks five experimental questions. First, does the B stack show distinct stopping and penetrating populations under different trigger conditions? Second, how much particle-identification information is retained when only four of the physical B-layer positions are represented in the analysed readout? Third, what timing information is supported by the available waveform products? Fourth, what does an explicit single-stave optical simulation predict for the response of the one-fibre, one-end readout? Fifth, how should that simulation be used to reconstruct deposited energy and define an energy-resolution measurement without treating model assumptions as calibration data?

The answers have different evidence status. We use four labels throughout the manuscript. **Beam-data measurement** refers to a quantity calculated from the real CCB data for a declared selected population. **Truth-level MC** refers to Geant4 particle or energy-deposit information before detector response. **Model-dependent detector MC** refers to a numerical prediction after optical or electronics modelling when some response parameters remain hypotheses. **Calibrated detector result** is reserved for a response quantity whose relevant parameters and data lineage have independent evidence and held-out closure. This distinction prevents simulation-only numbers from being presented as beam-data performance.

## 2. CCB test-beam configuration

Hardware facts, simulation-configuration values and unresolved legacy narratives are separated in `paper/hardware_bom.csv` (Refs #1296, PAPER-A01). Each row carries a status label: **MEASURED** (beam-data observation), **DESIGN_SPEC** (collaboration hardware clarification), **SIM_CONFIG** (reviewed Geant4/analysis configuration), or **UNKNOWN_EXTERNAL** (primary collaboration record still absent). Geant4 agreement alone does not resolve hardware contradictions.

### 2.1 Beam, target and two-arm layout

The reviewed CCB Geant4 run configuration specifies a 190 MeV incident proton beam and a 2.3 mm CD2 target (`SIM_CONFIG`; `geant4/macros/run_krakow.mac`). The event generator models the two-body channel

\[
p+d\rightarrow p+d,
\]

and transports the outgoing charged particles toward two scintillator arms. The source-bound configuration uses a nominal geometry-distance parameter of 109 cm, with the B stack at approximately -38° and the A stack at +71.5° (`SIM_CONFIG`; `geant4/configs/krakow.geoconf`). The corresponding configuration contains eight bars in the B stack and four in the A stack. These values describe the simulation/configuration geometry and should not be read as survey-grade metrology until the collaboration hardware record is bound to the manuscript.

The compact CCB Geant4 geometry contains the CD2 target, scintillator stack volumes, scintillator bars, a trigger bar and ProtoTPC volumes. A source audit found it suitable for first-order acceptance, particle-stopping and truth-energy-deposit studies, but not yet complete enough for precision material-budget conclusions. Detailed wrapping, support material, photosensor boards, cabling, dead layers and survey uncertainties are not all represented in the historical compact geometry. This limitation is important for downstream stopping distributions because a small unmodelled material change can move a Bragg peak from an instrumented layer to an uninstrumented one.

[**Figure 1:** source-bound CCB test-beam layout showing the CD2 target, B arm at approximately -38°, A arm at +71.5°, nominal 109 cm geometry parameter, eight B physical layers and four A layers. Caption: `SCHEMATIC / SOURCE-BOUND CONFIGURATION, NOT SURVEY METROLOGY`.]

### 2.2 A and B stacks, channel map and trigger families

The analysis in this paper concentrates on the B stack. The Monte Carlo represents eight physical B layers, whereas the selected data product uses four B readout channels labelled B2, B4, B6 and B8 (`DESIGN_SPEC`). The labels correspond to alternating positions in the stack rather than eight independent measurements in the beam data. For data-matched Monte Carlo, the documented detector-map contract is B2→`Sci_bar_LayerID` 0, B4→2, B6→4 and B8→6 with 4 cm centre-to-centre spacing between adjacent analysed layers (`SIM_CONFIG`; S12b detector-map contract). This sparse sampling is a defining feature of the test configuration and must be retained in any data-matched Monte Carlo comparison.

The A arm is used primarily to define the coincidence-selected event family. Sample I denotes an A-and-B coincidence run family and Sample II a B-only family (`UNKNOWN_EXTERNAL` for the exact hardware trigger, threshold and prescale record). The current analysis grouping binds Sample-I calibration runs 31–37 and 39–42, Sample-I analysis runs 44–57, Sample-II calibration run 64, and Sample-II analysis runs 58–63 and 65 (`SIM_CONFIG`; S03e configuration). Runs 38 and 43 are not part of these declared groups. In the current Monte Carlo, Sample-I and Sample-II membership is assigned with a first-layer charged-hit proxy rather than a source-bound simulation of the complete trigger-counter geometry and electronics (`SIM_CONFIG`; `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json`). We therefore label the Monte Carlo trigger selection `MC_TRIGGER_PROXY`. Agreement after this selection demonstrates that a corresponding kinematic/topological population exists in the model; it does not, by itself, validate the hardware trigger efficiency.

## 3. Scintillator stave and readout

### 3.1 Stave geometry and material record

The current stave specification follows the later hardware clarification in issue #796 (`DESIGN_SPEC`; `docs/stave_sim/STAVE_SIM_ENERGY_MODEL.md`) and the geometry implemented in `geant4/single_stave/`. Each stave is an extruded polystyrene scintillator 50 cm long, 5.18 cm wide and 2.0 cm thick along the nominal particle path. A TiO2-loaded reflective coating surrounds the exterior faces. Two longitudinal holes have 2.0 mm diameter and are separated by 2.0 cm centre to centre. Each hole accepts a 1.8 mm diameter Kuraray Y-11 wavelength-shifting fibre.

Older repository prose described BC-408 bars approximately 10 cm × 1 cm × 1 m (`UNKNOWN_EXTERNAL`; legacy academic chapter 2). Issue #796 itself contains an earlier conflicting `5 cm thickness` phrase that is superseded by the later 50 × 5.18 × 2.0 cm clarification. These contradictions are not resolved by Geant4 agreement alone; they remain open until a primary collaboration build record, drawing, photo or channel map is bound. Until then, publication text uses the #796 design specification and labels all other dimensions as unresolved legacy narrative.

The optical simulation resolves each fibre into a Y-11-doped polystyrene core, PMMA inner cladding and fluorinated-PMMA outer cladding (`SIM_CONFIG`; `docs/stave-geometry.md`). The implemented fibre outer-cladding radius is 0.90 mm. The simulated fibre protrudes beyond the scintillator so that guided photons can reach end-mounted sensor surfaces. Kuraray technical data for Y-11(200) list a representative green emission peak near 476 nm, an absorption peak near 430 nm and an attenuation length greater than 3.5 m [6] (`EXTERNAL_PRIMARY`). These manufacturer values provide a spectral and scale reference; they are not a measurement of the installed CCB fibre/coupling system.

The B-stave design can support two fibres read from both ends, corresponding to four possible optical measurements. The beam-test configuration used one fibre at one end only (`DESIGN_SPEC`; issues #796/#797). This matters for energy reconstruction because a one-ended signal depends on the hit coordinate along the stave through attenuation and coupling. It also removes the two-ended time or charge asymmetry that could otherwise be used to estimate longitudinal position and reduce this dependence.

[**Figure 2:** stave transverse and longitudinal geometry. Reuse the source-generated drawings under `figures/geometry/`, mark the two fibres and four possible fibre-end sensor positions, and highlight the single physical beam-test readout.]

### 3.2 SiPM and electronics boundary

The source-bound single-stave model uses a Hamamatsu S13360-3050CS multipixel photon counter (`DESIGN_SPEC`; issue #796). Hamamatsu specifies a 3×3 mm² photosensitive area, 50 µm pixel pitch and 3600 pixels for this device, with a typical peak sensitivity wavelength near 450 nm [7]. The spectral range is therefore compatible with the green Y-11 emission band.

The manufacturer page does not define the CCB detector response on its own. Photon detection efficiency varies with wavelength and overvoltage. The observed waveform also depends on temperature, optical coupling, illuminated microcell footprint, gain, recovery, crosstalk, afterpulsing and the analogue transfer function. The current project has explicit SiPM models for several of these effects, but later audits leave the operating-point recovery law, coupling footprint, correlated-noise distributions and charge-domain impulse normalisation incompletely constrained. We therefore keep the optical-photon, primary-avalanche, charge and ADC observables as separate stages.

### 3.3 Waveform products

Two waveform schemas appear in the repository history. Historical timing and S00 reproduction configs declare eight channels with 18 samples per channel at a nominal 10 ns sample period, reading laptop-era `data/root/root` and `data/sorted-b` mounts. The located immutable LUNARC beam product under `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/` contains eight channels with **16 samples per channel only** (`128` scalar HRDv words per event). PAPER-A02 / issue #993 closes this as **distinct acquisition schemas**, not a reversible 16↔18 transform:

| Product | Mount / manifest | Words / event | Authorising use |
|---|---|---:|---|
| LUNARC raw HRDv | `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/hrdb_run_*.root` | 128 (`8×16`) | **Yes** for paper amplitude and format-limited timing on beam data |
| Historical 18-sample configs + sorted-b | `configs/s00_reproduction.yaml`; laptop `data/sorted-b` | 144 (`8×18`) | **No** for the LUNARC raw product; timing remains historical/non-authorising |

Evidence: complete SHA-256 manifest for all 33 paper runs; per-event width census (`128` words only); run 31 LUNARC SHA-256 `0986c826…` ≠ laptop raw `9921aa75…`; 500-record spot check finds 45 baseline/amplitude/peak mismatches against the historical canonical S00 table, including canonical `peak_sample=17` cases impossible in 16-sample raw. Samples 16–17 are absent from LUNARC rows.

Every paper amplitude or timing figure must bind this schema, producer revision and source hashes. Sub-nanosecond historical timing values derived from 18-sample products are not promoted as beam-data detector performance on the located 8×16 raw files.

## 4. Simulation programmes

### 4.1 CCB event simulation

The CCB event simulation provides particle identities, trajectories and energy deposits across the two-arm detector. It is used to study which particle species enter the B stack, where they deposit energy and how the selected population changes under the trigger proxy. The reviewed historical source used Geant4 electromagnetic option 4 together with hadronic and ion physics including INCLXX, a reasonable starting point for proton/deuteron transport at these energies [4,5].

The source review also identified two provenance/physics risks that must be stated when interpreting older samples. The generator historically sampled an angular variable uniformly and carried differential-cross-section information as an event weight, so unweighted downstream distributions need not represent the intended scattering distribution. A possible centre-of-mass-versus-laboratory angle mismatch was also identified in the historical weight application. Later repository work has tightened weighted-estimand handling and provenance, but each final paper figure still needs to bind the exact production revision, weight definition, sum of weights and effective sample size.

### 4.2 Single-stave optical simulation

`geant4/single_stave/` provides a second, more detailed model for one scintillator element. Geant4 generates scintillation photons, propagates them through optical boundaries, applies absorption and wavelength shifting in the fibre, and transports photons toward sensor end surfaces [4,5]. A separate SiPM/digitiser layer converts sensor photons into avalanches and an electronics-domain observable.

The two simulations answer different questions. The CCB geometry simulation predicts the incident particle population and the energy deposited in each layer. The single-stave simulation predicts the detector response conditional on a particle depositing energy in one stave. An end-to-end energy reconstruction must compose these models once, with quenching, optical attenuation, PDE, saturation and electronics gain assigned to explicit stages.

### 4.3 Simulation evidence classes

We distinguish four simulation products in figures and tables:

1. **TRUTH-LEVEL MC:** particle truth and Geant4 energy deposits before detector response;
2. **DIGITISED MC:** simulated response reconstructed with the same observable definition as data;
3. **MODEL-DEPENDENT OPTICAL MC:** optical/SiPM output under declared but incompletely calibrated response assumptions;
4. **CALIBRATED DETECTOR MC:** reserved for a response whose important nuisance parameters are source-bound or measured and whose predictions close on held-out data.

The current single-stave PE/MeV result belongs to category 3.

## 5. Data taking and event selections

### 5.1 Run families

The current reconstruction separates the trigger families from the calibration/evaluation split. Sample I denotes the A-and-B coincidence run family; Sample II denotes the B-only family. The configuration used for the transfer studies assigns Sample-I calibration runs 31-37 and 39-42, Sample-I analysis runs 44-57, Sample-II calibration run 64, and Sample-II analysis runs 58-63 and 65. Runs 38 and 43 are not part of these declared groups. A publication table should ultimately bind this mapping to the hardware run log and record the trigger thresholds/prescales rather than relying only on analysis configuration.

The canonical selected-pulse table contains 640,737 B-stack pulses under the historical S00 selection contract, with the raw-to-selected lineage still subject to the waveform/product provenance gate. In the Sample-II analysis subset, the configuration records 125,096 selected pulses: 88,213 in B2, 21,229 in B4, 11,148 in B6 and 4,506 in B8. The pulse selection uses a baseline from the first waveform samples and a historical amplitude threshold of 1000 ADC.

These are selected-pulse counts, not particle efficiencies. Trigger requirements, thresholding and saturation affect the observed fractions.

### 5.2 Trigger-dependent stopping topology

The clearest beam-data result is the different depth pattern of Sample I and Sample II. In the existing selected-population report, Sample I contains 241,422 B2 pulses with a mean amplitude of 6090 ADC and a 41.7% fraction at or above the historical 7000 ADC saturation marker. Sample II contains 88,213 B2 pulses with a mean amplitude of 3663 ADC and a 6.1% saturated fraction. Sample II also contains a larger relative population in B4, B6 and B8.

Truth-level CCB Monte Carlo gives the same qualitative direction under the trigger proxy. The coincidence-like selection enriches deuterons in the first B layer, while the B-only sample is more proton-rich and penetrates farther. In the historical truth table, the first-B-layer Sample-I population has a deuteron fraction of about 0.735 and proton fraction of about 0.124, compared with 0.484 and 0.404 in Sample II. The A-arm first-layer population in Sample I is proton dominated. These truth fractions support a p/d kinematic interpretation, but they are not a hardware-trigger efficiency measurement.

[**Figure 3:** data selected-pulse depth profile for Sample I and II, B2/B4/B6/B8. Regenerate from the authorising data product, show counts and normalized fractions, and mark the selection/saturation definition.]

[**Figure 4:** weighted MC depth profile and first-layer truth composition for the same sample definitions. Caption must state `MC_TRIGGER_PROXY`, exact event-weight treatment and data-matched readout mapping.]

## 6. Inter-stave timing

### 6.1 Observable and covariance

For two staves \(i\) and \(j\), we define

\[
\Delta t_{ij}=t_j-t_i-t_{\mathrm{TOF},ij},
\]

where the final term is the expected time-of-flight difference for the chosen geometry and particle hypothesis. The pair width does not uniquely determine two single-stave resolutions without further assumptions. In the general case,

\[
\mathrm{Var}(\Delta t_{ij})=\sigma_i^2+\sigma_j^2-2\,\mathrm{Cov}(t_i,t_j).
\]

Common trigger phase, sampling phase, reconstruction choices or event conditions can introduce covariance. A final single-stave timing resolution should therefore come from an overconstrained multi-pair covariance model, an independently justified symmetry assumption, or an external reference detector. We do not divide a pair width by \(\sqrt{2}\) by default.

### 6.2 Time pickoff and amplitude correction

Leading-edge timing crosses a fixed threshold and is therefore amplitude dependent. Historical project studies explored empirical time-walk corrections, including terms proportional to \(1/A\). A production correction should be fitted on calibration runs only and evaluated without retuning on held-out runs. The required closure plots are the corrected residual mean and width versus amplitude, run and pulse class.

A constant-fraction discriminator does not automatically solve the problem for multi-component waveforms. Issue #1059 demonstrates a structural ambiguity in the repository's global-maximum CFD: if an early pulse has peak \(A_1\) and a later pulse has a larger peak \(A_2\), the first crossing of \(f A_2\) can jump from the early component to the later one when \(f\) crosses approximately \(A_1/A_2\). A scan in CFD fraction can therefore change which physical pulse is timed. Deterministic two-pulse controls in `scripts/cfd_fraction_transition.py` reproduce this switch without invoking beam data. The production producer therefore defaults to `first_local_peak`, which binds the threshold and crossing to the same selected component, and serializes component-assignment diagnostics. That selector law is explicitly non-authorising for physical pulse identity: saturation, recovery tails, baseline shifts and sub-sample phase can still retarget the selected component.

The minimum pair `sigma68` across CFD fractions on the same events is recorded only as an exploratory diagnostic (`SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY`, issue #1062). It must not be promoted as detector resolution or used to choose a production CFD fraction without independent component-stability evidence.

### 6.3 Result supported by the located raw data

The direct analysis of the located 8×16-sample beam files gives 5,207 B4-B6 events with valid CFD times and a central 68% residual width of approximately 38.0 ns after the applied time-of-flight subtraction. A more restrictive in-window subset does not improve the result. The B6 peak-position distribution is multi-modal and frequently lies at the waveform boundaries. With a nominal 10 ns sample period, the residual is dominated by waveform sampling/window structure.

We therefore report this as a **format-limited timing residual**, not as the B-stave timing resolution. Historical values near 0.54 ns for a combined estimator and 0.68-0.75 ns for single-stave-like quantities are not promoted as beam-data performance. They belong to earlier simulation, toy-digitiser or provenance-gated analyses. Issue #993 closes the 16- versus 18-sample lineage as **distinct schemas**; cross-schema timing transfer remains quarantined. A real-data CFD fraction-transition study may proceed only on the authorising 8×16 LUNARC product (PAPER-A04); component-binding evidence outside that schema is limited to deterministic synthetic controls and non-authorising producer diagnostics.

[**Figure 5:** B4-B6 residual from the located 8×16 data product. Caption must include `10 ns nominal sampling`, event count, waveform schema and `NOT DETECTOR RESOLUTION`.]

[**Figure 6:** production timing closure, to be inserted only after PAPER-A04 closes. Required panels: pre/post correction residual, residual mean/width versus amplitude, run-held-out closure and CFD component-stability diagnostic.]

## 7. Amplitude ΔE-E and the segmentation limit

### 7.1 Correct telescope definition

For a range telescope, \(\Delta E\) is the energy lost in the upstream sampling layer and \(E\) is the residual energy measured downstream. The supervisor-defined CCB data analogue is therefore

\[
\Delta E_{\mathrm{data}} = A(B2),
\]

\[
E_{\mathrm{data}} = A(B4)+A(B6)+A(B8),
\]

where \(A\) denotes the baseline-subtracted pulse amplitude in ADC units. These axes are amplitude proxies, not calibrated energy.

The data-matched four-readout Monte Carlo definition is

\[
\Delta E_{\mathrm{MC,4}} = E_{\mathrm{dep}}(B2),
\]

\[
E_{\mathrm{MC,4}} = E_{\mathrm{dep}}(B4)+E_{\mathrm{dep}}(B6)+E_{\mathrm{dep}}(B8).
\]

For the full eight-layer truth model, the residual energy observable should sum all downstream B-stack layers available in the MC rather than discarding the uninstrumented layers. We therefore produce both a full-segmentation truth panel and a data-matched four-readout panel.

An earlier B2-versus-B4 plot is useful as a two-channel correlation diagnostic, but it is not the proper ΔE-E analogue. It should be labelled `B2-B4 amplitude correlation` or `two-layer response diagnostic` throughout the repository and paper.

### 7.2 Why sparse segmentation matters

The beam-test readout misses alternating physical layers. This can change the shape of the ΔE-E pattern when the steep increase in stopping power near the end of a charged-particle track occurs in a non-readout layer. A small shift in particle energy or passive material can move the high-dE/dx region from an instrumented to an uninstrumented stave. Consequently, the apparent pointing direction of the sparse four-channel ΔE-E distribution can change even when the underlying continuous stopping physics is unchanged.

This is not a failure of the ΔE-E principle. It is an aliasing problem caused by coarse longitudinal sampling. A future fully instrumented range stack would retain more of the Bragg-curve information and should be less sensitive to the readout-layer phase. PAPER-A10 therefore compares the full eight-layer MC with the data-matched four-layer view to quantify the information loss.

### 7.3 Production ΔE–E and two-channel diagnostic

Issue #956 regenerated the amplitude ΔE–E observable from the authorising S00 selected-pulse table using composite keys `(source_file_id, run_id, event_id)` and analysis-run groups only (Sample-I runs 44–57; Sample-II runs 58–63, 65). Missing downstream readout channels are zero-filled only after composite-key validation.

For the proper downstream-sum definition, Sample-I contains 147,274 physical events with median ΔE = 7101 ADC and median downstream E = 0 ADC because most coincidence-selected tracks stop at B2; the weighted Pearson correlation between ΔE and E is −0.042 with a run-block bootstrap interval [−0.051, −0.030]. Sample-II contains 69,174 events with median ΔE = 3567 ADC, median E = 4405 ADC (16–84% range 0–4405 ADC) and r = −0.070 ([−0.091, −0.029]). B2 saturation (≥7000 ADC) affects 51.8% of Sample-I and 7.6% of Sample-II B2 amplitudes; excluding saturated B2 events shifts Sample-I r to −0.092.

Under `MC_TRIGGER_PROXY` with PrimaryWeight propagation (Σw and ESS recorded in `reports/paper_956_deltaE_E_20260812T103800Z/`), the data-matched four-readout MC gives r = −0.70 (Sample I, n = 46,992, ESS = 23,099) and r = −0.46 (Sample II, n = 203,459, ESS = 102,463). Full-downstream truth sums yield r = +0.13 and +0.045 for the same samples, illustrating segmentation loss when uninstrumented layers are included.

The historical B2-versus-B4 two-channel diagnostic (33,966 events, r = +0.221) used an `eventno`-only join and is retained only as a legacy reference. The composite-key rerun with both B2 and B4 present gives n = 25,423 and r = +0.151 ([0.123, 0.178]); it is labelled `two-channel response diagnostic` and is not ΔE–E.

[**Figure 7:** `reports/paper_956_deltaE_E_20260812T103800Z/figures/fig07_data_deltaE_E_per_sample` — DATA amplitude ΔE–E per sample, identical axes, B2 saturation line at 7000 ADC, run-block bootstrap in `tables/sample_summary.json`.]

[**Figure 8:** `reports/paper_956_deltaE_E_20260812T103800Z/figures/fig08_mc_deltaE_E_{I,II}` — MC four-readout vs full-downstream panels per sample; PrimaryWeight-weighted; `MC_TRIGGER_PROXY`. Segmentation phase ablation: `fig_segmentation_readout_phase`.]

## 8. Monte Carlo prediction of light collection and transport

### 8.1 Response stages

The single-stave simulation is most useful when the response is decomposed into causal stages rather than represented by one fitted efficiency:

\[
E_{\mathrm{dep}}
\rightarrow E_{\mathrm{vis}}
\rightarrow N_{\gamma,\mathrm{scint}}
\rightarrow N_{\gamma,\mathrm{WLS\ abs}}
\rightarrow N_{\gamma,\mathrm{WLS\ emit}}
\rightarrow N_{\gamma,\mathrm{sensor}}
\rightarrow N_{\mathrm{primary\ aval}}
\rightarrow Q
\rightarrow A_{\mathrm{ADC}}.
\]

The first step includes quenching; the middle steps contain geometry, WLS and attenuation; the sensor step contains PDE; and the final steps contain SiPM/electronics response. Keeping them separate makes it possible to identify which measurement constrains which model parameter.

### 8.2 Existing optical-MC campaign

A completed single-stave Geant4 campaign generated representative deposited-energy and detected-photoelectron points for protons and deuterons:

| particle | kinetic energy [MeV] | mean Edep [MeV] | simulated detected PE | PE/MeV | campaign-reported relative spread |
|---|---:|---:|---:|---:|---:|
| proton | 60 | 28.7 | 282 ± 25 | 9.85 | 8.9% |
| proton | 100 | 16.2 | 177 ± 17 | 10.9 | 9.3% |
| proton | 140 | 12.7 | 140 ± 29 | 11.0 | 20.8% |
| deuteron | 70 | 49.7 | 432 ± 62 | 8.7 | 14.5% |
| deuteron | 110 | 28.6 | 276 ± 48 | 9.6 | 17.2% |

The campaign demonstrates that the implemented one-fibre, one-end optical model produces a signal of order ten detected photoelectrons per deposited MeV over these points. It does **not** establish a measured CCB light yield or a calibrated total collection efficiency.

The absolute interpretation is blocked by an upstream photophysics uncertainty. The current Geant4 Y-11 model specifies WLS absorption, emission spectrum and timing, but no source-bound fluorescence-yield/multiplicity contract. Geant4's default one-secondary behaviour therefore acts as a model assumption. Issue #1088 has been reopened on this scientific acceptance criterion. A downstream PDE scale or coupling factor could compensate the mean light yield at one point without reproducing the same photon-count variance, timing, wavelength distribution or saturation behaviour.

The project also lacks a fully source-bound CCB operating-point transfer from sensor photons to charge/ADC. For this reason, the paper should use **model-dependent optical response** for the table above. The older analytical value of 0.56% total scintillation-photon-to-photoelectron efficiency is not a publication result.

### 8.3 Quantities required for a physical efficiency statement

The final optical chapter should report stage ratios such as

\[
\epsilon_{\mathrm{WLS\ capture}}=
\frac{N_{\gamma,\mathrm{WLS\ abs}}}{N_{\gamma,\mathrm{scint}}},
\]

\[
\epsilon_{\mathrm{transport}}=
\frac{N_{\gamma,\mathrm{sensor}}}{N_{\gamma,\mathrm{WLS\ emit}}},
\]

\[
\epsilon_{\mathrm{PDE}}=
\frac{N_{\mathrm{primary\ aval}}}{N_{\gamma,\mathrm{sensor}}}.
\]

These ratios should be shown versus hit position, particle/deposit regime and the relevant nuisance parameters. The physical F1+x beam-test channel should be compared with the other simulated fibre/end control channels to quantify the information lost by one-fibre, one-end readout.

[**Figure 9:** existing Edep-versus-detected-PE optical MC for proton and deuteron points. Caption: `MODEL-DEPENDENT OPTICAL MC; ABSOLUTE LIGHT YIELD NOT AUTHORISED`.]

[**Figure 10:** stage-resolved optical efficiencies, to be generated by PAPER-A07/A08.]

## 9. Energy reconstruction and resolution

### 9.1 Define the reconstruction target

"Energy resolution" can refer to several different quantities in this detector. For the single-stave optical simulation, the cleanest first target is the Geant4 deposited energy \(E_{\mathrm{dep}}\). For the full range stack, a later target is the incident charged-particle kinetic energy inferred from amplitudes and stopping depth. These are not interchangeable and should not be combined into one number.

For the single-stave study we define the event residual

\[
r=\frac{E_{\mathrm{reco}}-E_{\mathrm{dep}}}{E_{\mathrm{dep}}}.
\]

A publication analysis should report the median bias, central 68% width \(\sigma_{68}\), RMS and a tail fraction on held-out events. If the residual is non-Gaussian, a single fitted Gaussian width is insufficient.

### 9.2 Held-out deposited-energy reconstruction (PAPER-A09 / #1297)

The optical calibration grid at `/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid/` provides five SHA-256-bound ROOT files (200 events each; Geant4 commit `0005ed0cb2c06617abd36b3bb1e615497e15832a`). Training uses `deuteron_70`, `proton_100` and `proton_140` (600 events); held-out evaluation uses `deuteron_110` and `proton_60` (400 events). A pooled linear response `PE = (49.3 \pm 2.5) + (7.63 \pm 0.08)\,E_{\mathrm{dep}}` is fit on the training population only and inverted to obtain \(E_{\mathrm{reco}}\). No ADC/MeV heuristic enters this chain.

On the held-out fraction the relative residual \(r=(E_{\mathrm{reco}}-E_{\mathrm{dep}})/E_{\mathrm{dep}}\) gives a median bias of \(+10.1\%\), central width \(\sigma_{68}=8.9\%\), RMS \(=17.8\%\) and tail fraction \(|\!r\!|>0.20\) of 15%. Per held-out grid point:

| species | held-out KE [MeV] | median \(E_{\mathrm{dep}}\) [MeV] | median bias | \(\sigma_{68}\) | RMS | tail fraction |
|---|---:|---:|---:|---:|---:|---:|
| proton | 60 | 27.6 | +10.3% | 8.3% | 15.9% | 13.5% |
| deuteron | 110 | 26.5 | +9.9% | 9.1% | 19.6% | 16.5% |

A species-aware two-line calibration reduces the pooled median bias to \(+8.1\%\) but widens \(\sigma_{68}\) to 23.5% on the same held-out events, so the common proton/deuteron line is retained as the transparent primary baseline. Saturation corrections are not required at these deposited-energy points (mean saturation fraction 0). Longitudinal hit-position variation is negligible in this campaign and is not used.

These numbers are **model-dependent optical MC** results: they describe reconstruction of Geant4 deposited energy from simulated detected PE under the current Y-11/SiPM hypothesis. They are not a beam-data energy calibration and do not authorise relabelling ADC amplitudes in MeV. The optical/SiPM nuisance envelope from PAPER-A07/A08 remains `NOT_EVALUATED`.

[**Figure 11:** held-out single-stave \(E_{\mathrm{reco}}\) bias and \(\sigma_{68}\) versus \(E_{\mathrm{dep}}\) for the two held-out grid points. Caption: `MODEL-DEPENDENT OPTICAL MC; TARGET IS GEANT4 E_dep; NOT BEAM-DATA CALIBRATION`. Source: `reports/paper_a09_heldout_edep_reconstruction/`.]

[**Table 2:** energy-reconstruction summary (`heldout_energy_reconstruction_summary.csv`). Estimator: pooled linear PE\(\rightarrow\)\(E_{\mathrm{dep}}\); train/held-out split as above; \(n=400\) held-out events; nuisance envelope blocked pending A07/A08.]

### 9.3 Full-stack reconstruction

A full-stack incident-energy estimator can use the amplitude vector

\[
\mathbf{A}=(A_{B2},A_{B4},A_{B6},A_{B8}),
\]

saturation flags and the deepest active readout position. A physics baseline should precede any machine-learning model: for example, a calibrated sum of visible energy plus a range/stopping-depth correction. The Monte Carlo can then quantify the performance lost when the eight physical layers are reduced to the four-channel data view.

This full-stack result remains blocked until the passive material, per-channel response and data/MC trigger/selection transfer are sufficiently constrained. The paper can describe the reconstruction method now, but a detector energy-resolution number should be inserted only after held-out closure.

## 10. Discussion

The beam data demonstrate the basic range-stack behaviour needed for the HIBEAM/NNBAR concept: the selected B-stack population changes markedly between the two trigger families, with one population concentrated near the entrance and the other penetrating more deeply. Truth-level Geant4 gives a corresponding change in p/d composition under its trigger proxy. The current evidence supports a topology statement; a quantitative trigger efficiency or absolute stopping probability requires the hardware trigger response and material budget to be closed.

The ΔE-E study explains why the beam-test segmentation should not be judged by the appearance of one two-dimensional plot. The physically relevant data proxy uses B2 for \(\Delta E\) and the sum of B4, B6 and B8 for residual \(E\). Because alternating physical layers are absent from the analysed readout, the sampled Bragg rise can fall between channels. A small shift in incident energy or passive material can then change the direction of the sparse sampled correlation. The appropriate conclusion is that the test configuration retains stopping-depth information but loses part of the finely sampled dE/dx sequence.

The timing analysis provides a separate lesson. The located raw waveform product is adequate for pulse-amplitude and coarse timing diagnostics, but it does not support a sub-nanosecond detector-resolution measurement. The 10 ns sampling/window structure and the unresolved relationship between the 16- and 18-sample products dominate the current direct residual. Multi-component waveforms also require the timed pulse to be defined before a CFD fraction is optimised. These requirements specify what a future timing result must demonstrate rather than supplying a performance number from incomplete provenance.

The optical model gives a plausible signal scale and a framework for energy reconstruction, but the absolute response remains underdetermined. WLS fluorescence yield, coupling, PDE at the operating point, microcell response and electronics transfer can compensate one another in the mean. Stage-resolved counters and independent constraints are therefore more informative than tuning one total efficiency to a data amplitude. The reopened #1088 physics atom and the SiPM operating-point tasks define this closure programme.

The test configuration also indicates practical design priorities for a future range detector: instrument more longitudinal layers where feasible, preserve a position-sensitive or two-ended optical observable, avoid first-layer saturation, and record waveform windows with a calibrated time reference and enough samples to isolate the intended pulse component.

## 11. Conclusions

The CCB campaign provides a measured test of the stopping topology of a scintillator range stack for HIBEAM/NNBAR and a structured path from particle transport to optical/electronics response. In beam data, the Sample-I selected population is concentrated near B2 and contains a larger high-amplitude/saturated component, while Sample II reaches downstream B channels more often. The corresponding truth-level Monte Carlo gives a coincidence-like population enriched in deuterons at the B entrance and a more penetrating B-only population.

For particle-identification plots, the correct beam-data amplitude analogue is \(\Delta E=A(B2)\) and \(E=A(B4)+A(B6)+A(B8)\). The four-channel readout misses alternating physical layers, so the sampled ΔE-E topology is sensitive to where the stopping-power rise falls relative to the readout positions. An existing B2-B4 correlation difference between data and truth MC remains useful as a two-layer model diagnostic but is not itself the paper's ΔE-E measurement.

The standalone optical simulation predicts roughly 9-11 detected PE per deposited MeV at the existing proton/deuteron campaign points, with reported relative spreads of roughly 9-21%. Held-out reconstruction of Geant4 deposited energy from detected PE on the SHA-256-bound calibration grid gives a pooled median bias of about +10% and \(\sigma_{68}\approx 9\%\) on held-out grid points. These are model-dependent predictions because the absolute WLS fluorescence yield and CCB SiPM/electronics response are not yet fully constrained. The located raw 8×16 waveform product gives an approximately 38 ns B4-B6 residual that is sampling/window limited and is not an intrinsic stave timing resolution.

The paper is therefore already able to report the measured stopping topology, the correct sparse-segmentation ΔE-E framework, and the limitations of the current waveform product. The remaining P0 analyses are well defined: establish the publication hardware/run and waveform provenance, regenerate the proper amplitude ΔE-E and data-matched weighted MC comparisons, close the material budget, resolve the optical/SiPM response stages, and evaluate held-out deposited-energy reconstruction. Those steps are required before adding detector timing, absolute optical-efficiency or detector energy-resolution numbers.

## 12. Reproducibility and figure-generation requirements

Every final quantitative figure should be generated from a tracked result file through the repository result-registry/figure tooling. The figure producer must record the source commit, configuration, input paths and SHA-256 values, event selection, event/run counts, weight treatment and uncertainty method. No final plot should contain a number copied manually from this manuscript.

Data and Monte Carlo must use matching observable definitions before a quantitative closure statement is made. ADC amplitude and Geant4 truth EDep may be displayed in separate panels, but they must not be overlaid on a shared numerical energy axis without a validated response transform. Weighted Monte Carlo outputs should report \(\sum w\), \(\sum w^2\) and effective sample size for the estimand being plotted.

Timing and energy calibrations must be fitted on declared calibration/training populations and evaluated on held-out runs or simulation points without retuning. Resampling should preserve run/event dependence rather than treating all pulses as independent observations.

## Evidence paths used for this draft

- `paper/manuscript_outline.md`
- issue #618, current supervisor ΔE-E definitions and required plots
- issue #796 and #797, stave/readout and paper requirements
- issue #879, segmentation sensitivity of sparse ΔE-E readout
- `docs/stave-geometry.md`
- `geant4/configs/krakow.geoconf`
- `reports/1781181864.166832.35d806b2__s21_geant4_source_review/REPORT.md`
- `configs/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.yaml`
- `reports/SAMPLE_I_II_DATA_MC_REPORT.md`
- `reports/studies/data_side/REPORT.md`
- `docs/claim_ledger.csv`
- `docs/adr/ADR-WLS-FLUORESCENCE-YIELD-UNVERIFIED.md`
- `docs/adr/ADR-SIPM-PHYSICS-BLOCKED-WAVEA-LANE01.md`
- issue #993, closed as **distinct 8×16 LUNARC raw vs 8×18 historical products**; cross-schema timing quarantined
- issue #1059, CFD component-selection ambiguity
- issue #1088, reopened for the unresolved WLS fluorescence-yield physics contract

Where an older narrative conflicts with these evidence surfaces, the older value is treated as historical until independently verified.

## References

1. S.-C. Yiu et al., "Status of the Design of an Annihilation Detector to Observe Neutron-Antineutron Conversions at the European Spallation Source," *Symmetry* **14** (2022) 76. DOI: 10.3390/sym14010076.
2. K. Dunne et al., "The HIBEAM/NNBAR Calorimeter Prototype," *Journal of Physics: Conference Series* **2374** (2022) 012014. DOI: 10.1088/1742-6596/2374/1/012014. arXiv:2107.02147.
3. J. Barrow et al., "A Computing and Detector Simulation Framework for the HIBEAM/NNBAR Experimental Program at the ESS," *EPJ Web of Conferences* **251** (2021) 02062. DOI: 10.1051/epjconf/202125102062. arXiv:2106.15898.
4. S. Agostinelli et al., "Geant4: a simulation toolkit," *Nuclear Instruments and Methods in Physics Research A* **506** (2003) 250-303. DOI: 10.1016/S0168-9002(03)01368-8.
5. J. Allison et al., "Recent developments in Geant4," *Nuclear Instruments and Methods in Physics Research A* **835** (2016) 186-225. DOI: 10.1016/j.nima.2016.06.125.
6. Kuraray Co., Ltd., "Spectral and Characteristic Data: Wavelength Converting Fiber," Y-11(200) technical data, accessed 2026-08-12. Manufacturer values are representative rather than guaranteed specifications.
7. Hamamatsu Photonics K.K., "MPPC S13360-3050CS," official product specifications, accessed 2026-08-12.

## Publication blockers and handoff

The manuscript is ready for collaboration-level editing, but the full detector-performance version is not ready for submission. The executable remaining tasks are in `chatgpt_todo/PAPER_OPEN_ATOMS_20260812.md`. Highest priority is PAPER-A01/A02/A03 for hardware, run and waveform provenance; PAPER-A04 for a physically defined timing measurement; PAPER-A05/A06 for the correct amplitude ΔE-E and data-matched weighted MC; PAPER-A07/A08 for stage-resolved optical/SiPM response; and PAPER-A09 for held-out deposited-energy reconstruction. The final review loop should be rerun after those result files update the claim ledger.