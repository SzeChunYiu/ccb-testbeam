# Test-beam characterisation of scintillator range staves for the HIBEAM/NNBAR annihilation detector

**Working manuscript draft, 2026-08-12**  
**Status:** near-complete prose, not submission-authorising. Numerical claims are classified below as measured data, model-dependent simulation, source-bound configuration, or blocked pending an explicit evidence gate.  
**Repository base used for this draft:** `main@4376a3f88c8e059a5c1a92c020856c98d31f538b` plus the evidence paths listed in this document.

## Abstract

The HIBEAM/NNBAR programme is developing an annihilation detector for searches for neutron conversion processes, including free neutron-antineutron oscillation. A proposed calorimetric element uses layers of plastic scintillator to estimate the range and energy-loss pattern of low-energy charged particles, for which conventional high-energy sampling calorimetry is not optimal. We report a test-beam and simulation study of the scintillator range-detector concept using a 190 MeV proton beam incident on a deuterated target at the CCB facility in Krakow. The B-stack, which is the focus of this work, comprises eight physical scintillator layers but only four readout channels in the analysed data. Each source-bound stave design is a 50 cm × 5.18 cm × 2.0 cm extruded-polystyrene element with two longitudinal Kuraray Y-11 wavelength-shifting fibres; in the test configuration only one fibre was read out at one end.

The data establish a clear trigger-dependent stopping topology. In the analysis population, the coincidence-selected sample is concentrated in the first B channel and contains a much larger fraction of high-amplitude and saturated pulses than the single-B sample, while the latter penetrates more deeply into the stack. A direct amplitude-based ΔE-E representation is therefore informative as a topology diagnostic, but the four-channel longitudinal sampling and the strong first-channel occupancy limit conventional finely segmented ΔE-E particle identification. In a real-data B2-B4 coincidence sample of 33,966 events, the measured amplitude correlation is +0.221, whereas the current Geant4 truth comparison gives a correlation of -0.533 under a different observable scale. The sign difference is a useful model diagnostic, not evidence for an absolute energy disagreement, because the data are in ADC units and the simulation values are truth-level energy deposits.

A standalone Geant4 optical model predicts an order-10 detected-photoelectron response per deposited MeV for one-fibre, one-end readout and gives model resolutions of roughly 9-21% at selected proton and deuteron energies. These values are retained here as model-dependent predictions only. The current model uses an unverified Geant4 default WLS re-emission assumption, and the SiPM operating point, coupling footprint, charge transfer function and correlated-noise model are not yet source-bound well enough to authorise an absolute light-collection efficiency. Similarly, a detector timing resolution is not quoted from beam data. The located 8×16-sample raw waveform product gives a B4-B6 residual width of about 38 ns, which is dominated by the 10 ns sampling and unstable pulse-window timing and is explicitly not a detector resolution. Precision timing remains blocked by waveform-product lineage and by a constant-fraction timing ambiguity on multi-component pulses. The study therefore provides a measured topology result, a reproducible framework for data-to-Monte-Carlo comparisons, and a concrete programme for closing the remaining timing, optical and energy-calibration uncertainties.

## 1. Introduction

The HIBEAM/NNBAR programme targets processes in which neutrons convert to sterile neutrons and/or antineutrons. Observation of neutron-antineutron conversion would violate baryon number and would have consequences for models of baryogenesis and physics beyond the Standard Model [1]. The detector concept for such a search must identify an antineutron-nucleon annihilation in a thin target and reconstruct the resulting low-energy hadronic final state. The expected final state is dominated by pions, with additional nuclear fragments and secondary interactions [1].

A practical complication is that the neutron flight region must be magnetically quiet. The annihilation detector therefore cannot rely on a conventional magnetic spectrometer for momentum reconstruction. At the same time, kinetic energies of many charged annihilation products are below the regime in which a traditional sampling calorimeter gives its best performance. Earlier HIBEAM/NNBAR detector studies consequently proposed a hadronic range measurement using multiple plastic-scintillator layers followed by an electromagnetic calorimeter [2]. The range stack is intended to provide three complementary observables: the number of layers traversed, the energy-loss pattern as a function of depth, and timing information between layers.

The present work studies that range-detector concept with CCB test-beam data and a hierarchy of Monte Carlo models. The goals are deliberately narrower than a full annihilation-detector performance measurement. We ask whether the prototype produces the expected stopping-versus-penetrating topology in real beam data, whether Geant4 reproduces the qualitative depth structure, what information is retained by a sparsely read out ΔE-E representation, what the current optical model predicts for one-fibre, one-end light collection, and which parts of timing and energy reconstruction are already supported by data rather than by simulation assumptions.

This distinction between measured response and model prediction is central to the paper. Several historical project notes quoted sub-nanosecond timing resolutions and an absolute photoelectron yield as if they were detector measurements. Subsequent audit work showed that these quantities depend on unresolved waveform provenance, timing-estimator definitions, optical assumptions, or simulation-only calibrations. We therefore report each result with its evidence class and withhold a detector-performance number when the required calibration is not identifiable from the present data.

## 2. CCB test-beam configuration

### 2.1 Beam and target

The Geant4 configuration used to model the CCB campaign specifies a 190 MeV incident proton beam and a 2.3 mm CD2 target. The source model produces the two-body final state

\[
p+d\rightarrow p+d,
\]

and propagates the outgoing particles toward two scintillator stacks. The compact CCB geometry places the two arms at approximately -38° and +71.5° with a nominal 109 cm geometry-distance parameter. The model contains eight bars in the first stack and four in the second. These values are source-bound in `geant4/configs/krakow.geoconf` and in the reviewed run macro, but they should not be interpreted as a substitute for a survey-grade mechanical drawing. The current Geant4 geometry is a compact representation and does not include every support, wrapping, cable or electronics material.

[**Figure 1:** CCB layout. Use a source-bound geometry schematic, with the CD2 target, B arm at -38°, A arm at +71.5°, nominal 109 cm geometry parameter, eight B layers and four A layers. Label the drawing `SCHEMATIC / SOURCE-BOUND CONFIGURATION`, not metrology.]

The CCB beam study is useful for the HIBEAM/NNBAR range detector because proton-deuteron scattering produces charged particles with different stopping behaviour in the scintillator stack. It therefore provides a controlled way to test the relationship between deposited energy, depth and readout amplitude without requiring a full antineutron-annihilation final state.

### 2.2 A and B stacks

The analysis concentrates on the B stack. Eight physical B layers are represented in the simulation, but the selected data product uses four readout channels conventionally named B2, B4, B6 and B8. This is an important limitation for any calorimetric interpretation. Four longitudinal measurements can establish whether a particle stops early or penetrates the stack, but they do not sample a Bragg curve with the granularity of an eight- or ten-layer fully instrumented range detector.

The A arm is used mainly to define the coincidence-selected event class. Current Monte Carlo sample definitions use a first-layer charged-hit proxy for the trigger, because a source-bound model of the complete trigger-counter geometry and electronics response is not yet available. The paper therefore treats the Monte Carlo trigger as a proxy for the experimental selection rather than as a validated reproduction of the trigger hardware.

## 3. Scintillator stave and readout

### 3.1 Mechanical and optical design

The stave specification used for this paper follows the source-bound geometry and the hardware clarification in issue #796. Each stave is an extruded polystyrene scintillator with dimensions 50 cm in length, 5.18 cm in width and 2.0 cm along the nominal particle path. A TiO2-loaded reflective coating surrounds the outer scintillator faces. Two longitudinal 2.0 mm diameter holes are separated by 2.0 cm, and each contains a 1.8 mm diameter wavelength-shifting fibre.

The implemented single-stave optical model resolves the fibre into a Y-11-doped polystyrene core, PMMA inner cladding and fluorinated-PMMA outer cladding, with an air gap between the fibre and the 2.0 mm hole. The fibre radius is 0.90 mm and the simulated fibre protrudes beyond the scintillator at each end so that photons can reach external sensor surfaces. The refractive-index hierarchy in the model supports total internal reflection after wavelength shifting. Kuraray lists Y-11(200) as a green wavelength-shifting fibre with a representative emission peak near 476 nm, absorption peak near 430 nm and attenuation length greater than 3.5 m [6].

The B-stave design permits two fibres to be read from both ends, corresponding to four possible optical measurements per stave. The CCB test configuration did not exploit that redundancy. Only one fibre was read out, and it was read from one end. This single-channel configuration is critical for interpreting both the energy response and the achievable position correction. It removes the usual two-ended timing or charge asymmetry that could be used to infer the longitudinal hit position and cancel attenuation to first order.

[**Figure 2:** Stave cross-section and longitudinal view. Reuse `figures/geometry/fig_stave_crosssection_yz.png`, `fig_stave_longitudinal_xy.png` and, if needed, `fig_fibre_radial_stack.png`.]

### 3.2 SiPM readout

The source-bound optical model uses a Hamamatsu S13360-3050CS SiPM. The manufacturer specifies a 3×3 mm² photosensitive area, 50 µm pixel pitch and 3600 pixels, with a typical peak sensitivity wavelength of 450 nm [7]. The Y-11 emission band and the SiPM spectral response therefore overlap in the intended green-sensitive readout region.

Manufacturer specifications alone are not enough to determine the CCB photoelectron-to-ADC conversion. Photon detection efficiency depends on wavelength and operating conditions, while the measured waveform additionally depends on overvoltage, temperature, microcell recovery, optical crosstalk, afterpulsing, coupling geometry and the analogue transfer function. The current repository models several of these effects, but the audit classifies the operating point, recovery law, coupling footprint and charge-domain impulse normalisation as incompletely validated. Absolute light yield and absolute ADC calibration are therefore separated from the relative optical-response predictions below.

### 3.3 Digitisation and waveform products

The historical timing analysis uses eight channels with 18 samples per channel at a nominal 10 ns sample period. The located raw CCB ROOT files contain eight channels with 16 samples per channel. The two products have substantial event-level overlap and agree for several early-sample features, but a byte-level producer transformation from 8×16 to 8×18 has not been established. The precision-timing analysis must therefore name the waveform schema used for each result. This draft does not infer that the 18-sample product is simply the 16-sample product with two additional genuine trailing samples.

## 4. Simulation programmes

The analysis uses two related but distinct Geant4 applications.

First, the CCB event simulation models 190 MeV proton scattering on CD2, the two-arm telescope geometry and truth-level energy deposits in the stack. This application is used to study particle species, stopping depth, trigger-proxy selections and data-versus-MC topology. The source review found that the compact geometry is appropriate for first-order acceptance and stopping studies but does not yet represent the complete passive material budget. It also identified a historical angular-weighting risk: events were sampled uniformly in a scattering-angle variable and differential-cross-section information was carried as an event weight. Current downstream work therefore treats event weights and their effective sample size explicitly rather than assuming that all unweighted truth histograms are physical distributions.

Second, `geant4/single_stave/` models one scintillator element with optical photons. Geant4 generates scintillation photons, transports them across material boundaries, performs absorption and wavelength shifting in the Y-11 core, and propagates photons to SiPM end surfaces. These processes are part of the standard Geant4 optical-photon framework [4,5]. A separate SiPM/digitiser layer then models photon detection and waveform formation.

The two simulations answer different questions. The CCB geometry simulation predicts which particles reach each layer and how much energy they deposit. The single-stave simulation predicts the response conditional on a particle entering one stave. A valid end-to-end energy reconstruction requires these models to be composed without double-counting quenching, attenuation, PDE or electronics gain.

### 4.1 Model-status hierarchy

For this paper, simulation outputs are labelled in one of four ways:

1. **TRUTH-LEVEL MC:** Geant4 particle identities, trajectories and energy deposits before detector response.
2. **DIGITISED MC:** a simulated detector-response chain has been applied and the output can be reconstructed with the same observable definition as data.
3. **MODEL-DEPENDENT OPTICAL PREDICTION:** the output is numerically reproducible for a declared optical hypothesis but depends on uncalibrated material or sensor parameters.
4. **CALIBRATED PREDICTION:** reserved for an output whose model parameters have independent source-bound or measured constraints and whose closure has been demonstrated on held-out data.

At the time of this draft, the single-stave photoelectron yield belongs to category 3, not category 4.

## 5. Data taking and event selections

The current analysis convention divides the B-stack data into two trigger families. Sample I denotes the A-and-B coincidence family, while Sample II denotes the B-only family. Within those families, calibration and analysis runs are deliberately separated. The configuration used for the transfer studies defines Sample-I calibration runs 31-37 and 39-42, Sample-I analysis runs 44-57, Sample-II calibration run 64, and Sample-II analysis runs 58-63 and 65. These subsets should be quoted instead of treating all runs in a broad numeric interval as one statistically interchangeable sample.

The canonical selected-pulse table contains 640,737 B-stave pulses, although the upstream waveform lineage and exact raw-to-selected reconstruction remain gated. In the Sample-II analysis subset, the configuration records 125,096 selected pulses: 88,213 in B2, 21,229 in B4, 11,148 in B6 and 4,506 in B8. The Sample-I analysis is much more strongly concentrated in B2.

The pulse-selection threshold used in the historical reconstruction is an amplitude above 1000 ADC relative to a baseline estimated from the first four samples. Because the available data are trigger-selected and because the first B channel can saturate, pulse-count fractions are not direct particle efficiencies. They are properties of the selected analysis population.

### 5.1 Trigger-dependent stopping pattern

The most robust beam-data result is the contrast between the two trigger families. In Sample I, B2 carries the overwhelming majority of selected pulses and has a large high-amplitude population. The earlier data/MC report finds 241,422 B2 pulses in the Sample-I analysis population, a mean amplitude of 6090 ADC, and a 41.7% fraction at or above the historical saturation threshold of 7000 ADC. In Sample II, the B2 mean is 3663 ADC and the corresponding saturated fraction is 6.1%. Sample II also has a much larger relative population in B4, B6 and B8.

The CCB Geant4 truth sample gives the same qualitative stopping-versus-penetrating contrast under its trigger proxy. The coincidence-like selection enriches deuterons in the first B layer, while the B-only selection is more proton-rich and penetrates more deeply. Because the MC trigger is a proxy and the CCB passive material budget is not yet fully closed, this agreement is presently a topology-level result. It should not be converted into an absolute efficiency or cross-section claim.

[**Figure 3:** B-stack depth profile for Sample I and Sample II, data. Use a result-registry plot if available. Show normalized selected-pulse fraction per B2/B4/B6/B8 and include raw counts in the caption.]

[**Figure 4:** Corresponding MC first-layer/depth profile with truth species composition. Label event-weight treatment and `MC_TRIGGER_PROXY`.]

## 6. Inter-stave timing

### 6.1 Timing observable

For two staves i and j, the basic timing observable is

\[
\Delta t_{ij}=t_j-t_i-t_{\mathrm{TOF},ij},
\]

where the final term removes the expected flight-time difference for the chosen particle hypothesis and geometry. A detector-resolution inference additionally requires a model for the covariance of the two stave times. The common approximation

\[
\sigma_{\Delta t}^2=\sigma_i^2+\sigma_j^2
\]

is valid only when the two measurements are independent after common-mode effects and selection correlations are removed. With common trigger phase, waveform processing or shared event conditions, covariance terms must be retained.

### 6.2 Time pickoff and amplitude correction

Historical analyses used leading-edge, constant-fraction and template-like timing estimators. A simple leading-edge time is amplitude dependent because a larger pulse crosses a fixed threshold earlier. The project therefore studied empirical time-walk corrections, including forms proportional to 1/A. The correction should be fitted on a calibration population and validated on held-out runs by plotting the residual mean and width versus amplitude. An apparent reduction in the global width is not sufficient if a residual amplitude slope remains.

Constant-fraction timing is also not automatically free of bias in these data. The current P0 timing issue #1059 demonstrates that a global-maximum CFD can switch which physical pulse component it times when a waveform contains an earlier smaller component and a later larger component. Changing the CFD fraction can therefore change the measurand rather than merely tune the same timestamp. Production timing must either select a demonstrated single-pulse class or explicitly assign the pulse component to be timed.

### 6.3 What can be measured from the located raw data

The direct analysis of the located 8×16-sample raw files gives a B4-B6 residual central 68% width of approximately 38.0 ns after the applied time-of-flight subtraction for 5,207 events with valid CFD times. Restricting to a clean in-window-peak subset did not improve the result. The B6 peak positions are multi-modal and often lie at the waveform boundaries. With 10 ns sampling, these observations show that the residual is dominated by data-format and timing-window effects.

We therefore do **not** report 38 ns as the B-stave timing resolution. It is an upper-level diagnostic of an inadequate waveform representation for the desired precision measurement. We also do not promote the historical 0.54 ns combined timing number or the 0.68-0.75 ns single-stave values as beam-data performance. Those values belong to earlier toy/digitised analyses whose source product and estimator assumptions are not authorised by the current claim ledger.

The paper can nevertheless publish the timing methodology and the negative result: the present raw waveform product is insufficient for a defensible sub-nanosecond detector-resolution measurement. A final timing figure should show the raw B4-B6 residual, its sampling structure, and the dependence on amplitude and CFD fraction, with a caption that states this limitation explicitly.

[**Figure 5:** Real-data B4-B6 timing residual from the located 8×16 product. Use `reports/studies/data_side/VIS-TIM-DATA_sampling_limited.png` or regenerate from the result file. Caption: `FORMAT-LIMITED; NOT DETECTOR RESOLUTION`.]

[**Figure 6:** Timing correction closure. Produce only after PAPER-A04 closes: pre/post correction residual versus 1/A or amplitude, calibration and held-out runs separated, plus CFD component-stability diagnostic.]

## 7. Amplitude-based ΔE-E

### 7.1 Motivation and observable definition

A traditional ΔE-E telescope exploits the correlation between the energy loss in an upstream detector and the residual energy measured downstream. In a sufficiently segmented range stack, the sequence of energy deposits also samples the rise in dE/dx as a charged hadron slows toward the Bragg peak. The CCB B readout is too sparse for that full programme: only four channels are available in the analysed data, the first channel dominates Sample I, and saturation compresses part of its high-amplitude tail.

We therefore define an amplitude-space diagnostic rather than claim a calibrated ΔE-E particle-identification measurement. For the simplest B2-B4 view,

\[
E_{\mathrm{proxy}}=A_{B2},\qquad \Delta E_{\mathrm{proxy}}=A_{B4},
\]

with both axes in baseline-subtracted ADC amplitude. The names E and ΔE describe the telescope role of the channels, not a conversion to MeV. A MeV label is not permitted until the channel-dependent response model is calibrated and validated.

### 7.2 Real-data result

Using the composite event key, the real-data study finds 33,966 events containing selected B2 and B4 pulses. The Pearson correlation between B4 and B2 amplitudes is +0.221. The median B2 amplitude is 3385 ADC and the median B4 amplitude is 2963 ADC. The corresponding current MC study, expressed in truth-level energy-deposit units rather than ADC, gives a correlation of -0.533 with medians near 101.0 MeV and 24.1 MeV for the chosen layer observables.

The different correlation signs are a genuine topology discrepancy between the present data and MC observables, but the numerical medians must not be compared as if they share an energy scale. The data are strongly B2-selected, while the Geant4 geometry omits part of the real inter-stave/passive material budget. Both effects can change the population that reaches B4. A material-budget and response-model closure is therefore required before attributing the difference to a specific hadronic interaction model or particle species.

The limited segmentation still makes the plot useful. It demonstrates that the real detector is not simply reproducing the nominal MC depth correlation; it identifies where the response model must be improved; and it motivates the use of the full B2/B4/B6/B8 stopping-depth pattern rather than a single two-dimensional PID boundary.

[**Figure 7:** Data B4 amplitude versus B2 amplitude, logarithmic density or hexbin, with saturation region marked. Regenerate from the composite-key result.]

[**Figure 8:** MC layer-1 versus layer-0 truth EDep using the data-matched four-channel mapping. Keep axis units in MeV and place beside, not overlaid on, the ADC data panel unless a validated digitiser is applied.]

## 8. Monte Carlo prediction of light collection and transport

### 8.1 Stage-by-stage response

The single-stave optical simulation is designed to connect deposited energy to a detected signal through a sequence of physically distinct stages:

\[
E_{\mathrm{dep}}
\rightarrow N_{\gamma,\mathrm{scint}}
\rightarrow N_{\gamma,\mathrm{WLS\ abs}}
\rightarrow N_{\gamma,\mathrm{WLS\ emit}}
\rightarrow N_{\gamma,\mathrm{sensor}}
\rightarrow N_{\mathrm{avalanche}}
\rightarrow Q
\rightarrow A_{\mathrm{ADC}}.
\]

Keeping these stages separate is more informative than quoting one total efficiency. It allows the data to constrain attenuation or electronics gain without absorbing those effects into a fictitious scintillation yield.

### 8.2 Existing optical-MC result

A completed Geant4 campaign generated deposited-energy to detected-photoelectron predictions for proton and deuteron beams. Representative points from that campaign are:

| particle | kinetic energy [MeV] | mean deposited energy [MeV] | simulated detected PE | PE / MeV | relative width reported in campaign |
|---|---:|---:|---:|---:|---:|
| proton | 60 | 28.7 | 282 ± 25 | 9.85 | 8.9% |
| proton | 100 | 16.2 | 177 ± 17 | 10.9 | 9.3% |
| proton | 140 | 12.7 | 140 ± 29 | 11.0 | 20.8% |
| deuteron | 70 | 49.7 | 432 ± 62 | 8.7 | 14.5% |
| deuteron | 110 | 28.6 | 276 ± 48 | 9.6 | 17.2% |

These numbers are valuable because they quantify the response of the implemented one-fibre, one-end geometry and show a plausible order of magnitude for the signal. They are not yet an absolute prediction of the real CCB stave. The current Geant4 WLS configuration uses the default one-secondary re-emission behaviour unless a fluorescence-yield spectrum is supplied. The project ADR therefore sets `authorising_absolute_light_yield_claims=false` for this configuration. The fibre attenuation data are source-bound at the manufacturer level, but the actual installed fibre length, bending, end finish, coupling, reflector behaviour and PDE operating point still require campaign-specific evidence.

Accordingly, this paper should use the phrase **model-dependent detected-light response**, not **measured light-collection efficiency**. A publication-ready efficiency table should eventually report separate ratios such as

\[
\epsilon_{\mathrm{capture}} = \frac{N_{\gamma,\mathrm{WLS\ abs}}}{N_{\gamma,\mathrm{scint}}},
\quad
\epsilon_{\mathrm{transport}} = \frac{N_{\gamma,\mathrm{sensor}}}{N_{\gamma,\mathrm{WLS\ emit}}},
\quad
\epsilon_{\mathrm{PDE}} = \frac{N_{\mathrm{primary\ aval}}}{N_{\gamma,\mathrm{sensor}}},
\]

with position dependence and uncertainty bands. The total response then follows as a product only when the definitions are statistically and causally compatible.

[**Figure 9:** Single-stave Edep versus detected PE for proton and deuteron simulation. Show the five published campaign points and, preferably, the full event distributions. Caption must state `MODEL-DEPENDENT OPTICAL MC; ABSOLUTE LIGHT YIELD NOT AUTHORISED`.]

[**Figure 10:** Future stage-efficiency plot, photons generated → WLS absorbed → WLS emitted → sensor incident → primary avalanches. This is an open analysis atom.]

## 9. Energy reconstruction and resolution

### 9.1 What is reconstructable now

There are two different energy-reconstruction questions.

The first is the response of a **single stave**: can deposited energy in Geant4 be reconstructed from detected photoelectrons or from a digitised amplitude? The optical campaign already supplies the ingredients for a simulation-only resolution study. One can fit a calibration on a training subset, apply it without retuning to held-out energies and species, and report bias and a robust central-width estimator such as σ68 of

\[
r = \frac{E_{\mathrm{reco}}-E_{\mathrm{true}}}{E_{\mathrm{true}}}.
\]

The second is the **range stack**: can the incident charged-particle energy be reconstructed from the vector of B2/B4/B6/B8 signals and stopping depth? This requires the full material budget and a data-calibrated response per channel. The current data do not authorise that absolute reconstruction yet.

### 9.2 Simulation-only resolution

The relative widths reported by the existing optical campaign, approximately 9-21% for the selected p/d points, are useful first estimates of the stochastic spread in the implemented optical model. They are not yet a detector energy resolution because the reported quantity mixes finite optical statistics, event-to-event deposition variation and the particular campaign estimator. A publication-grade energy-resolution result must state whether the denominator is incident kinetic energy, Geant4 deposited energy, visible energy after quenching, or reconstructed photoelectron-equivalent energy.

The preferred analysis is therefore:

1. choose `E_true = Edep` for the single-stave optical calibration;
2. split simulated events by energy point into calibration and held-out validation samples before fitting;
3. fit a monotonic response `N_PE(Edep)` or a physically motivated saturating response if SiPM saturation is active;
4. reconstruct held-out `Edep` event by event;
5. report median bias, σ68, RMS, non-Gaussian tail fraction and coverage versus Edep;
6. repeat over proton/deuteron and hit position without species-dependent retuning unless the model explicitly requires it;
7. scan Birks/quenching, WLS properties, PDE, coupling, saturation and electronics nuisance parameters;
8. only after data closure, convert the resulting response into ADC units.

A heuristic project-level gain of about 92 ADC/MeV with a broad uncertainty envelope exists in the claim ledger, but it is not a precision stave calibration and should not be used to label the data axes in MeV. The historical 246 ADC/MeV conversion is obsolete for production interpretation.

[**Figure 11:** Simulation-only reconstructed Edep bias and resolution versus true Edep. Open atom PAPER-A09.]

[**Table 2:** Energy-resolution summary by energy/species/position, including estimator definition, number of events, calibration/validation split and nuisance set.]

## 10. Discussion

The CCB campaign already answers several of the questions that motivated the range-detector prototype. The B stack responds differently to the coincidence and B-only trigger families, and the difference is large enough to be visible without an absolute energy calibration. The coincidence family is concentrated at the entrance of the B stack and contains a much larger high-amplitude population, while the B-only family penetrates to later staves. This is the expected qualitative behaviour of a range telescope exposed to different p/d mixtures and energy distributions.

The study also shows why a simple two-axis ΔE-E plot should not carry the full particle-identification claim. Four readout depths, one-ended optical readout and first-channel saturation remove much of the information that a finely segmented telescope would provide. The most faithful observable is therefore the joint pattern of amplitudes, saturation flags and stopping depth. ΔE-E remains useful as a compact diagnostic and as a data-versus-MC stress test.

The timing result is more cautionary. The project contains sophisticated correction studies, but the located raw waveform data do not support a sub-nanosecond detector-resolution claim. The 10 ns sampling, boundary peaks and unresolved relationship between 16- and 18-sample products dominate the direct residual. In addition, multi-component waveforms can cause a global-maximum CFD to change which physical pulse it times as the fraction changes. These are not cosmetic analysis details; they define the measurand. A final detector timing number should therefore be added only after the waveform lineage and component-assignment criteria are closed on immutable data.

The optical simulation is similarly informative but not yet absolute. It predicts an order-10 PE/MeV response for the implemented one-fibre, one-end geometry and provides a starting point for energy reconstruction. Later audit work correctly prevents that number from being treated as a measured collection efficiency because the WLS fluorescence yield, coupling, PDE operating point and electronics charge scale are not all independently constrained. The right next step is not to discard the optical simulation, but to decompose the chain into measurable efficiencies and calibrate them with independent data.

These limitations strengthen rather than weaken the design lesson. A future range detector should retain full longitudinal segmentation where practical, instrument both ends or otherwise provide a position observable, avoid avoidable first-layer saturation, and acquire waveform windows whose timing reference and sampling are independently calibrated. The present test beam provides the evidence needed to prioritize those changes.

## 11. Conclusions

We have assembled the CCB test-beam data and Geant4 studies into a single evidence-bounded characterisation of the HIBEAM/NNBAR scintillator range-stave concept. The test-beam data show a strong trigger-dependent stopping pattern in the B stack. The coincidence-selected population is concentrated in the first readout layer and contains many high-amplitude pulses, while the B-only population penetrates more deeply. An amplitude-space B2-B4 ΔE-E diagnostic contains real information, but sparse segmentation and saturation limit its use as a stand-alone particle-identification observable. The measured data correlation of +0.221 differs from the present MC truth correlation of -0.533, motivating material-budget and response-model closure rather than an immediate absolute-energy interpretation.

The standalone optical Geant4 simulation predicts roughly 9-11 detected PE per deposited MeV at several proton and deuteron calibration points, with campaign relative widths of roughly 9-21%. These values are model-dependent because the absolute WLS re-emission, coupling and SiPM/electronics response are not yet fully calibrated. The located raw waveform product likewise does not yield an intrinsic timing resolution: its approximately 38 ns B4-B6 residual is sampling and window limited. Precision timing remains a defined follow-up analysis rather than a completed detector-performance claim.

The test beam has therefore achieved an important intermediate objective. It has demonstrated the stopping topology of the range stack in real data and supplied a reproducible path from Geant4 truth to optical and digitised response. Closing the remaining waveform, material-budget and optical-calibration atoms will turn that framework into quantitative detector timing and energy-resolution measurements.

## Methods and reproducibility notes

All final figures should be generated from tracked result files through the repository result-registry/figure tooling. No final figure should contain a number copied by hand from this manuscript. Every production plot must record the input artifact hashes, selection flow, event counts, code revision, configuration revision and uncertainty method.

For data/MC overlays, the same observable definition must be used on both sides. A Geant4 truth energy deposit must not be overlaid on an ADC amplitude axis and described as closure unless a response model is applied. For weighted Monte Carlo samples, report `sum(w)`, `sum(w^2)` and effective sample size, and propagate the weights through the plotted estimand.

Timing and energy calibrations must be fitted on calibration runs or training MC only and evaluated without retuning on held-out runs/energy points. Resampling should respect the event and run grouping that defines the statistical dependence.

## Evidence notes for authors

The following repository paths are the main evidence surfaces used in this draft:

- `paper/manuscript_outline.md`
- `docs/stave-geometry.md`
- `geant4/configs/krakow.geoconf`
- `reports/1781181864.166832.35d806b2__s21_geant4_source_review/REPORT.md`
- `configs/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.yaml`
- `reports/SAMPLE_I_II_DATA_MC_REPORT.md`
- `reports/studies/data_side/REPORT.md`
- `docs/claim_ledger.csv`
- `docs/adr/ADR-WLS-FLUORESCENCE-YIELD-UNVERIFIED.md`
- `docs/adr/ADR-SIPM-PHYSICS-BLOCKED-WAVEA-LANE01.md`
- `docs/stave_sim/STAVE_SIM_ENERGY_MODEL.md`
- issue #796 and issue #797 supervisor clarifications
- issue #1059 for the CFD component-selection ambiguity

Where an older narrative file conflicts with these evidence surfaces, the older value is not propagated into the manuscript.

## References

1. S.-C. Yiu et al., "Status of the Design of an Annihilation Detector to Observe Neutron-Antineutron Conversions at the European Spallation Source," *Symmetry* **14** (2022) 76. DOI: 10.3390/sym14010076.
2. K. Dunne et al., "The HIBEAM/NNBAR Calorimeter Prototype," *Journal of Physics: Conference Series* **2374** (2022) 012014. DOI: 10.1088/1742-6596/2374/1/012014. arXiv:2107.02147.
3. J. Barrow et al., "A Computing and Detector Simulation Framework for the HIBEAM/NNBAR Experimental Program at the ESS," *EPJ Web of Conferences* **251** (2021) 02062. DOI: 10.1051/epjconf/202125102062. arXiv:2106.15898.
4. S. Agostinelli et al., "Geant4: a simulation toolkit," *Nuclear Instruments and Methods in Physics Research A* **506** (2003) 250-303. DOI: 10.1016/S0168-9002(03)01368-8.
5. J. Allison et al., "Recent developments in Geant4," *Nuclear Instruments and Methods in Physics Research A* **835** (2016) 186-225. DOI: 10.1016/j.nima.2016.06.125.
6. Kuraray Co., Ltd., "Spectral and Characteristic Data: Wavelength Converting Fiber," product technical data for Y-11(200), accessed 2026-08-12. Manufacturer page reports a representative 476 nm emission peak, 430 nm absorption peak and >3.5 m attenuation length.
7. Hamamatsu Photonics K.K., "MPPC S13360-3050CS," product specifications, accessed 2026-08-12. Manufacturer page reports 3×3 mm² active area, 50 µm pixel pitch and 3600 pixels.

## Author action before submission

This manuscript is text-ready for collaboration editing, but it is **not yet numerically submission-ready**. The blocking analyses are enumerated in `chatgpt_todo/PAPER_OPEN_ATOMS_20260812.md`. The highest-priority items are: production timing on an authorising waveform product; a data-matched ΔE-E MC response after material-budget closure; stage-resolved optical efficiency with source-bound WLS/SiPM assumptions; and a held-out simulation energy-reconstruction resolution study. The final paper should be promoted into `paper/` only after those atoms update the claim ledger and the pre-submission review has no unresolved BLOCK items.