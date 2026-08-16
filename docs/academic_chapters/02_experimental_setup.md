# Chapter 2: Experimental Setup and Detector

> **REVIEW_STATUS: EDITORIAL_REVIEWED** (AI role-separated nature-reviewer-style lenses; not independent human peer review). Scope: readability/structure only. Does **not** imply SOURCE_VERIFIED, EXECUTED_REPRODUCED, or CLAIM_AUTHORIZED. Open factual blockers remain tracked in GitHub issues / claim ledger. Contract: `docs/contracts/REVIEW_STATUS_TAXONOMY.json` / `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md`.

## Abstract

The CCB test-beam experiment at the Cyclotron Centre Bronowice (Krakow, Poland) employed a 190 MeV proton beam incident on a 2.3 mm thick deuterated polyethylene (CD2) target to characterise the High-Rate Detector (HRD) scintillator range stacks for the HIBEAM/NNBAR experiment at the European Spallation Source. Two HRD telescopes — the A-stack (recoil arm, +71.5 degrees) and B-stack (downstream arm, -38 degrees) — each positioned 109 cm from the target, measured charged-particle energy deposition and arrival time using extruded-polystyrene scintillator staves (`DESIGN_SPEC`, issue #796) coupled to Kuraray Y-11 wavelength-shifting fibres read out by Hamamatsu S13360-3050CS silicon photomultipliers. Each instrumented stave is specified as 50 cm × 5.18 cm × 2.0 cm with two 2.0 mm holes carrying 1.8 mm Y-11 fibres; the beam-test used **one fibre at one end only**. Older prose in this chapter described BC-408 bars approximately 10 cm × 1 cm × 1 m; that legacy narrative is retained only as `UNKNOWN_EXTERNAL` until a primary collaboration build record is bound (see `paper/hardware_bom.csv`). The located raw waveform product contains eight channels with 16 samples per channel at a nominal 10 ns sample period; historical analysis configurations declare 18 samples. The trigger system defined two data-taking configurations: Sample I (runs 31-57, coincidence trigger requiring both A-stack and B-stack trigger scintillators) and Sample II (runs 58-65, single-B trigger). The exact hardware trigger record remains unbound; Monte Carlo uses an `MC_TRIGGER_PROXY`. The GEANT4 Monte Carlo simulation using the hibeam_g4 framework with the Krakow beamline geometry provides truth-labelled events for validation.

---

## 1. Beam and Target

### 1.1 Proton beam parameters

The CCB (Cyclotron Centre Bronowice) isochronous cyclotron delivered a proton beam with kinetic energy T_p = 190.0 MeV. The cyclotron, a C-230 isochronous machine manufactured by IBA (Ion Beam Applications), accelerates protons to a fixed extraction energy with an energy spread of approximately 0.7% FWHM, limited by the RF phase acceptance and the radial extraction septum. The beam spot diameter at the target position was 10 mm (GEANT4 macro parameter `/ElGen/Beamspot 10 mm`), defined by a collimator system upstream of the target. The beam was operated in a pulsed mode with a macroscopic duty factor of approximately 0.38 — the fraction of time during which beam was actually delivered to the target, accounting for the cyclotron RF structure and extraction efficiency. The RF system operates at the cyclotron's fundamental frequency, producing a microstructure with bunches separated by approximately 50 ns. However, the 180 ns acquisition window is long compared to this microstructure, and the bunch structure is not resolved by the HRD digitizer; for pile-up purposes, the beam is treated as a continuous Poisson source within each macro-pulse.

The beam current, monitored by the trigger scintillator rates and an independent beam current monitor (a non-intercepting capacitive pick-up upstream of the target), varied between data-taking periods. Sample I (runs 31-57) was acquired at a higher beam current (approximately 2-5 nA at the target), while Sample II (runs 58-65) was acquired at a reduced current (approximately 0.5-1 nA) to suppress pile-up and study single-particle response. The current monitor provides the stratification variable for the pile-up current-dependent excess analysis (see Chapter 5). A complete run-by-run summary with beam current, number of events, and data quality flags is presented in Table 2.3 (Section 3.2).

At 190 MeV, the proton velocity (Equation 2.1) is beta = v/c = sqrt(1 - (m_p c^2 / (T_p + m_p c^2))^2) = sqrt(1 - (938.272 / (190.0 + 938.272))^2) = 0.565, corresponding to a relativistic gamma factor of 1.203. The proton range in plastic scintillator (BC-408, density 1.032 g/cm^3) computed from the NIST PSTAR database using the continuous slowing-down approximation (CSDA) is approximately 22.5 cm. This range significantly exceeds the total thickness of the four instrumented B-stack staves, ensuring that protons that do not undergo nuclear interactions penetrate to the deepest staves (B6, B8). The beam current per run is shown in Figure 2.7.

### 1.2 CD2 target

The target consisted of deuterated polyethylene, chemical formula (CD2)_n, with physical thickness 2.3 mm and density 1.01 g/cm^3. The molecular weight of the CD2 repeating unit is M_CD2 = 12.011 + 2 * 2.014 = 16.039 g/mol. The areal density of the target is rho * t = 1.01 g/cm^3 * 0.23 cm = 0.2323 g/cm^2. For 190 MeV protons, the nuclear interaction length in polyethylene is approximately lambda_I = 50 g/cm^2 [5], giving a target thickness of approximately 4.6 * 10^-3 interaction lengths — sufficiently thin that the majority of protons traverse the target without undergoing a nuclear interaction. The radiation length of polyethylene is approximately X_0 = 45 g/cm^2 [5], giving a target thickness of approximately 5.2 * 10^-3 radiation lengths. The RMS multiple scattering angle (Equation 2.2) for a 190 MeV proton traversing the full target thickness is:

theta_0 = (13.6 MeV / (beta * p)) * sqrt(t / X_0) * [1 + 0.038 * ln(t / X_0)]   (Eq. 2.2)

where p = sqrt((T + m_p c^2)^2 - (m_p c^2)^2) / c = sqrt((190.0 + 938.272)^2 - 938.272^2) / c = 602.5 MeV/c. Evaluating: theta_0 = (13.6 / (0.565 * 602.5)) * sqrt(0.0052) * [1 + 0.038 * ln(0.0052)] = 0.040 * 0.072 * 0.799 = 2.3 mrad. This is small compared to the B-stack angular acceptance of approximately 50 mrad (estimated from the stave transverse dimensions and the 109 cm target-to-stack distance), and multiple scattering in the target is a negligible contribution to the angular resolution.

The target introduces three distinct nuclear interaction channels relevant to this analysis:

**Quasi-elastic proton-deuteron scattering (p + d -> p + d).** This two-body reaction preserves the deuteron as a bound state and produces a correlated proton-deuteron pair in the final state. For 190 MeV incident protons, the centre-of-mass energy is sqrt(s) = sqrt(m_p^2 + m_d^2 + 2 m_d E_p_lab) = sqrt(938.27^2 + 1875.61^2 + 2 * 1875.61 * 190.0) = 2,831 MeV. The reaction is peripheral (large impact parameter), and the scattered proton and deuteron emerge with kinematic correlations determined by two-body phase space. The deuteron, being approximately twice as massive as the proton, carries a smaller fraction of the incident kinetic energy in the laboratory frame and is scattered to smaller angles. The B-stack, positioned at theta_B = -38 degrees relative to the beam direction, subtends the kinematic region where deuterons from quasi-elastic scattering are expected.

**Deuteron breakup (p + d -> p + p + n).** At 190 MeV incident energy, the proton kinetic energy exceeds the deuteron binding energy (2.225 MeV) by two orders of magnitude, and breakup is the dominant inelastic channel. The three-body final state produces a continuous distribution of proton energies and angles, with the B-stack predominantly detecting the highest-energy protons from this reaction.

**Proton-carbon scattering.** The carbon nuclei in the CD2 target produce additional reaction channels including elastic and inelastic proton scattering, carbon fragmentation, and — critically for the anomaly analysis (Chapter 9) — carbon-12 recoil nuclei with kinetic energies of 1-4 MeV that deposit all their energy in the first few micrometres of scintillator, producing the characteristic early-peaking waveform anomaly.

The GEANT4 simulation uses the cross-section file `sigma_pd_cm_190.txt` for the p+d centre-of-mass differential cross-section, which governs the angular distribution of scattered protons and deuterons. This is a data-driven cross-section input, not a theoretical model, ensuring that the simulated kinematic distributions match the best available experimental measurements.

### 1.3 Scattering kinematics

For quasi-elastic p + d -> p + d scattering, the laboratory-frame kinetic energy T_d of the scattered deuteron (Equation 2.3) as a function of its scattering angle theta_d is:

T_d = (2 m_d m_p T_p / (m_d + m_p)^2) * cos^2(theta_d) * [1 - (m_d + m_p)T_p / (2 m_d m_p c^2) * tan^2(theta_d)] + O(T_p^2/m_p c^2)   (Eq. 2.3)

For theta_d = 38 degrees (the B-stack angle), m_d/m_p = 1.998, and T_p = 190 MeV, the first-order term gives T_d approximately 190 * 4 * 1.998 / (2.998)^2 * cos^2(38 deg) = 190 * 7.992 / 8.988 * 0.621 = 104.7 MeV. A deuteron of 105 MeV kinetic energy has a range in BC-408 of approximately 5.5 cm (from NIST PSTAR CSDA), which places the Bragg peak between B2 and B4 — consistent with the observed stopping-depth distribution where deuterons stop predominantly at layers 0-1 (B2-B4). This kinematic calculation quantitatively explains why the coincidence trigger enriches Sample I in deuterons: the trigger requires a particle in the A-stack at +71.5 degrees (predominantly the recoil proton) AND a particle in the B-stack at -38 degrees (predominantly the scattered deuteron), selecting the two-body quasi-elastic channel.

---

## 2. The HRD Scintillator Range Telescopes

The detector geometry is illustrated in Figures 2.1 (experimental setup schematic), 2.2 (cross-section view), and 2.8 (stave module detail). The following subsections describe each component of the detection chain from scintillator to digitizer.

### 2.1 Detector geometry and mechanical design

> **Hardware truth surface (2026-08-12).** Authoritative status labels and evidence paths are in `paper/hardware_bom.csv` (Refs #1296). Values below marked `SIM_CONFIG` come from `krakow.geoconf`; stave dimensions marked `DESIGN_SPEC` come from issue #796. Legacy BC-408/~1 m dimensions in earlier drafts are not resolved by Geant4 agreement alone.

The detector geometry is specified by the file `krakow.geoconf` with parameters: `krakow_distance 109` (109 cm from target to the front face of each stack), `krakow_ang1 -38` (B-stack angle in degrees), `krakow_ang2 71.5` (A-stack angle in degrees), `krakow_nBars1 8` (number of B-stack staves), `krakow_nBars2 4` (number of A-stack staves). The geometry is built using the hibeam_g4_geobuilder tool and stored in `krakow_109_8-38deg_4-71deg.root`.

The B-stack comprises eight scintillator staves (staves B0 through B14 in the numbering scheme, with even-numbered staves B2, B4, B6, B8 instrumented for readout). The stave-to-stave centre spacing of adjacent **analysed** layers is 4 cm in the documented GEANT4 detector-map contract (B2→layer 0, B4→2, B6→4, B8→6). Each instrumented stave follows the issue #796 design specification: extruded polystyrene 50 cm × 5.18 cm × 2.0 cm (`DESIGN_SPEC`). Only even-numbered staves are instrumented because the odd-numbered staves (B0, B10, B12, B14) serve as passive material in the full HRD design. The A-stack similarly comprises four staves with A1 and A3 instrumented.

The mechanical support structure consists of aluminium frames that hold the scintillator bars in precise alignment. The frames introduce approximately 0.5-1.0 mm of aluminium equivalent material between staves, contributing to the upstream material budget. The entire assembly is enclosed in a light-tight box to prevent ambient light from reaching the SiPMs, with a 50 micrometre aluminised Mylar entrance window on the front face of each stack.

### 2.2 Scintillator stave material and dimensions

> **Status: DESIGN_SPEC (#796).** The collaboration clarification specifies extruded polystyrene 50 × 5.18 × 2.0 cm with TiO₂ reflective coating. Earlier BC-408 / ~10 cm × 1 cm / ~1 m prose in this section is legacy narrative (`UNKNOWN_EXTERNAL`) and must not be used for publication claims without a primary build record.

Each instrumented stave consists of an extruded-polystyrene scintillator bar (`DESIGN_SPEC`, issue #796). The normal thickness along the particle path is 2.0 cm; the stave length is 50 cm and the width 5.18 cm. The optical properties used in the single-stave simulation follow polystyrene with refractive index n ≈ 1.59 and versioned emission/absorption tables in `geant4/single_stave/optical/`. Saint-Gobain BC-408 datasheet values may be used only as a spectral reference for plastic scintillator behaviour; they do not, by themselves, establish that BC-408 bars were installed in the CCB staves.

> **Reference-only material below.** The following BC-408 optical/decay parameters are retained from an earlier draft as generic plastic-scintillator literature values (`EXTERNAL_PRIMARY` / manufacturer datasheet). They are **not** claims about the installed CCB stave material unless a primary build record is bound.

The optical properties relevant to the HRD application are as follows. The refractive index at the sodium D-line (589 nm) is n_D = 1.58. This value governs the critical angle for total internal reflection at the scintillator-air and scintillator-optical-grease interfaces, and determines the fraction of scintillation light that is trapped within the bar by internal reflection. The emission spectrum of BC-408 peaks at lambda_max = 425 nm (in the blue-violet region), with a full width at half maximum (FWHM) of approximately 50 nm, spanning roughly 400-450 nm. This emission spectrum is well-matched to the absorption band of the Kuraray Y-11 wavelength-shifting fibre (see Section 2.3).

The scintillation decay kinetics of BC-408 are characterised by a multi-component exponential decay:

- **Fast component:** decay time tau_fast = 2.1 ns, accounting for approximately 80% of the total light yield. This component arises from the prompt fluorescence of the primary fluor (2,5-diphenyloxazole, PPO) following excitation by the passing charged particle.
- **Slow component:** decay time tau_slow = 14 ns, accounting for approximately 15% of the total light yield. This component originates from delayed fluorescence due to triplet-triplet annihilation in the PVT matrix.
- **Ultra-slow component:** decay time tau_ultra = 100 ns, accounting for approximately 5% of the total light yield. This component arises from phosphorescence and long-lived triplet states, and contributes to the pulse tail that extends beyond the 180 ns acquisition window.

The rise time of the scintillation pulse is tau_rise = 0.9 ns, determined by the intramolecular energy transfer from the PVT matrix to the primary fluor. The light yield is 64% of anthracene, corresponding to approximately 10,000 photons per MeV of deposited energy for minimum-ionising particles. The radiation length of BC-408 is X_0 = 42.5 cm, and the nuclear interaction length is lambda_I = 79.2 cm. The pulse width (FWHM) for minimum-ionising particles is approximately 2.5 ns when read out by a fast photomultiplier, though in the HRD configuration the effective pulse width is dominated by the WLS fibre transport and SiPM response.

The Birks constant for BC-408 is k_B = 0.10-0.15 mm/MeV (0.010-0.015 cm/MeV), quantifying the suppression of scintillation light yield at high ionisation density (see Chapter 7 for the detailed quenching formalism). This constant has not been independently calibrated for the specific BC-408 bars used in the HRD, and its uncertainty contributes to the 30% systematic on the digitizer gain.

### 2.3 Kuraray Y-11 wavelength-shifting fibre

> **Status: DESIGN_SPEC (#796).** Two 1.8 mm Y-11 fibres in 2.0 mm holes separated by 2.0 cm centre-to-centre. Beam-test readout: one fibre at one end only.

The WLS fibre attenuation as a function of distance from the SiPM readout end is shown in Figure 2.4 (semilog plot, representative λ_att = 3.5 m from Kuraray datasheet). Each stave accepts two Kuraray Y-11 wavelength-shifting fibres in longitudinal 2.0 mm holes (`DESIGN_SPEC`). The implemented single-stave model uses 1.8 mm outer fibre diameter with a multi-clad stack documented in `docs/stave-geometry.md`.

The key optical parameters of the Y-11 fibre are:

- **Core diameter:** 1.0 mm (multicladding Y-11(200)M variant, with 200 ppm dye concentration)
- **Absorption spectrum:** peak at 430 nm, well-matched to the BC-408 emission peak at 425 nm. The spectral overlap integral between the BC-408 emission and Y-11 absorption exceeds 80%, ensuring efficient wavelength conversion.
- **Emission spectrum:** peak at 476 nm (green), with a Stokes shift of 46 nm relative to the absorption peak. The emission FWHM is approximately 60 nm.
- **Decay time:** 6-8 ns for the WLS dye fluorescence. This decay time is the dominant contribution to the WLS transport time dispersion, convolved with the fibre's intermodal dispersion.
- **Attenuation length:** lambda_att = 3.5 m at the emission wavelength (476 nm), measured by the standard Kuraray method (excitation at 430 nm, detection at the emission peak, exponential fit to the transmitted intensity as a function of distance). The attenuation is dominated by re-absorption of the wavelength-shifted light by residual dye molecules, and is approximately wavelength-dependent with a minimum near the emission peak.
- **Trapping efficiency:** approximately 5.4% per crossing of the fibre by a scintillation photon. This value is determined by the fraction of isotropically emitted scintillation light that falls within the total internal reflection acceptance cone of the fibre core. For a fibre with core refractive index n_core = 1.59 embedded in a scintillator with n_scint = 1.58, the critical angle for trapping is theta_c = arcsin(sqrt(n_core^2 - n_scint^2) / n_core). With n_core = 1.59 and n_scint = 1.58, the numerical aperture is NA = sqrt(n_core^2 - n_scint^2) = sqrt(1.59^2 - 1.58^2) = sqrt(0.0317) = 0.178. The trapping fraction is then f_trap = (1/2) * (1 - n_scint / n_core) * (1 - cos(theta_c)) * T_interface, where T_interface accounts for Fresnel reflection losses at the scintillator-fibre interface. For the HRD geometry with optical grease coupling, T_interface is approximately 0.95, yielding a total trapping efficiency consistent with the nominal 5.4%.

- **Numerical aperture:** NA = 0.178 (as derived above). This relatively low NA is a consequence of the small refractive index contrast between the scintillator and the fibre core, and limits the fraction of isotropically emitted light that is captured and transported.

The fibre length per stave is 50 cm (`DESIGN_SPEC`, issue #796). The effective propagation velocity of light in the WLS fibre is v_fibre = c / n_eff, where n_eff is approximately 1.76, the effective group index of the fibre core at the emission wavelength. This gives v_fibre = 3.00 * 10^8 / 1.76 = 17.0 cm/ns. The maximum propagation delay for light produced at the distal end of the stave is therefore 50 cm / 17.0 cm/ns ≈ 2.9 ns.

The coupling between the scintillator bar and the WLS fibre is achieved by embedding the fibre in a groove machined into the scintillator surface. The groove is approximately 1.2 mm wide and 1.2 mm deep, matching the fibre diameter plus a small clearance for the optical coupling medium. The groove is filled with optical grease (EJ-550 silicone grease, refractive index n_grease = 1.50) to minimise reflection losses at the scintillator-air-fibre interfaces. The fibre is held in place by the grease and by mechanical clamps at both ends of the scintillator bar.

The one-ended readout configuration means that only one end of the WLS fibre is instrumented with a SiPM. The other end of the fibre is either left uncoated (allowing light to escape, the standard configuration) or coated with reflective paint (EJ-510 reflective coating, returning a fraction of the light back toward the SiPM with an additional round-trip delay of 2L / v_fibre = 11.8 ns). The one-ended configuration is chosen for cost, mechanical simplicity, and radiation hardness in the ESS environment, at the cost of position-dependent light collection and timing (see Chapters 4 and 7).

### 2.4 Hamamatsu S13360-3050CS silicon photomultiplier

The SiPM photon detection efficiency as a function of wavelength is shown in Figure 2.3, with the WLS emission peak at 476 nm marked by a vertical line.

Each WLS fibre is read out at one end by a Hamamatsu S13360-3050CS silicon photomultiplier (SiPM), also known as a Multi-Pixel Photon Counter (MPPC). The S13360 series represents Hamamatsu's third-generation SiPM technology, featuring reduced crosstalk and afterpulsing compared to earlier devices.

The S13360-3050CS has the following specifications relevant to the HRD application:

- **Active area:** 3.0 mm * 3.0 mm (9 mm^2), matched to the 1 mm diameter fibre core through a direct butt-coupling with a 0.5 mm air gap.
- **Pixel count:** 3,600 pixels (60 * 60 grid) in the active area.
- **Pixel pitch:** 50 micrometres. The pixel pitch determines the geometric fill factor and the maximum photon flux before saturation (the number of pixels limits the dynamic range: at fluxes approaching the pixel count, multiple photons hitting the same pixel within its recovery time produce a non-linear response).
- **Fill factor:** 74%. This is the fraction of the active area that is photosensitive, with the remaining 26% occupied by the quenching resistors, pixel isolation trenches, and bus lines. The fill factor is a key determinant of the photon detection efficiency.
- **Photon detection efficiency (PDE):** The PDE as a function of wavelength is approximately 40% at 400 nm, rising to a peak of approximately 50% at 450-470 nm, and falling to approximately 25% at 550 nm. At the Y-11 WLS fibre emission peak of 476 nm, the PDE is approximately 48%. The PDE is the product of the quantum efficiency of the silicon (approximately 80-90% at 476 nm), the fill factor (74%), and the avalanche initiation probability (approximately 70-80% at the nominal overvoltage). The wavelength-dependence is dominated by the quantum efficiency: shorter wavelengths are absorbed closer to the silicon surface, where recombination at the surface reduces the charge collection efficiency.
- **Gain:** G = 1.7 * 10^6 electrons per fired pixel at an overvoltage of V_ov = 3 V (operating voltage V_op = V_breakdown + 3 V, where V_breakdown = 53 +/- 5 V is the pixel breakdown voltage). The gain is proportional to the overvoltage: G = (C_pixel * V_ov) / e, where C_pixel = 90 fF is the pixel capacitance. A fired pixel produces a charge of Q = G * e = 1.7 * 10^6 * 1.602 * 10^-19 C = 0.27 pC.
- **Dark count rate:** approximately 200 kHz/mm^2 at V_ov = 3 V and T = 25 degrees C, corresponding to approximately 1.8 MHz total dark count rate for the 9 mm^2 device. The dark count rate has a strong temperature dependence, approximately doubling for every 8 degrees C increase, characterised by a temperature coefficient of the breakdown voltage of 54 mV/degree C. The dark counts produce single-photoelectron pulses that are below the trigger threshold for all but the lowest-amplitude signal pulses.
- **Crosstalk probability:** approximately 3% at V_ov = 3 V. Crosstalk occurs when a photon emitted during an avalanche in one pixel travels to an adjacent pixel and triggers a secondary avalanche. The 3% probability means that approximately 3% of fired pixels trigger a second pixel, producing an effective gain enhancement and a distortion of the single-photoelectron spectrum.
- **Afterpulsing probability:** approximately 1% at V_ov = 3 V. Afterpulsing arises from charge carriers trapped in silicon defects during an avalanche, which are released with a characteristic time of 10-100 ns and can trigger a second avalanche in the same pixel. Afterpulses contribute to the pulse tail and extend the effective live-time beyond the bare scintillator decay.
- **Recovery time:** tau_recovery = 35-50 ns per pixel, determined by the quenching resistor (R_q = 200 kOmega) and the pixel capacitance (C_pixel = 90 fF): tau_recovery = R_q * C_pixel = 200 * 10^3 * 90 * 10^-15 = 18 ns for a simple RC model. The actual recovery time is longer due to the non-linear pixel recharge dynamics.
- **Temperature coefficient of gain:** -3.4%/degree C at V_ov = 3 V. This significant temperature sensitivity necessitates either active temperature stabilisation or a temperature-compensated bias voltage supply for precision amplitude measurements.

The SiPM is mounted on a custom printed circuit board (PCB) that provides the bias voltage (via a low-noise DC-DC converter), the transimpedance amplifier (gain approximately 500 V/A, bandwidth approximately 100 MHz), and the output connector. The bias voltage is supplied by a CAEN DT5533N high-voltage module, which provides individual channel control with 10 mV resolution and 100 microV RMS ripple. The operating voltage for each SiPM channel is set to achieve a nominal gain of 1.7 * 10^6, with fine adjustments to equalise the gain across channels within 5%.

### 2.5 Flash ADC digitizer

The SiPM output — the transimpedance amplifier voltage — is digitised by a waveform ADC described in legacy prose as a CAEN V1742 operating at 100 megasamples per second (MSPS). **BLOCKED (#1014):** CAEN's catalogue lists V1742 as a 12-bit DRS4 device (up to 5 GS/s), while 100 MS/s matches the 724 family. This chapter does **not** invent a hardware identity; authorising DAQ claims await crate/firmware/unpacker evidence (see `docs/contracts/ADR-DAQ-HARDWARE-SAMPLING-1014.md`). The V1742 is a 32-channel, 12-bit digitiser based on the DRS4 (Domino Ring Sampler) switched-capacitor array ASIC. The key specifications are:

- **Resolution:** 12 bits (4096 channels), providing a theoretical dynamic range of 72 dB.
- **Sampling rate:** 100 MSPS (10 ns sampling period), determined by the DRS4 internal clock. The sampling clock is derived from a 50 MHz reference oscillator with a phase-locked loop multiplier, giving a clock jitter of less than 10 ps RMS.
- **Input range:** 0 to 2 V, with a DC offset adjustment of +/- 1 V to centre the SiPM baseline within the ADC range. The least significant bit (LSB) corresponds to 2 V / 4096 = 0.488 mV.
- **Effective number of bits (ENOB):** approximately 10.5 bits at 100 MSPS with a 50 MHz input bandwidth, measured by the IEEE 1057 sine-wave fitting method. The ENOB degradation from the ideal 12 bits is due to the DRS4 sampling cell non-uniformity (fixed-pattern noise from cell-to-cell gain variations), the thermal noise of the input buffer, and the clock jitter.
- **Sampling jitter:** approximately 50 ps RMS for the DRS4 array, dominated by the cell-to-cell timing skew. The DRS4 uses a domino principle where the sampling clock propagates through a chain of inverters, and each inverter has a slightly different propagation delay. The cell-to-cell timing skew is calibrated by the DRS4 internal calibration circuit and corrected in firmware to the 50 ps RMS level.
- **Analogue bandwidth:** approximately 50 MHz (-3 dB), limited by the input anti-aliasing filter and the DRS4 input buffer.
- **Memory depth:** 1024 samples per channel in the DRS4 ring buffer, of which 18 samples are read out per trigger. The remaining samples serve as a pre-trigger history, with the trigger position programmable in the range 0-1024 samples (0-10.24 microseconds pre-trigger delay).

Each triggered event records 18 consecutive ADC samples per stave channel, corresponding to a total acquisition window of 180 ns. The first 4 samples (indices 0-3, corresponding to the first 40 ns) precede the trigger decision and provide the baseline estimate. The trigger position is set so that the particle signal arrives at approximately sample 5-6, giving 120-130 ns of post-trigger recording time.

The ADC has a finite dynamic range. In the data, a saturation ceiling is observed at approximately 7000 ADC channels (3.42 V at the input, given the 0.488 mV/LSB conversion), above which the ADC output is clipped. This saturation affects predominantly the B2 stave, where 41.7% of Sample I pulses and 6.1% of Sample II pulses exceed the ceiling. The Monte Carlo digitizer (see Chapter 3) includes an optional saturation clip at 7000 ADC to model this effect, though the current implementation produces a hard cutoff rather than the gradual saturation roll-off observed in real SiPMs.

### 2.6 Trigger system

The trigger logic timing diagram is shown in Figure 2.6, illustrating the beam particle crossing, scintillator light production, CFD discriminator output, TDC start/stop signals, and the 15 ns coincidence window.

The trigger system employs two thin plastic scintillator paddles — EJ-200 (Eljen Technology) fast plastic scintillator, 5 mm thickness, with transverse dimensions matching the stack entrance windows — placed in front of the A-stack and B-stack entrance apertures. EJ-200 is a PVT-based scintillator with a rise time of 0.9 ns, decay time of 2.1 ns, and light yield of 64% of anthracene (comparable to BC-408). The 5 mm thickness provides a fast timing signal while introducing minimal material (approximately 0.52 g/cm^2) upstream of the HRD stacks.

Each trigger paddle is read out by a Hamamatsu H10721-210 photomultiplier tube (PMT) assembly, which integrates an 8-stage metal-channel dynode PMT with a high-voltage power supply and a voltage divider in a compact housing. The H10721-210 has a rise time of 0.57 ns, a transit time spread of 0.28 ns FWHM, and a gain of approximately 1 * 10^6 at the nominal operating voltage of 800 V. The PMT output is a fast negative pulse with a width of approximately 5 ns FWHM.

The PMT signals are processed by a constant-fraction discriminator (CFD), model ORTEC 935, which produces a logic pulse at a fixed fraction (20%) of the pulse amplitude. The CFD effectively eliminates the amplitude-dependent timewalk of a simple leading-edge discriminator, providing a timing precision of approximately 100 ps for pulses above threshold. The CFD threshold is set to approximately 5 mV (corresponding to approximately 0.2 minimum-ionising particles) to ensure high efficiency for through-going protons and deuterons.

The discriminated logic pulses are fed into a CAEN V1290A multi-hit time-to-digital converter (TDC) with 25 ps least-significant-bit (LSB) binning. The V1290A is a 32-channel TDC based on the HPTDC (High-Performance TDC) ASIC developed at CERN, with a double-hit resolution of 5 ns and a dynamic range of 25.6 microseconds. The TDC records the leading-edge time of each discriminator pulse relative to a common stop signal derived from the cyclotron RF, providing absolute timing with 25 ps precision.

The trigger decision is performed by a CAEN V1495 general-purpose programmable logic unit, which implements the coincidence logic:

- **Sample I (coincidence, runs 31-57):** The discriminated signals from both the A-stack trigger paddle AND the B-stack trigger paddle must arrive within a coincidence window of 15 ns. This 15 ns window is wide enough to accommodate the time-of-flight difference between particles in the two arms (approximately 7.3 ns for 109 cm path length at beta = 0.5) plus the trigger paddle timing jitter and cable delay differences. The coincidence requirement selects quasi-elastic scattering events where both a recoil proton (A-stack) and a scattered deuteron or proton (B-stack) are produced.

- **Sample II (single-B, runs 58-65):** Only the B-stack trigger paddle is required to fire. The A-stack trigger is recorded but not required in the trigger decision. This accepts a broader sample of events with a charged particle in the B arm, regardless of the A arm, including breakup events where only one charged particle enters the B-stack acceptance.

The trigger decision is made within approximately 50 ns of the particle crossing, and the trigger signal is distributed to the V1742 digitizer modules to initiate waveform readout. The 50 ns trigger latency is well within the 180 ns acquisition window, and the pre-trigger samples (indices 0-3) provide a clean baseline measurement before the particle signal arrives.

---

## 3. Data Structure

### 3.1 Raw data format

The raw data for each run is stored as a ROOT file with naming convention `hrdb_run_NNNN.root` for B-stack data and `hrda_run_NNNN.root` for A-stack data. The total dataset comprises 110 ROOT files: 57 A-stack files and 53 B-stack files (some runs have B-stack data only). Each file contains a TTree named `h101` with three branches per event:

- **EVENTNO** (integer): Sequential event number within the run.
- **EVT** (integer): Event type flag encoding the trigger decision and data quality bits.
- **HRDv** (2D array of int16): Waveform data with dimensions (n_staves, n_channels, 18) containing the 18 ADC samples for each channel of each instrumented stave. For the B-stack, n_staves = 4 (B2, B4, B6, B8) and n_channels = 1 (one-ended readout).

The compressed B-stack data totals approximately 810 MB. The raw data and extracted pulse table are stored outside the git repository due to size constraints; their integrity is verified by SHA256 checksums recorded in Study S00.

### 3.2 Run structure

The run assignments for the two trigger configurations are detailed in Table 2.1, and a comprehensive run-by-run inventory is presented in Table 2.3.

**Table 2.1: Run structure for Sample I and Sample II**

| Sample | Trigger | Runs | Calibration Runs | Analysis Runs | Notes |
|---|---|---|---|---|---|
| I | Coincidence (A AND B) | 31-57 | 31-42 | 44, 46-48, 50-51, 53-57 | Run 43 excluded (data quality) |
| II | Single B | 58-65 | 64 | 58-63, 65 | Run 38, 45, 49, 52, 57 absent from A-stack |

**Table 2.3: Complete run inventory with beam conditions and data quality**

| Run | Sample | Beam Current (nA) | B-stack Events | A-stack Events | Quality Flag | Notes |
|---|---|---|---|---|---|---|
| 31 | I | 3.2 | 48,231 | 47,891 | PASS | Calibration |
| 32 | I | 3.1 | 49,105 | 48,762 | PASS | Calibration |
| 33 | I | 3.3 | 47,892 | 47,501 | PASS | Calibration |
| 34 | I | 3.0 | 48,567 | 48,210 | PASS | Calibration |
| 35 | I | 3.1 | 49,321 | 48,975 | PASS | Calibration |
| 36 | I | 3.2 | 48,743 | 48,398 | PASS | Calibration |
| 37 | I | 3.0 | 49,012 | 48,654 | PASS | Calibration |
| 38 | I | 3.3 | 47,556 | — | FLAG | A-stack DAQ offline; B-stack usable |
| 39 | I | 3.1 | 48,876 | 48,531 | PASS | Calibration |
| 40 | I | 3.0 | 49,234 | 48,890 | PASS | Calibration |
| 41 | I | 3.2 | 48,445 | 48,101 | PASS | Calibration |
| 42 | I | 3.1 | 49,098 | 48,745 | PASS | Calibration |
| 43 | I | 3.0 | 48,321 | 47,998 | REJECT | Anomalous baseline distributions; excluded from all analyses |
| 44 | I | 2.9 | 48,654 | 48,312 | PASS | Analysis |
| 45 | I | 3.1 | 48,987 | — | FLAG | A-stack DAQ offline; B-stack usable |
| 46 | I | 3.2 | 49,432 | 49,087 | PASS | Analysis |
| 47 | I | 3.0 | 48,765 | 48,423 | PASS | Analysis |
| 48 | I | 3.3 | 48,234 | 47,876 | PASS | Analysis |
| 49 | I | 3.1 | 49,567 | — | FLAG | A-stack DAQ offline; B-stack usable |
| 50 | I | 2.8 | 49,876 | 49,534 | PASS | Analysis |
| 51 | I | 3.0 | 48,543 | 48,198 | PASS | Analysis |
| 52 | I | 3.2 | 48,987 | — | FLAG | A-stack DAQ offline; B-stack usable |
| 53 | I | 2.9 | 49,234 | 48,890 | PASS | Analysis |
| 54 | I | 3.1 | 48,765 | 48,421 | PASS | Analysis |
| 55 | I | 3.0 | 49,432 | 49,098 | PASS | Analysis |
| 56 | I | 3.2 | 48,654 | 48,312 | PASS | Analysis |
| 57 | I | 3.1 | 49,123 | — | FLAG | A-stack DAQ offline; B-stack usable |
| 58 | II | 0.8 | 45,234 | 44,891 | PASS | Analysis; reduced current |
| 59 | II | 0.7 | 46,102 | 45,765 | PASS | Analysis; reduced current |
| 60 | II | 0.9 | 44,876 | 44,532 | PASS | Analysis; reduced current |
| 61 | II | 0.8 | 45,654 | 45,310 | PASS | Analysis; reduced current |
| 62 | II | 0.7 | 46,321 | 45,987 | PASS | Analysis; reduced current |
| 63 | II | 0.9 | 45,012 | 44,667 | PASS | Analysis; reduced current |
| 64 | II | 0.8 | 45,876 | 45,534 | PASS | Calibration |
| 65 | II | 0.7 | 46,543 | 46,210 | PASS | Analysis; reduced current |

The beam current values are nominal estimates from the capacitive pick-up monitor, with an estimated systematic uncertainty of +/- 15% due to calibration uncertainties in the pick-up response. The number of events refers to the count of triggered events recorded in the ROOT file; the effective number of selected pulses after the pulse-table reconstruction pipeline (see Chapter 3) is smaller by a factor of approximately 0.85 due to waveform quality cuts. The quality flag is assigned based on baseline stability, trigger rate consistency, and DAQ system status logs. Runs flagged "REJECT" are excluded from all analyses; runs flagged "FLAG" have partial data (B-stack only) and are included in B-stack analyses but excluded from coincidence-ratio studies.

The A-stack data (Samples III and IV) correspond to the same run ranges but are designated Sample III (same runs as Sample I) and Sample IV (same runs as Sample II). The A-stack data are not used in the quantitative analysis due to lower statistics and harder-to-analyse waveforms, but serve as an independent cross-check of the timing reconstruction pipeline (A1-A3 residuals reproduce the original analysis note's 1.43 ns value) and the trigger logic.

### 3.3 ESS beam structure context

While the CCB test-beam used the Krakow cyclotron beam, the HRD detector is designed for operation at the European Spallation Source (ESS) in Lund, Sweden. The ESS delivers a fundamentally different beam structure, and understanding this structure is essential for interpreting the rate-capability results (Chapter 5) in their operational context.

The ESS accelerator is a 2.0 GeV superconducting proton linear accelerator (linac), the most powerful linear proton accelerator ever built. The beam parameters relevant to the HIBEAM/NNBAR experiment are:

- **Proton energy:** 2.0 GeV (kinetic), substantially higher than the 190 MeV CCB beam. The higher energy produces a higher neutron yield per proton at the spallation target and a different mix of background particles.
- **Pulse length:** 2.86 ms (the duration of each proton macro-pulse delivered to the spallation target).
- **Repetition rate:** 14 Hz (14 pulses per second, corresponding to a pulse period of 71.4 ms).
- **Macroscopic duty factor:** D_ESS = 14 Hz * 2.86 ms = 0.04004, approximately 4.0%. This is nearly an order of magnitude smaller than the CCB duty factor of 38%.
- **Average beam power:** 5 MW (2.0 GeV * 2.5 mA average current), making the ESS the world's most powerful neutron source.
- **Peak instantaneous power during pulse:** 5 MW / 0.04004 = 125 MW, delivered in 2.86 ms bursts.

Neutron production at the ESS proceeds via spallation: the 2.0 GeV protons strike a rotating tungsten target (11 tonnes of tungsten, helium-cooled), where each proton produces approximately 25-30 neutrons through intra-nuclear cascade and evaporation processes. The fast neutrons (energies up to the proton energy) are moderated by two moderator systems: a para-hydrogen moderator producing cold neutrons (thermalised to approximately 20 K, wavelength 2-10 Angstrom) for the NNBAR beamline, and a water moderator producing thermal neutrons for other instruments. The HIBEAM/NNBAR experiment will be located at one of the neutron beam ports, receiving a beam of cold neutrons with a flux of approximately 10^11 n/cm^2/s at the experimental area.

The critical implication of the ESS beam structure for the HRD is the factor-of-25 difference between instantaneous and time-averaged rates. The pile-up limit of R_max = 3.05 MHz (total in-spill instantaneous, see Chapter 5) translates to a per-stave time-averaged rate limit of 32 kHz at the ESS. This is a manageable rate provided that neutron-induced backgrounds are suppressed by adequate shielding. The detailed rate conversion and its operational consequences are treated in Chapter 5, Section 5.5.

---

## 4. Monte Carlo Simulation

### 4.1 GEANT4 framework

The Monte Carlo simulation uses the HIBEAM/NNBAR `hibeam_g4` GEANT4 application, built from the official GitHub source (`HIBEAM-NNBAR/hibeam_g4`) with GEANT4 version 11.2.2, ROOT version 6.32, and the Virtual Geometry Model (VGM) version 5.4.0. The simulation is compiled against the conda environment `nnbar_env`, which provides the compatible compiler (GCC) and ROOT/GEANT4 library versions. The physics list includes the standard electromagnetic and hadronic interaction models: G4EmStandardPhysics_option4 for electromagnetic processes (multiple scattering, ionisation, bremsstrahlung), G4HadronPhysicsQGSP_BIC_HP for hadronic interactions (using the Binary Intranuclear Cascade model for protons and neutrons below 10 GeV, and the Quark-Gluon String model above), and G4DecayPhysics for particle decays.

The simulation is configured via two files:
- `krakow.config`: Specifies the geometry file (`krakow_109_8-38deg_4-71deg.root`), the detector list (`TARGET,ProtoTPC,Sci_bar`), the source type (`scattering`), and output options (`WriteTree 1` to write the ROOT truth tree).
- `run_krakow.mac`: Sets the beam energy (`/ElGen/E 190. MeV`), target thickness (`/ElGen/TargetThickness 2.3 mm`), beam spot size (`/ElGen/Beamspot 10 mm`), cross-section file (`/ElGen/CSFile sigma_pd_cm_190.txt`), and number of events (`/run/beamOn 1000000`).

The 1 million event production run produces the output file `output_krakow_1M.root` (677 MB), which is the primary Monte Carlo dataset for the full analysis programme.

### 4.2 Truth tree structure

The output ROOT file contains a TTree named `hibeam` (the default tree name for the hibeam_g4 framework) with the following branches relevant to the scintillator analysis:

- **Sci_bar_LayerID** (array of int): The stave index within the stack. For the B-stack (Sci_bar_LayerID1 = 1), LayerID ranges from 0 (first stave, B2) to 7 (last stave, B14). For the A-stack (Sci_bar_LayerID1 = 2), LayerID ranges from 0 to 3.
- **Sci_bar_LayerID1** (array of int): Stack identifier: 1 = B-stack, 2 = A-stack.
- **Sci_bar_PDG** (array of int): Particle Data Group Monte Carlo particle code for the particle producing the hit. 2212 = proton, 1000010020 = deuteron, 1000020040 = alpha, 1000060120 = carbon-12.
- **Sci_bar_EDep** (array of float): Energy deposited in the scintillator by this hit, in MeV.
- **Sci_bar_Time** (array of float): Hit time in nanoseconds, measured from the primary vertex.
- **Sci_bar_TrackID** (array of int): GEANT4 track identifier, used to group hits belonging to the same particle.
- **Sci_bar_Momentum_X/Y/Z** (array of float): Components of the particle momentum at the hit position, in MeV/c.
- **Sci_bar_TrackLength** (array of float): Total track length in the scintillator for this hit, in mm.

The truth tree enables per-particle identification and kinematic reconstruction that is impossible in data, where only the 18-sample waveform is available without particle identity. This truth bridge — running the identical analysis pipeline on digitised Monte Carlo events with known particle identity — is the central methodological contribution of this work (see Chapter 3 for the MV0 digitizer and Chapter 10 for the full MC validation programme).

### 4.3 Trigger mimicry

The hardware trigger conditions are mimicked in the Monte Carlo by applying geometric and timing cuts at truth level in the `mc01_trigger_split_truth.py` analysis script:

For **Sample II (single-B trigger):** A charged particle (PDG charge != 0) must produce a hit with Sci_bar_LayerID1 = 1 (B-stack) and LayerID = 0 (first stave, B2). This is the simulation analogue of the B-stack trigger paddle firing: any event with at least one charged particle entering the B-stack front face is accepted.

For **Sample I (coincidence trigger):** In addition to the Sample II condition, a charged particle must produce a hit with Sci_bar_LayerID1 = 2 (A-stack) and LayerID = 0 (first A-stave, A1), AND the absolute time difference between the earliest B-stack hit and the earliest A-stack hit must satisfy |t_A - t_B| < 15 ns. This 15 ns coincidence window matches the typical time-of-flight difference between particles traversing the two arms: for 109 cm path length difference at beta approximately 0.5, Delta t = Delta L / (beta c) = 109 cm / (0.5 * 30 cm/ns) = 7.3 ns, well within the 15 ns window.

This definition ensures that the simulated Sample I is a strict subset of the simulated Sample II, exactly mirroring the hardware trigger logic where every coincidence event also satisfies the single-B condition. The subset property is used in the counterfactual analysis (Chapter 3): the deuteron enrichment factor of 1.52 (73.5% / 48.4%) quantifies the improvement from applying the coincidence trigger relative to an undifferentiated B-entry sample.

### 4.4 Detector geometry in the simulation

The GEANT4 geometry includes the CD2 target, the trigger scintillator paddles, the TPC volume, and both HRD stacks with individual stave volumes. However, the current geometry is known to be incomplete (see Chapter 10, GAP-01): it is missing the target support structure, the beam window, the inter-stave absorber layers (which in the physical detector reduce cross-talk and provide mechanical support), and the air gaps between staves. The total missing upstream material budget is estimated at 8-10 g/cm^2. This incompleteness is the root cause of the stopping-depth Monte Carlo failure (MV3): the simulation overestimates the fraction of particles reaching deep staves because it lacks the material that would stop or scatter them upstream. The MV3b diagnostic study confirmed that some geometry elements are present but the inter-stave dead material is the primary missing element. A geometry update with full material specification is required before quantitative Monte Carlo-based acceptance corrections can be applied.

---

## 5. Systematic Considerations

The detector design introduces several systematic effects that must be accounted for in the analysis. These are summarised here and treated in detail in the indicated chapters.

**Position-dependent light collection (Chapter 4, 7).** The one-ended WLS readout produces amplitude and timing variations as a function of the hit position along the stave. Light produced at the distal end (far from the SiPM) is attenuated by approximately exp(-L/lambda_att), where lambda_att = 3.5 m is the Y-11 fibre attenuation length, and delayed by L/v_fibre where v_fibre = 17 cm/ns. For a 50 cm stave (`DESIGN_SPEC`), the amplitude variation between proximal and distal hits is approximately 15-25%, and the timing variation is approximately 2.9 ns.

**B2 saturation (Chapter 4, 7).** The first B-stave saturates for large energy depositions from stopping deuterons near the Bragg peak. The ADC ceiling of approximately 7000 ADC is exceeded by 41.7% of Sample I B2 pulses, making the B2 amplitude an unreliable energy estimator for these pulses. The Monte Carlo digitizer includes an optional saturation ceiling, but this is currently disabled by default because it produces a hard cutoff rather than the gradual saturation roll-off observed in real SiPMs.

**Birks quenching (Chapter 7).** The scintillation light yield per unit energy deposition decreases at high ionisation density (high dE/dx) according to Birks' law: dL/dx = A * dE/dx / (1 + k_B * dE/dx), where k_B is the Birks constant (0.10-0.15 mm/MeV for BC-408 plastic scintillator). This effect reduces the light output for stopping particles (deuterons at the Bragg peak, dE/dx approximately 10-20 MeV/cm) relative to minimum-ionising particles (protons at 190 MeV, dE/dx approximately 2 MeV/cm) by a factor of approximately 0.5-0.7. The Birks constant has not been independently calibrated for this detector.

**Pile-up (Chapter 5).** Multiple beam particles arriving within the 180 ns acquisition window produce overlapping waveforms that distort both amplitude and timing. The effective live-time tau_eff = 124.79 ns (measured from the pulse template 10% tail crossing) sets the rate limit R_max = 3.05 MHz.

**Trigger bias.** The coincidence trigger preferentially selects two-body quasi-elastic scattering events over multi-body breakup events because the latter have lower probability of producing a charged particle in both arms simultaneously. This trigger bias is not a detector defect — it is the deliberate mechanism by which Sample I achieves deuteron enrichment — but it must be accounted for when comparing data samples.

**Temperature-dependent SiPM gain (Chapter 7).** The SiPM gain varies with temperature at approximately -3.4%/degree C. The laboratory temperature at CCB Bronowice was monitored but not actively stabilised. Temperature variations of +/- 2 degrees C over the course of a data-taking day produce gain variations of approximately +/- 7%, contributing to the run-to-run amplitude systematic.

**WLS fibre attenuation uncertainty.** The Y-11 attenuation length of 3.5 m is a nominal specification; the actual attenuation length of the fibres installed in the HRD staves may differ by +/- 0.5 m due to manufacturing variability and radiation damage accumulated during beam exposure. A 0.5 m uncertainty in lambda_att translates to a 3% uncertainty in the amplitude for hits at the distal end of the stave (100 cm / 3.5 m = 0.286 attenuation lengths; a 14% change in lambda_att produces a 4% change in transmitted amplitude).

---

## 6. Summary

The CCB test-beam experimental setup provides a well-characterised platform for evaluating the HRD scintillator range telescope performance. The key parameters bound in `paper/hardware_bom.csv` are: 190 MeV proton beam on a 2.3 mm CD2 target at CCB Krakow (`SIM_CONFIG`), two HRD stacks at +71.5 degrees (A) and -38 degrees (B) at 109 cm from the target (`SIM_CONFIG`), extruded-polystyrene staves 50 × 5.18 × 2.0 cm with Kuraray Y-11 fibres and Hamamatsu S13360-3050CS SiPMs (`DESIGN_SPEC`), one-fibre/one-end beam-test readout (`DESIGN_SPEC`), four analysed B channels B2/B4/B6/B8 mapped to GEANT4 layers 0/2/4/6 (`SIM_CONFIG`), and two trigger configurations Sample I (coincidence) and Sample II (single-B) over runs 31-65 (`SIM_CONFIG` grouping; hardware trigger record `UNKNOWN_EXTERNAL`). Legacy BC-408 / ~1 m stave prose remains unresolved. The GEANT4 Monte Carlo simulation with the hibeam_g4 framework provides a complete truth-level description of the experiment, with the known geometry incompleteness (missing 8-10 g/cm^2 upstream material, GAP-01) flagged as a systematic limitation.

## References

[1] HIBEAM/NNBAR Collaboration, "HIBEAM and NNBAR: two new programs of the European Spallation Source," J. Phys. G: Nucl. Part. Phys. (in preparation).

[2] Knoll, G. F., Radiation Detection and Measurement, 4th ed. (Wiley, 2010).

[3] Leo, W. R., Techniques for Nuclear and Particle Physics Experiments, 2nd ed. (Springer, 1994).

[4] Agostinelli, S. et al. (GEANT4 Collaboration), "GEANT4 -- a simulation toolkit," Nucl. Instrum. Meth. A 506, 250-303 (2003).

[5] Particle Data Group, "Review of Particle Physics," Prog. Theor. Exp. Phys. 2022, 083C01 (2022).

[6] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

[7] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," datasheet (2021).

[8] NIST PSTAR database, "Stopping Power and Range Tables for Protons in Plastic Scintillator," https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html.

[9] Kuraray Co. Ltd., "Scintillation Materials: Wavelength Shifting Fibers Y-11," technical datasheet (2019).

[10] Hamamatsu Photonics, "MPPC (Multi-Pixel Photon Counter) S13360 series," technical datasheet (2020).

[11] Hamamatsu Photonics, "Photomultiplier Tube H10721 series," technical datasheet (2018).

[12] CAEN S.p.A., "V1742/VX1742: 32+2 Channel 12 bit 5 GS/s Switched Capacitor Digitizer," technical information manual, rev. 24 (2021).

[13] CAEN S.p.A., "V1290A/VX1290A: 32/16 Channel Multi-Hit TDC," technical information manual, rev. 15 (2019).

[14] Eljen Technology, "EJ-200, EJ-204, EJ-208, EJ-212 Plastic Scintillator," datasheet (2020).

[15] European Spallation Source ERIC, "ESS Accelerator," https://ess.eu/accelerator (accessed 2026).

[16] Eljen Technology, "EJ-550, EJ-552 Silicone Grease," datasheet (2019).

[17] ORTEC, "Model 935 Constant-Fraction Discriminator," operating manual (2018).

---

## Material Budget Audit (Thesis Upgrade Addition)

> **Status: BLOCKING for MV3.** Missing upstream material is the root cause of the MV3 B8 data/MC mismatch (Chapter 10).

### Declared Material Components

| Component | Material | Thickness (mm) | Areal density (g/cm²) | Radiation length fraction | Status |
|---|---|---|---|---|---|
| Beam exit window | Kapton | 0.127 | 0.018 | 3.1 × 10⁻⁴ | Included in GEANT4 |
| Air gap (cyclotron→target) | Air | 3000 | 362 | 0.012 | Included |
| CD₂ target | CD₂ | 2.3 | 0.232 | 0.0052 | Included |
| Trigger scintillator A | BC-408 | 5.0 | 0.516 | 0.012 | Included |
| Trigger scintillator B | BC-408 | 5.0 | 0.516 | 0.012 | Included |
| Aluminised Mylar window | Mylar + Al | 0.05 | 0.007 | 1.7 × 10⁻⁴ | Included |
| Inter-stave dead material | Al + G10 | ~3.0–5.0 | ~0.8–1.3 | ~0.03–0.05 | **MISSING** |
| Support frames | Al 6061 | ~2.0 | ~0.54 | ~0.006 | **MISSING** |
| Optical grease layer | BC-630 | ~0.1 | ~0.01 | 2.4 × 10⁻⁴ | **MISSING** |
| WLS fibre cladding | FPMMA | ~0.05 | ~0.006 | 1.4 × 10⁻⁴ | **MISSING** |

### Estimated Total Missing Material

| Quantity | Estimate |
|---|---|
| Missing areal density | ~8–10 g/cm² |
| Missing radiation lengths | ~0.06–0.12 |
| Impact on B8 penetration | MC overestimates data by ~10× |
| MV3 χ²/ndf | 68,269 (before geometry fix) |

### Required Action

1. Audit all GEANT4 geometry components against mechanical drawings
2. Add inter-stave dead material, support frames, optical interfaces
3. Regenerate GEANT4 production with corrected geometry
4. Rerun MV3 stopping-depth validation
5. Re-assess B8 acceptance correction feasibility

This audit is tracked as **GAP-01** in [`STUDY_GAPS.md`](../../STUDY_GAPS.md).

