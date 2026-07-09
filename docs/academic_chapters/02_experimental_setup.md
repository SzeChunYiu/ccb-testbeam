# Chapter 2: Experimental Setup and Detector

## Abstract

The CCB test-beam experiment at the Cyclotron Centre Bronowice (Krakow, Poland) employed a 190 MeV proton beam incident on a 2.3 mm thick deuterated polyethylene (CD2) target to characterise the High-Rate Detector (HRD) scintillator range stacks for the HIBEAM/NNBAR experiment at the European Spallation Source. Two HRD telescopes — the A-stack (recoil arm, +71.5 degrees) and B-stack (downstream arm, -38 degrees) — each positioned 109 cm from the target, measured charged-particle energy deposition and arrival time using BC-408 plastic scintillator staves coupled to wavelength-shifting fibres read out by silicon photomultipliers. Each stave produced 18-sample ADC waveforms at 100 megasamples per second (10 ns per sample, 180 ns acquisition window). The trigger system defined two data-taking configurations: Sample I (runs 31-57, coincidence trigger requiring both A-stack and B-stack trigger scintillators) and Sample II (runs 58-65, single-B trigger). The GEANT4 Monte Carlo simulation using the hibeam_g4 framework with the Krakow beamline geometry provides truth-labelled events for validation.

---

## 1. Beam and Target

### 1.1 Proton beam parameters

The CCB cyclotron delivered a proton beam with kinetic energy T_p = 190.0 MeV. The beam spot diameter at the target position was 10 mm (GEANT4 macro parameter `/ElGen/Beamspot 10 mm`). The beam was operated in a pulsed mode with a macroscopic duty factor of approximately 0.38 (the fraction of time during which beam was actually delivered to the target, accounting for the cyclotron RF structure and extraction efficiency). The beam current, monitored by the trigger scintillator rates and an independent beam current monitor, varied between data-taking periods, with Sample I and Sample II corresponding to different beam intensities — the current monitor provides the stratification variable for the pile-up current-dependent excess analysis (see Chapter 5).

At 190 MeV, the proton velocity is beta = v/c = sqrt(1 - (m_p c^2 / (T_p + m_p c^2))^2) = sqrt(1 - (938.272 / (190.0 + 938.272))^2) = 0.565, corresponding to a relativistic gamma factor of 1.203. The proton range in plastic scintillator (BC-408, density approximately 1.032 g/cm^3) computed from the NIST PSTAR database using CSDA (continuous slowing-down approximation) is approximately 22.5 cm. This range significantly exceeds the total thickness of the four instrumented B-stack staves, ensuring that protons that do not undergo nuclear interactions penetrate to the deepest staves (B6, B8).

### 1.2 CD2 target

The target consisted of deuterated polyethylene, chemical formula (CD2)_n, with physical thickness 2.3 mm and density 1.01 g/cm^3 (approximately). The target introduces two distinct nuclear interaction channels relevant to this analysis:

**Quasi-elastic proton-deuteron scattering (p + d -> p + d).** This two-body reaction preserves the deuteron as a bound state and produces a correlated proton-deuteron pair in the final state. For 190 MeV incident protons, the centre-of-mass energy is sqrt(s) = sqrt(m_p^2 + m_d^2 + 2 m_d E_p_lab) = sqrt(938.27^2 + 1875.61^2 + 2 * 1875.61 * 190.0) = 2,831 MeV. The reaction is peripheral (large impact parameter), and the scattered proton and deuteron emerge with kinematic correlations determined by two-body phase space. The deuteron, being approximately twice as massive as the proton, carries a smaller fraction of the incident kinetic energy in the laboratory frame and is scattered to smaller angles. The B-stack, positioned at theta_B = -38 degrees relative to the beam direction, subtends the kinematic region where deuterons from quasi-elastic scattering are expected.

**Deuteron breakup (p + d -> p + p + n).** At 190 MeV incident energy, the proton kinetic energy exceeds the deuteron binding energy (2.225 MeV) by two orders of magnitude, and breakup is the dominant inelastic channel. The three-body final state produces a continuous distribution of proton energies and angles, with the B-stack predominantly detecting the highest-energy protons from this reaction.

**Proton-carbon scattering.** The carbon nuclei in the CD2 target produce additional reaction channels including elastic and inelastic proton scattering, carbon fragmentation, and — critically for the anomaly analysis (Chapter 9) — carbon-12 recoil nuclei with kinetic energies of 1-4 MeV that deposit all their energy in the first few micrometres of scintillator, producing the characteristic early-peaking waveform anomaly.

The GEANT4 simulation uses the cross-section file `sigma_pd_cm_190.txt` for the p+d centre-of-mass differential cross-section, which governs the angular distribution of scattered protons and deuterons. This is a data-driven cross-section input, not a theoretical model, ensuring that the simulated kinematic distributions match the best available experimental measurements.

### 1.3 Scattering kinematics

For quasi-elastic p + d -> p + d scattering, the laboratory-frame kinetic energy T_d of the scattered deuteron as a function of its scattering angle theta_d is:

T_d = (2 m_d m_p T_p / (m_d + m_p)^2) * cos^2(theta_d) * [1 - (m_d + m_p)T_p / (2 m_d m_p c^2) * tan^2(theta_d)] + O(T_p^2/m_p c^2)

For theta_d = 38 degrees (the B-stack angle), m_d/m_p = 1.998, and T_p = 190 MeV, the first-order term gives T_d approximately 190 * 4 * 1.998 / (2.998)^2 * cos^2(38 deg) = 190 * 7.992 / 8.988 * 0.621 = 104.7 MeV. A deuteron of 105 MeV kinetic energy has a range in BC-408 of approximately 5.5 cm (from NIST PSTAR CSDA), which places the Bragg peak between B2 and B4 — consistent with the observed stopping-depth distribution where deuterons stop predominantly at layers 0-1 (B2-B4). This kinematic calculation quantitatively explains why the coincidence trigger enriches Sample I in deuterons: the trigger requires a particle in the A-stack at +71.5 degrees (predominantly the recoil proton) AND a particle in the B-stack at -38 degrees (predominantly the scattered deuteron), selecting the two-body quasi-elastic channel.

---

## 2. Detector Geometry

### 2.1 HRD scintillator range telescopes

The detector geometry is specified by the file `krakow.geoconf` with parameters: `krakow_distance 109` (109 cm from target to the front face of each stack), `krakow_ang1 -38` (B-stack angle in degrees), `krakow_ang2 71.5` (A-stack angle in degrees), `krakow_nBars1 8` (number of B-stack staves), `krakow_nBars2 4` (number of A-stack staves). The geometry is built using the hibeam_g4_geobuilder tool and stored in `krakow_109_8-38deg_4-71deg.root`.

The B-stack comprises eight scintillator staves (staves B0 through B14 in the numbering scheme, with even-numbered staves B2, B4, B6, B8 instrumented for readout). The stave-to-stave centre spacing is 4 cm, giving a total B-stack depth of approximately 28 cm from B0 to B14. Only even-numbered staves are instrumented because the odd-numbered staves serve as passive material (representing the structural support and inter-stave gaps in the full HRD design). The A-stack similarly comprises four staves with A1 and A3 instrumented.

Each instrumented stave consists of a BC-408 plastic scintillator bar (polyvinyltoluene base, density 1.032 g/cm^3, refractive index 1.58, light yield approximately 64% of anthracene, rise time 0.9 ns, decay time 2.1 ns for the fast component and approximately 14 ns for the slow component). The scintillator bar is optically coupled to a wavelength-shifting (WLS) optical fibre that runs along the length of the bar. The coupling is achieved by embedding the fibre in a groove machined into the scintillator surface, with optical grease filling the interface to minimise reflection losses.

The WLS fibre absorbs the primary scintillation light (emission peak approximately 425 nm for BC-408) and re-emits it at a longer wavelength (typically 490-520 nm, depending on the WLS dye). The re-emission is isotropic, with a fraction of the light trapped by total internal reflection within the fibre and guided to the readout end. The characteristic propagation velocity of light in the WLS fibre is v_fibre = c / n_fibre approximately 17 cm/ns, where n_fibre approximately 1.76 is the effective refractive index of the fibre core. The fibre length per stave is approximately 100 cm (the scintillator bar length plus routing to the SiPM), giving a maximum propagation delay of 100 cm / 17 cm/ns = 5.9 ns for light produced at the distal end of the stave.

### 2.2 SiPM readout

Each WLS fibre is read out at one end by a silicon photomultiplier (SiPM). The SiPM consists of an array of single-photon avalanche diodes (SPADs) operating in Geiger mode, each with its own quenching resistor. The summed output current is proportional to the number of fired SPADs, which is proportional to the incident photon flux for fluxes well below the SPAD count (typically several thousand per SiPM). The SiPM gain — the charge produced per fired SPAD — is typically 10^5 to 10^6 electrons, and the single-photon timing resolution is typically 100-200 ps.

The one-ended readout configuration means that only the end of the WLS fibre closest to the SiPM is instrumented. The other end of the fibre is either uncoated (allowing light to escape) or coated with reflective paint (returning a fraction of the light back toward the SiPM with an additional round-trip delay). The position-dependent light collection efficiency and timing are the dominant contributions to the single-stave energy and timing resolution (see Chapters 4 and 7).

### 2.3 Digitizer electronics

The SiPM output current is converted to a voltage by a transimpedance amplifier and digitised by a flash analogue-to-digital converter (ADC) operating at 100 megasamples per second (MSPS). The sampling period of 10 ns defines the fundamental time resolution of the digitizer. Each triggered event records 18 consecutive ADC samples, corresponding to a total acquisition window of 180 ns. The first 4 samples (0-3, corresponding to the first 40 ns) precede the trigger decision and provide the baseline estimate.

The ADC has a finite dynamic range. In the data, a saturation ceiling is observed at approximately 7000 ADC, above which the ADC output is clipped. This saturation affects predominantly the B2 stave, where 41.7% of Sample I pulses and 6.1% of Sample II pulses exceed the ceiling. The Monte Carlo digitizer (see Chapter 3) includes an optional saturation clip at 7000 ADC to model this effect.

### 2.4 Trigger system

Two trigger scintillators (thin plastic scintillator paddles, approximately 5 mm thickness) are placed in front of the A-stack and B-stack entrance windows. These paddles produce fast timing signals (sub-nanosecond rise time) that are discriminated and fed into a coincidence unit. The trigger decision — whether to read out the waveform digitizers — is made within approximately 50 ns of the particle crossing, well within the 180 ns acquisition window.

The two trigger configurations are:

- **Sample I (coincidence, runs 31-57):** The discriminated signals from both the A-stack trigger paddle AND the B-stack trigger paddle must arrive within a coincidence window of approximately 15 ns. This requires a charged particle in both arms, selecting quasi-elastic scattering events. Run 43 was excluded due to anomalous baseline distributions (see Chapter 3 data quality monitoring).

- **Sample II (single-B, runs 58-65):** Only the B-stack trigger paddle is required to fire. The A-stack trigger is recorded but not required. This accepts a broader sample of events with a charged particle in the B arm, regardless of the A arm.

Runs 31-42 and run 64 are designated as calibration runs for timing corrections. These runs use the same trigger configuration as their respective samples but are reserved for calibrating the timewalk correction parameters and inter-stave time offsets, ensuring that the calibration is performed on independent data from the physics analysis.

---

## 3. Data Structure

### 3.1 Raw data format

The raw data for each run is stored as a ROOT file with naming convention `hrdb_run_NNNN.root` for B-stack data and `hrda_run_NNNN.root` for A-stack data. The total dataset comprises 110 ROOT files: 57 A-stack files and 53 B-stack files (some runs have B-stack data only). Each file contains a TTree named `h101` with three branches per event:

- **EVENTNO** (integer): Sequential event number within the run.
- **EVT** (integer): Event type flag encoding the trigger decision and data quality bits.
- **HRDv** (2D array of int16): Waveform data with dimensions (n_staves, n_channels, 18) containing the 18 ADC samples for each channel of each instrumented stave. For the B-stack, n_staves = 4 (B2, B4, B6, B8) and n_channels = 1 (one-ended readout).

The compressed B-stack data totals approximately 810 MB. The raw data and extracted pulse table are stored outside the git repository due to size constraints; their integrity is verified by SHA256 checksums recorded in Study S00.

### 3.2 Run structure

The run assignments for the two trigger configurations are detailed in Table 2.1.

**Table 2.1: Run structure for Sample I and Sample II**

| Sample | Trigger | Runs | Calibration Runs | Analysis Runs | Notes |
|---|---|---|---|---|---|
| I | Coincidence (A AND B) | 31-57 | 31-42 | 44, 46-48, 50-51, 53-57 | Run 43 excluded (data quality) |
| II | Single B | 58-65 | 64 | 58-63, 65 | Run 38, 45, 49, 52, 57 absent from A-stack |

The A-stack data (Samples III and IV) correspond to the same run ranges but are designated Sample III (same runs as Sample I) and Sample IV (same runs as Sample II). The A-stack data are not used in the quantitative analysis due to lower statistics and harder-to-analyse waveforms, but serve as an independent cross-check of the timing reconstruction pipeline (A1-A3 residuals reproduce the original analysis note's 1.43 ns value) and the trigger logic.

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

**Position-dependent light collection (Chapter 4, 7).** The one-ended WLS readout produces amplitude and timing variations as a function of the hit position along the stave. Light produced at the distal end (far from the SiPM) is attenuated by approximately exp(-L/lambda_att), where lambda_att is the WLS fibre attenuation length (typically 2-4 m), and delayed by L/v_fibre where v_fibre = 17 cm/ns. For a 100 cm stave, the amplitude variation between proximal and distal hits is approximately 25-40%, and the timing variation is 5.9 ns.

**B2 saturation (Chapter 4, 7).** The first B-stave saturates for large energy depositions from stopping deuterons near the Bragg peak. The ADC ceiling of approximately 7000 ADC is exceeded by 41.7% of Sample I B2 pulses, making the B2 amplitude an unreliable energy estimator for these pulses. The Monte Carlo digitizer includes an optional saturation ceiling, but this is currently disabled by default because it produces a hard cutoff rather than the gradual saturation roll-off observed in real SiPMs.

**Birks quenching (Chapter 7).** The scintillation light yield per unit energy deposition decreases at high ionisation density (high dE/dx) according to Birks' law: dL/dx = A * dE/dx / (1 + k_B * dE/dx), where k_B is the Birks constant (typically 0.1-0.2 mm/MeV for plastic scintillator). This effect reduces the light output for stopping particles (deuterons at the Bragg peak, dE/dx approximately 10-20 MeV/cm) relative to minimum-ionising particles (protons at 190 MeV, dE/dx approximately 2 MeV/cm) by a factor of approximately 0.5-0.7. The Birks constant has not been independently calibrated for this detector.

**Pile-up (Chapter 5).** Multiple beam particles arriving within the 180 ns acquisition window produce overlapping waveforms that distort both amplitude and timing. The effective live-time tau_eff = 124.79 ns (measured from the pulse template 10% tail crossing) sets the rate limit R_max = 3.05 MHz.

**Trigger bias.** The coincidence trigger preferentially selects two-body quasi-elastic scattering events over multi-body breakup events because the latter have lower probability of producing a charged particle in both arms simultaneously. This trigger bias is not a detector defect — it is the deliberate mechanism by which Sample I achieves deuteron enrichment — but it must be accounted for when comparing data samples.

---

## References

[1] HIBEAM/NNBAR Collaboration, "HIBEAM and NNBAR: two new programs of the European Spallation Source," J. Phys. G: Nucl. Part. Phys. (in preparation).

[2] Knoll, G. F., Radiation Detection and Measurement, 4th ed. (Wiley, 2010).

[3] Leo, W. R., Techniques for Nuclear and Particle Physics Experiments, 2nd ed. (Springer, 1994).

[4] Agostinelli, S. et al. (GEANT4 Collaboration), "GEANT4 -- a simulation toolkit," Nucl. Instrum. Meth. A 506, 250-303 (2003).

[5] Particle Data Group, "Review of Particle Physics," Prog. Theor. Exp. Phys. 2022, 083C01 (2022).

[6] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

[7] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," datasheet (2021).

[8] NIST PSTAR database, "Stopping Power and Range Tables for Protons in Plastic Scintillator," https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html.
